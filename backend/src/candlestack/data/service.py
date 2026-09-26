"""``DataService``: instruments and candles of both markets, the entry point of the module.

A candles request is checked (catalog, period, candle count), its period is split into the
source's chunks (closed months or years, closed days, today), every chunk comes from Redis or
the source (single-flight, a few at once), and the chunks are joined, resampled for stocks,
sliced to ``[start, end)``, checked for gaps and fingerprinted in a worker thread.
"""

import asyncio
import bisect
import logging
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from functools import partial

import httpx
import orjson
import polars as pl
from anyio import to_thread
from redis.asyncio import Redis

from candlestack.core import RateLimiter, Settings
from candlestack.data.cache import Cache, decode_chunk, encode_chunk
from candlestack.data.candles import (
    candle_count,
    closed_only,
    expected_bins_fixed,
    expected_bins_sessions,
    find_gaps,
    fingerprint,
    resample_sessions,
    slice_range,
    suggest,
)
from candlestack.data.catalog import normalise_query
from candlestack.data.catalog_store import CatalogStore
from candlestack.data.errors import (
    InstrumentNotFound,
    InvalidRequest,
    PeriodOutOfRange,
    SourceUnavailable,
    TooManyCandles,
)
from candlestack.data.models import (
    CandleSet,
    Instrument,
    InstrumentId,
    InstrumentInfo,
    Market,
    SourceHealth,
    Timeframe,
    empty_candles,
)
from candlestack.data.sessions import Session
from candlestack.data.sources.alpaca import AlpacaSource
from candlestack.data.sources.base import DAY, DataSource, Period
from candlestack.data.sources.binance import BinanceSource

logger = logging.getLogger(__name__)

# Chunks of one request fetched at once.
CHUNK_CONCURRENCY = 16
FIRST_TTL = 7 * DAY
# An instrument without any candle yet (a new listing) is asked again after an hour.
FIRST_NONE_TTL = 3600
HEALTH_TTL = 60

# Patched by tests to move the clock.
_time = time.time


class DataService:
    def __init__(
        self,
        *,
        sources: Mapping[Market, DataSource],
        cache: Cache,
        catalogs: CatalogStore,
        candles_max: int,
    ) -> None:
        self._sources = sources
        self._cache = cache
        self._catalogs = catalogs
        self._candles_max = candles_max

    async def search(
        self, q: str, market: Market | None = None, limit: int = 20
    ) -> list[Instrument]:
        """Instruments matching ``q``, best first (ranking in ``candlestack.data.catalog``)."""
        if limit <= 0 or not normalise_query(q):
            return []
        catalog = await self._catalogs.catalog(market)
        return catalog.search(q, market, limit)

    async def instrument(self, instrument_id: InstrumentId) -> InstrumentInfo:
        """The instrument and its available period. ``available_from`` is ``None`` when the
        source cannot be asked right now."""
        instrument = await self._find(instrument_id)
        source = self._sources[instrument_id.market]
        sessions = await source.sessions()
        try:
            first = await self._first(source, instrument)
        except SourceUnavailable as exc:
            logger.warning("First candle of %s unknown: %s", instrument_id, exc.detail)
            first = None
        return InstrumentInfo(
            instrument=instrument,
            timeframes=tuple(Timeframe),
            available_from=first,
            available_to=newest_minute(int(_time()), sessions),
            max_candles=self._candles_max,
        )

    async def candles(
        self, instrument_id: InstrumentId, timeframe: Timeframe, start: int, end: int
    ) -> CandleSet:
        """Closed candles of ``[start, end)`` with their gaps and fingerprint.

        Raises ``InvalidRequest``, ``InstrumentNotFound``, ``PeriodOutOfRange``,
        ``TooManyCandles``, ``SourceUnavailable`` and ``DataIntegrityError``.
        """
        if start >= end:
            raise InvalidRequest(f"start ({start}) must be before end ({end}).")
        instrument = await self._find(instrument_id)
        source = self._sources[instrument_id.market]
        now = int(_time())
        sessions = await source.sessions()
        first = await self._first(source, instrument)
        available_from = None if first is None else bin_open(first, timeframe, sessions)
        if end > now or (available_from is not None and start < available_from):
            raise PeriodOutOfRange(
                instrument_id, timeframe, available_from, now, start=start, end=end
            )
        requested = candle_count(start, end, timeframe, sessions)
        if requested > self._candles_max:
            hint = suggest(start, end, timeframe, self._candles_max, sessions)
            raise TooManyCandles(requested, self._candles_max, hint)

        base = source.base_timeframe(timeframe)
        periods = [] if first is None else source.periods(base, start, end, now)
        blobs = await self._chunks(source, instrument, base, periods)
        return await to_thread.run_sync(
            partial(
                assemble,
                source,
                instrument_id,
                timeframe,
                base,
                start,
                end,
                now,
                sessions,
                periods,
                blobs,
            )
        )

    async def sources_health(self) -> dict[str, SourceHealth]:
        """Reachability of every source, each checked at most once a minute."""
        sources = list(self._sources.values())
        results = await asyncio.gather(*(self._health(source) for source in sources))
        return {source.name: health for source, health in zip(sources, results, strict=True)}

    async def _find(self, instrument_id: InstrumentId) -> Instrument:
        catalog = await self._catalogs.catalog(instrument_id.market)
        instrument = catalog.get(instrument_id)
        if instrument is None:
            raise InstrumentNotFound(instrument_id)
        return instrument

    async def _first(self, source: DataSource, instrument: Instrument) -> int | None:
        async def fetch() -> tuple[bytes, int]:
            first = await source.first_timestamp(instrument.symbol)
            if first is None:
                return b"", FIRST_NONE_TTL
            return str(first).encode(), FIRST_TTL

        blob = await self._cache.get_or_fetch(f"first:{instrument.id}", fetch)
        return int(blob) if blob else None

    async def _chunks(
        self,
        source: DataSource,
        instrument: Instrument,
        timeframe: Timeframe,
        periods: Sequence[Period],
    ) -> list[bytes]:
        limit = asyncio.Semaphore(CHUNK_CONCURRENCY)

        async def fetch(period: Period) -> tuple[bytes, int]:
            frame = await source.fetch_period(instrument.symbol, timeframe, period)
            blob = await to_thread.run_sync(encode_chunk, frame, period.end)
            return blob, period.ttl

        async def chunk(period: Period) -> bytes:
            async with limit:
                name = f"candles:{instrument.id}:{timeframe}:{period.label}"
                return await self._cache.get_or_fetch(name, partial(fetch, period))

        return await asyncio.gather(*(chunk(period) for period in periods))

    async def _health(self, source: DataSource) -> SourceHealth:
        async def fetch() -> tuple[bytes, int]:
            return orjson.dumps(asdict(await source.health())), HEALTH_TTL

        blob = await self._cache.get_or_fetch(f"health:{source.name}", fetch)
        return SourceHealth(**orjson.loads(blob))


def build_data_service(settings: Settings, redis: Redis, http: httpx.AsyncClient) -> DataService:
    """The service with both sources; no I/O happens until it is used."""
    limiter = RateLimiter(redis)
    cache = Cache(redis)
    sources: dict[Market, DataSource] = {
        Market.CRYPTO: BinanceSource(settings, http, limiter),
        Market.STOCK: AlpacaSource(settings, http, limiter, cache),
    }
    return DataService(
        sources=sources,
        cache=cache,
        catalogs=CatalogStore(cache, sources),
        candles_max=settings.candles_max,
    )


def newest_minute(now: int, sessions: Sequence[Session] | None) -> int:
    """Open time of the newest 1m bin closed at ``now``; for stocks within the latest session
    that has begun."""
    minute = now // 60 * 60
    if sessions:
        latest = bisect.bisect_right(sessions, now - 60, key=lambda session: session.open) - 1
        if latest >= 0:
            minute = min(minute, sessions[latest].close)
    return minute - 60


def bin_open(ts: int, timeframe: Timeframe, sessions: Sequence[Session] | None) -> int:
    """Open time of the bin of ``timeframe`` that holds the moment ``ts``."""
    step = timeframe.seconds
    if sessions is None:
        return ts // step * step
    index = bisect.bisect_right(sessions, ts, key=lambda session: session.open) - 1
    if index < 0 or ts >= sessions[index].close:
        return ts
    opens = sessions[index].open
    return opens + (ts - opens) // step * step


def assemble(
    source: DataSource,
    instrument_id: InstrumentId,
    timeframe: Timeframe,
    base: Timeframe,
    start: int,
    end: int,
    now: int,
    sessions: list[Session] | None,
    periods: Sequence[Period],
    blobs: Sequence[bytes],
) -> CandleSet:
    """The candle set from cached chunks of the base timeframe (CPU work, run in a thread).

    Candles count as known up to when the live chunk was fetched: a candle that closed after
    that is neither returned nor a gap (it comes with the next fetch).
    """
    frames, as_of = [], now
    for period, blob in zip(periods, blobs, strict=True):
        frame, complete_until = decode_chunk(blob)
        frames.append(frame)
        if period.kind == "live":
            as_of = min(as_of, complete_until)
    frame = pl.concat(frames) if frames else empty_candles()
    if sessions is not None and timeframe is not base:
        frame = resample_sessions(frame, timeframe, sessions)
    frame = slice_range(closed_only(frame, timeframe, as_of, sessions), start, end)
    if sessions is None:
        expected = expected_bins_fixed(start, end, timeframe, now=as_of)
    else:
        expected = expected_bins_sessions(start, end, timeframe, sessions, now=as_of)
    gaps = find_gaps(frame["ts"], expected, timeframe, sessions)
    return CandleSet(
        instrument=instrument_id,
        timeframe=timeframe,
        start=start,
        end=end,
        source=source.name,
        feed=source.feed,
        frame=frame,
        gaps=gaps.ranges,
        gaps_total=gaps.total,
        fingerprint=fingerprint(
            source.name, source.feed, instrument_id, timeframe, start, end, frame
        ),
    )

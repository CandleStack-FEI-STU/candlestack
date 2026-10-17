"""The first candle of each instrument (``available_from``): asked from its source once and kept
in Redis (``first:<instrument>``).

The instrument detail and the candle checks wait for it. The list only reads what Redis has, for
a whole page in one round trip, and looks up a few of the instruments it lacks in the background,
so the next visit shows them: a page of the list never sends a burst of requests to a source, and
never waits for one. The lookups in the background are capped per page, per process and per
minute in every process (a share of the source's budget, ``data:rl:first-warm:<market>``); each
also counts against the source's own budget, like any other request.
"""

import asyncio
import logging
import time
from collections.abc import Mapping, Sequence

from candlestack.core import RateLimiter
from candlestack.data.cache import Cache
from candlestack.data.errors import DataIntegrityError, SourceUnavailable
from candlestack.data.models import Instrument, InstrumentId, Market
from candlestack.data.sources.base import DAY, DataSource

logger = logging.getLogger(__name__)

# The first candle of a symbol never moves: history is only added after it. The long life keeps
# the list from asking the sources again; the value still expires, so that a symbol given to
# another listing (a ticker reused, a pair listed again) is asked again some day.
FIRST_TTL = 90 * DAY
# An instrument without any candle yet (a new listing) is asked again after an hour.
FIRST_NONE_TTL = 3600
# Instruments of one page of the list looked up in the background, at most; its first rows first.
WARM_PER_PAGE = 5
# Lookups in the background of one process at once, at most; the others wait for a later page.
WARM_RUNNING_MAX = 10
# Lookups in the background per minute and market in all processes: Binance 60 (120 of its 6000
# weight), Alpaca 6 (a tenth of the smallest ALPACA_RATE_LIMIT), so the charts keep the rest.
WARM_RATE_KEY = "data:rl:first-warm"
WARM_PER_MINUTE = {Market.CRYPTO: 60, Market.STOCK: 6}
# How long a market's lookups in the background stop after its source could not be asked (down,
# its budget spent, no keys): one warning per pause instead of one per page.
WARM_PAUSE_SECONDS = 60

# Patched by tests to move the clock.
_monotonic = time.monotonic


def _name(instrument_id: InstrumentId) -> str:
    return f"first:{instrument_id}"


class Firsts:
    def __init__(
        self, cache: Cache, sources: Mapping[Market, DataSource], limiter: RateLimiter
    ) -> None:
        self._cache = cache
        self._sources = sources
        self._limiter = limiter
        self._running: dict[InstrumentId, asyncio.Task[None]] = {}
        self._paused_until: dict[Market, float] = {}

    async def first(self, instrument: Instrument) -> int | None:
        """Open time of the instrument's first candle, ``None`` when it has none; from Redis or
        its source (single-flight). Raises the source's ``SourceUnavailable`` and
        ``DataIntegrityError``."""
        source = self._sources[instrument.market]

        async def fetch() -> tuple[bytes, int]:
            first = await source.first_timestamp(instrument.symbol)
            if first is None:
                return b"", FIRST_NONE_TTL
            return str(first).encode(), FIRST_TTL

        blob = await self._cache.get_or_fetch(_name(instrument.id), fetch)
        return int(blob) if blob else None

    async def known(self, instruments: Sequence[Instrument]) -> list[int | None]:
        """The first candle of each instrument as far as Redis knows it (one ``MGET``), ``None``
        for one without a candle or not known yet. Never asks a source: up to ``WARM_PER_PAGE``
        of the unknown ones are looked up in the background."""
        blobs = await self._cache.get_many([_name(i.id) for i in instruments])
        if self._cache.available():  # without Redis a lookup would be lost
            self._warm([i for i, blob in zip(instruments, blobs, strict=True) if blob is None])
        return [int(blob) if blob else None for blob in blobs]

    def _warm(self, missing: Sequence[Instrument]) -> None:
        now = _monotonic()
        started = 0
        for instrument in missing:
            if started == WARM_PER_PAGE or len(self._running) >= WARM_RUNNING_MAX:
                return
            if instrument.id in self._running or now < self._paused_until.get(
                instrument.market, 0.0
            ):
                continue
            task = asyncio.create_task(self._lookup(instrument))
            self._running[instrument.id] = task
            task.add_done_callback(lambda _, key=instrument.id: self._running.pop(key, None))
            started += 1

    async def _lookup(self, instrument: Instrument) -> None:
        market = instrument.market
        try:
            share = WARM_PER_MINUTE[market]
            if await self._limiter.hit(f"{WARM_RATE_KEY}:{market}", share) > 0:
                return
            await self.first(instrument)
        except SourceUnavailable as exc:
            self._paused_until[market] = _monotonic() + max(
                WARM_PAUSE_SECONDS, exc.retry_after or 0
            )
            logger.warning("First candle of %s not looked up: %s", instrument.id, exc.detail)
        except DataIntegrityError as exc:
            logger.warning("First candle of %s not looked up: %s", instrument.id, exc.detail)
        except Exception:
            logger.exception("Looking up the first candle of %s failed", instrument.id)

    async def wait(self) -> None:
        """Waits for the lookups running in the background."""
        await asyncio.gather(*self._running.values())

    async def close(self) -> None:
        """Stops the lookups running in the background (on shutdown)."""
        tasks = list(self._running.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

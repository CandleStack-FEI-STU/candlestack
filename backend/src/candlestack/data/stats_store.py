"""The 24 h stats of the instruments (last price, change, volume in USD), kept in Redis and in
process memory, refreshed in the background.

Each market's stats are one Redis value (``data:v1:stats:<market>``, the frame as Arrow IPC after
the time of the refresh, like a candle chunk) that a refresh replaces every few minutes. Every
row keeps the time it was fetched: a refresh that could not ask for some instruments carries
their last rows over, until those are ``KEEP_SECONDS`` old. Searches only
read: the process's copy, checked against Redis at most once a minute (only the 8-byte fetch
time is read unless it changed), so a search never waits for a source. Stats live
``KEEP_SECONDS`` from their fetch time, in Redis and in the process alike; without any,
instruments have no stats and sort last.

``MarketFrames`` is this way of keeping a frame per market; the daily candles of the mini charts
(``spark_store``) are kept the same way.
"""

import asyncio
import logging
import struct
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from typing import ClassVar, override

import polars as pl
from anyio import to_thread

from candlestack.data.cache import (
    HEADER_SIZE,
    Cache,
    decode_chunk,
    decode_fetched_at,
    encode_chunk,
)
from candlestack.data.catalog import MARKET_STATS_SCHEMA
from candlestack.data.errors import DataError
from candlestack.data.models import STATS_SCHEMA, Market, SourceStats

logger = logging.getLogger(__name__)

# How often each market's stats are fetched: one Binance request for every pair, and about 27
# Alpaca requests for every stock, whose numbers change only while the market is open.
REFRESH_SECONDS = {Market.CRYPTO: 300, Market.STOCK: 600}
# Stats this long after their fetch are not shown any more: Redis drops them, and so does the
# process.
KEEP_SECONDS = 2 * 3600
# How often a process looks for newer stats in Redis (another process may have refreshed them).
RELOAD_SECONDS = 60
# The lock of a refresh expires this long after it was taken or last renewed; it is renewed
# every RENEW_SECONDS while the refresh runs, however long that takes (the stocks wait for their
# share of the Alpaca budget), and runs out soon after a process that died holding it.
LOCK_MS = 120_000
RENEW_SECONDS = 40.0

# Patched by tests to move the clock.
_time = time.time

Fetch = Callable[[], Awaitable[SourceStats]]
"""Fetches a market's stats (or daily candles) from its source."""

# A market's stats as stored: ``STATS_SCHEMA`` and when each row was fetched (epoch seconds).
STORED_SCHEMA = pl.Schema({**STATS_SCHEMA, "fetched_at": pl.Int64})


@dataclass(frozen=True, slots=True)
class Entry:
    fetched_at: int
    frame: pl.DataFrame


class MarketFrames:
    """A frame per market that a background refresh replaces and searches only read, in Redis
    (``data:v1:<kind>:<market>``) and in process memory, each row with the time it was fetched:
    what ``StatsStore`` and ``SparkStore`` share. One process refreshes a market at a time (a
    lock renewed while it runs); the others adopt what it stored."""

    kind: ClassVar[str]
    # The frame a source reports; stored with ``fetched_at`` after it.
    schema: ClassVar[pl.Schema]
    # Rows this long after their fetch are not shown any more: Redis drops them, and so does the
    # process.
    keep_seconds: ClassVar[int]

    def __init__(self, cache: Cache, markets: Iterable[Market]) -> None:
        self._cache = cache
        self._markets = list(markets)
        self._entries: dict[Market, Entry] = {}
        self._reload_at: dict[Market, float] = {}
        self._stored_schema = pl.Schema({**self.schema, "fetched_at": pl.Int64})

    async def _current(self) -> dict[Market, Entry]:
        """The frames of the markets that have them, read from Redis at most once a minute per
        market, never from a source."""
        for market in self._markets:
            if time.monotonic() >= self._reload_at.get(market, 0.0):
                self._reload_at[market] = time.monotonic() + RELOAD_SECONDS
                await self._reload(market)
        self._forget_old()
        return self._entries

    def _changed(self) -> None:
        """Called when a market's frame was adopted or dropped, for what is derived from them."""

    @staticmethod
    def _now() -> float:
        return _time()

    async def _refresh(self, market: Market, fetch: Fetch, stale: Callable[[int], bool]) -> bool:
        """Fetches the market's frame when the stored one is missing or ``stale`` (given its
        fetch time) and no other process is fetching it, and stores it. Rows of the symbols the
        source could not ask for are carried over. A source that fails leaves the last frame in
        place (logged) and gives ``False``; the next call tries again."""
        name = f"{self.kind}:{market}"
        started = int(_time())
        if not await self._due(market, stale):
            return True
        token = await self._cache.lock(name, LOCK_MS)
        if token is None:
            return True  # another process is refreshing it; adopted on its next reload
        try:
            # It may have stored a new one between the check and the lock.
            if not await self._due(market, stale):
                return True
            async with _renewing(self._cache, name, token):
                found = await fetch()
            frame = self._merged(found, self._entries.get(market), started, int(_time()))
            blob = await to_thread.run_sync(encode_chunk, frame, started)
            # Redis keeps it as long as the process does: keep_seconds from the refresh.
            await self._cache.set(name, blob, max(1, self.keep_seconds - (int(_time()) - started)))
        except DataError as exc:
            logger.warning("Refreshing the %s %s failed: %s", market, self.kind, exc.detail)
            return False
        finally:
            await self._cache.unlock(name, token)
        self._adopt(market, Entry(started, frame))
        logger.info("Refreshed the %s %s: %d rows", market, self.kind, frame.height)
        return True

    async def _due(self, market: Market, stale: Callable[[int], bool]) -> bool:
        """Whether the market's frame, in Redis or this process, is missing or stale."""
        await self._reload(market)
        entry = self._entries.get(market)
        return entry is None or stale(entry.fetched_at)

    async def _reload(self, market: Market) -> None:
        """Adopts the frame in Redis when it is newer than the process's copy and not too old;
        only its fetch time is read otherwise."""
        name = f"{self.kind}:{market}"
        head = await self._cache.head(name, HEADER_SIZE)
        if head is None:
            return
        current = self._entries.get(market)
        try:
            fetched_at = decode_fetched_at(head)
            if current is not None and fetched_at <= current.fetched_at:
                return
            if _time() - fetched_at >= self.keep_seconds:
                return  # about to expire in Redis too
            blob = await self._cache.get(name)
            if blob is None:
                return
            frame, fetched_at = await to_thread.run_sync(decode_chunk, blob)
            if frame.schema != self._stored_schema:
                raise ValueError(f"columns {frame.schema}")
        except (struct.error, OSError, ValueError, pl.exceptions.PolarsError) as exc:
            # An unreadable value must not break the list: it goes, a refresh writes a new one.
            logger.warning("Dropping the stored %s %s: %s", market, self.kind, exc)
            await self._cache.delete(name)
            return
        self._adopt(market, Entry(fetched_at, frame))

    def _adopt(self, market: Market, entry: Entry) -> None:
        self._entries[market] = entry
        self._changed()

    def _forget_old(self) -> None:
        now = _time()
        for market, entry in list(self._entries.items()):
            if now - entry.fetched_at >= self.keep_seconds:
                del self._entries[market]
                self._changed()

    def _merged(
        self, found: SourceStats, last: Entry | None, started: int, now: int
    ) -> pl.DataFrame:
        """The new rows, fetched at ``started``, plus the last rows of the symbols the source
        could not ask for, with their own fetch time, while they are younger than
        ``keep_seconds``."""
        frame = found.frame.select(*self.schema).with_columns(fetched_at=pl.lit(started, pl.Int64))
        if not found.failed or last is None:
            return frame
        kept = last.frame.filter(
            pl.col("symbol").is_in(list(found.failed)),
            pl.col("fetched_at") > now - self.keep_seconds,
        )
        return pl.concat([frame, kept])


class StatsStore(MarketFrames):
    kind = "stats"
    schema = STATS_SCHEMA
    keep_seconds = KEEP_SECONDS

    def __init__(self, cache: Cache, markets: Iterable[Market]) -> None:
        super().__init__(cache, markets)
        self._table: pl.DataFrame | None = None
        self._table_until = 0.0  # when the oldest row of the table expires

    async def table(self) -> pl.DataFrame:
        """The stats of every market that has them (``MARKET_STATS_SCHEMA``). Reads Redis at most
        once a minute per market, never a source."""
        entries = await self._current()
        if self._table is None or _time() >= self._table_until:
            self._table, self._table_until = await to_thread.run_sync(
                _table, dict(entries), _time()
            )
        return self._table

    async def refresh(self, market: Market, fetch: Fetch) -> None:
        """Fetches the market's stats when the stored ones are ``REFRESH_SECONDS`` old (or
        missing) and no other process is fetching them, and stores them. Instruments the source
        could not ask for keep their last stats. A source that fails leaves the last stats in
        place (logged); the next call tries again."""
        started = int(_time())
        await self._refresh(
            market, fetch, lambda fetched_at: started - fetched_at >= REFRESH_SECONDS[market]
        )

    @override
    def _changed(self) -> None:
        self._table = None


def _table(entries: dict[Market, Entry], now: float) -> tuple[pl.DataFrame, float]:
    """The rows of every market younger than ``KEEP_SECONDS`` (``MARKET_STATS_SCHEMA``), and
    when the oldest of them expires (CPU work, run in a thread)."""
    frames = [
        entry.frame.filter(pl.col("fetched_at") > now - KEEP_SECONDS).with_columns(
            market=pl.lit(str(market))
        )
        for market, entry in entries.items()
    ]
    rows = (
        pl.concat(frames) if frames else pl.DataFrame(schema={**STORED_SCHEMA, "market": pl.String})
    )
    oldest = rows.select(pl.col("fetched_at").min()).item()
    until = float("inf") if oldest is None else oldest + KEEP_SECONDS
    return rows.select(*MARKET_STATS_SCHEMA), until


@asynccontextmanager
async def _renewing(cache: Cache, name: str, token: str) -> AsyncIterator[None]:
    """Renews the lock of ``name`` every ``RENEW_SECONDS`` while the block runs, so a long
    refresh keeps it; logs once when another process took it meanwhile."""
    done = asyncio.Event()

    async def renew() -> None:
        while not done.is_set():
            with suppress(TimeoutError):
                await asyncio.wait_for(done.wait(), RENEW_SECONDS)
            if not done.is_set() and not await cache.extend(name, token, LOCK_MS):
                logger.warning("The lock of the %s refresh was lost while it ran", name)
                return

    task = asyncio.create_task(renew())
    try:
        yield
    finally:
        done.set()
        await task

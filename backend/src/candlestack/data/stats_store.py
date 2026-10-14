"""The 24 h stats of the instruments (last price, change, volume in USD), kept in Redis and in
process memory, refreshed in the background.

Each market's stats are one Redis value (``data:v1:stats:<market>``, the frame as Arrow IPC after
its fetch time, like a candle chunk) that a refresh replaces every few minutes. Searches only
read: the process's copy, checked against Redis at most once a minute (only the 8-byte fetch
time is read unless it changed), so a search never waits for a source. Stats live
``KEEP_SECONDS`` from their fetch time, in Redis and in the process alike; without any,
instruments have no stats and sort last.
"""

import asyncio
import logging
import struct
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass

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
"""Fetches a market's stats from its source."""


@dataclass(frozen=True, slots=True)
class _Entry:
    fetched_at: int
    frame: pl.DataFrame


def _name(market: Market) -> str:
    return f"stats:{market}"


class StatsStore:
    def __init__(self, cache: Cache, markets: Iterable[Market]) -> None:
        self._cache = cache
        self._markets = list(markets)
        self._entries: dict[Market, _Entry] = {}
        self._reload_at: dict[Market, float] = {}
        self._table: pl.DataFrame | None = None

    async def table(self) -> pl.DataFrame:
        """The stats of every market that has them (``MARKET_STATS_SCHEMA``). Reads Redis at most
        once a minute per market, never a source."""
        for market in self._markets:
            if time.monotonic() >= self._reload_at.get(market, 0.0):
                self._reload_at[market] = time.monotonic() + RELOAD_SECONDS
                await self._reload(market)
        self._forget_old()
        if self._table is None:
            self._table = pl.concat(
                [
                    entry.frame.select(pl.lit(str(market)).alias("market"), *STATS_SCHEMA)
                    for market, entry in self._entries.items()
                ]
                or [pl.DataFrame(schema=MARKET_STATS_SCHEMA)]
            )
        return self._table

    async def refresh(self, market: Market, fetch: Fetch) -> None:
        """Fetches the market's stats when the stored ones are ``REFRESH_SECONDS`` old (or
        missing) and no other process is fetching them, and stores them. Instruments the source
        could not ask for keep their last stats. A source that fails leaves the last stats in
        place (logged); the next call tries again."""
        name = _name(market)
        await self._reload(market)
        entry = self._entries.get(market)
        started = int(_time())
        if entry is not None and started - entry.fetched_at < REFRESH_SECONDS[market]:
            return
        token = await self._cache.lock(name, LOCK_MS)
        if token is None:
            return  # another process is refreshing them; adopted on its next reload
        try:
            async with _renewing(self._cache, name, token):
                found = await fetch()
            frame = _merged(found, entry)
            blob = await to_thread.run_sync(encode_chunk, frame, started)
            # Redis keeps them as long as the process does: KEEP_SECONDS from the fetch.
            await self._cache.set(name, blob, max(1, KEEP_SECONDS - (int(_time()) - started)))
        except DataError as exc:
            logger.warning("Refreshing the %s stats failed: %s", market, exc.detail)
            return
        finally:
            await self._cache.unlock(name, token)
        self._adopt(market, _Entry(started, frame))
        logger.info("Refreshed the %s stats: %d instruments", market, frame.height)

    async def _reload(self, market: Market) -> None:
        """Adopts the stats in Redis when they are newer than the process's copy and not too
        old; only their fetch time is read otherwise."""
        name = _name(market)
        head = await self._cache.head(name, HEADER_SIZE)
        if head is None:
            return
        current = self._entries.get(market)
        try:
            fetched_at = decode_fetched_at(head)
            if current is not None and fetched_at <= current.fetched_at:
                return
            if _time() - fetched_at >= KEEP_SECONDS:
                return  # about to expire in Redis too
            blob = await self._cache.get(name)
            if blob is None:
                return
            frame, fetched_at = await to_thread.run_sync(decode_chunk, blob)
            if frame.schema != STATS_SCHEMA:
                raise ValueError(f"columns {frame.schema}")
        except (struct.error, OSError, ValueError, pl.exceptions.PolarsError) as exc:
            # An unreadable value must not break the list: it goes, a refresh writes a new one.
            logger.warning("Dropping the stored %s stats: %s", market, exc)
            await self._cache.delete(name)
            return
        self._adopt(market, _Entry(fetched_at, frame))

    def _adopt(self, market: Market, entry: _Entry) -> None:
        self._entries[market] = entry
        self._table = None

    def _forget_old(self) -> None:
        now = _time()
        for market, entry in list(self._entries.items()):
            if now - entry.fetched_at >= KEEP_SECONDS:
                del self._entries[market]
                self._table = None


def _merged(found: SourceStats, last: _Entry | None) -> pl.DataFrame:
    """The new stats, plus the last ones of the symbols the source could not ask for."""
    frame = found.frame.select(*STATS_SCHEMA)
    if not found.failed or last is None:
        return frame
    kept = last.frame.filter(pl.col("symbol").is_in(list(found.failed)))
    return pl.concat([frame, kept.select(*STATS_SCHEMA)])


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

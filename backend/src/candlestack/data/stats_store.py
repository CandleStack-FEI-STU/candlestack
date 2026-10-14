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

# A market's stats as stored: ``STATS_SCHEMA`` and when each row was fetched (epoch seconds).
STORED_SCHEMA = pl.Schema({**STATS_SCHEMA, "fetched_at": pl.Int64})


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
        self._table_until = 0.0  # when the oldest row of the table expires

    async def table(self) -> pl.DataFrame:
        """The stats of every market that has them (``MARKET_STATS_SCHEMA``). Reads Redis at most
        once a minute per market, never a source."""
        for market in self._markets:
            if time.monotonic() >= self._reload_at.get(market, 0.0):
                self._reload_at[market] = time.monotonic() + RELOAD_SECONDS
                await self._reload(market)
        self._forget_old()
        if self._table is None or _time() >= self._table_until:
            self._table, self._table_until = await to_thread.run_sync(
                _table, dict(self._entries), _time()
            )
        return self._table

    async def refresh(self, market: Market, fetch: Fetch) -> None:
        """Fetches the market's stats when the stored ones are ``REFRESH_SECONDS`` old (or
        missing) and no other process is fetching them, and stores them. Instruments the source
        could not ask for keep their last stats. A source that fails leaves the last stats in
        place (logged); the next call tries again."""
        name = _name(market)
        started = int(_time())
        if not await self._due(market, started):
            return
        token = await self._cache.lock(name, LOCK_MS)
        if token is None:
            return  # another process is refreshing them; adopted on its next reload
        try:
            # It may have stored new ones between the check and the lock.
            if not await self._due(market, started):
                return
            async with _renewing(self._cache, name, token):
                found = await fetch()
            frame = _merged(found, self._entries.get(market), started, int(_time()))
            blob = await to_thread.run_sync(encode_chunk, frame, started)
            # Redis keeps them as long as the process does: KEEP_SECONDS from the refresh.
            await self._cache.set(name, blob, max(1, KEEP_SECONDS - (int(_time()) - started)))
        except DataError as exc:
            logger.warning("Refreshing the %s stats failed: %s", market, exc.detail)
            return
        finally:
            await self._cache.unlock(name, token)
        self._adopt(market, _Entry(started, frame))
        logger.info("Refreshed the %s stats: %d instruments", market, frame.height)

    async def _due(self, market: Market, now: int) -> bool:
        """Whether the market's stats, in Redis or this process, are ``REFRESH_SECONDS`` old or
        missing."""
        await self._reload(market)
        entry = self._entries.get(market)
        return entry is None or now - entry.fetched_at >= REFRESH_SECONDS[market]

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
            if frame.schema != STORED_SCHEMA:
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


def _merged(found: SourceStats, last: _Entry | None, started: int, now: int) -> pl.DataFrame:
    """The new stats, fetched at ``started``, plus the last rows of the symbols the source could
    not ask for, with their own fetch time, while they are younger than ``KEEP_SECONDS``."""
    frame = found.frame.select(*STATS_SCHEMA).with_columns(fetched_at=pl.lit(started, pl.Int64))
    if not found.failed or last is None:
        return frame
    kept = last.frame.filter(
        pl.col("symbol").is_in(list(found.failed)), pl.col("fetched_at") > now - KEEP_SECONDS
    )
    return pl.concat([frame, kept])


def _table(entries: dict[Market, _Entry], now: float) -> tuple[pl.DataFrame, float]:
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

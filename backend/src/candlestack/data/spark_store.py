"""The last daily candles of the instruments, for the mini charts of the list, kept in Redis and
in process memory like the stats (``MarketFrames``) and refreshed in the background once a day.

Each market's candles are one Redis value (``data:v1:spark:<market>``) that a refresh replaces
after the market's daily close: crypto after 00:00 UTC, stocks after the New York close, each
``SETTLE_SECONDS`` later so that the source has the day's candle. A refresh that could not ask
for some instruments carries their last candles over, until those are ``KEEP_SECONDS`` old; one
that fails is tried again ``RETRY_SECONDS`` later. A search reads the candles of its page only.
"""

import time
from collections.abc import Iterable, Sequence
from typing import override

import polars as pl
from anyio import to_thread

from candlestack.data.cache import Cache
from candlestack.data.models import SPARK_DAYS, SPARK_SCHEMA, Instrument, Market, Spark
from candlestack.data.stats_store import Entry, Fetch, MarketFrames

# A day's candle is asked for this long after the day closed: Binance has it at once, Alpaca's
# IEX daily bar may take a few minutes.
SETTLE_SECONDS = 900
# Candles this long after their fetch are not shown any more: a day and a half, so that a
# failed daily refresh leaves yesterday's candles until the next one.
KEEP_SECONDS = 36 * 3600
# After a refresh that failed, the next try waits this long (a whole refresh is many requests).
RETRY_SECONDS = 1800


class SparkStore(MarketFrames):
    kind = "spark"
    schema = SPARK_SCHEMA
    keep_seconds = KEEP_SECONDS

    def __init__(self, cache: Cache, markets: Iterable[Market]) -> None:
        super().__init__(cache, markets)
        self._retry_at: dict[Market, float] = {}
        # The days of each market's mini charts, worked out once per stored frame.
        self._days: dict[Market, list[int]] | None = None

    async def sparks(self, instruments: Sequence[Instrument]) -> list[Spark | None]:
        """The mini chart of each instrument, ``None`` without any candle. Reads Redis at most
        once a minute per market, never a source."""
        entries = dict(await self._current())
        if not instruments or not entries:
            return [None] * len(instruments)
        if self._days is None:
            self._days = await to_thread.run_sync(_days, entries)
        return await to_thread.run_sync(_sparks, entries, self._days, instruments, self._now())

    async def refresh(self, market: Market, fetch: Fetch, closed_at: int) -> None:
        """Fetches the market's daily candles when the stored ones were fetched before the day
        that closed at ``closed_at`` settled (or are missing) and no other process is fetching
        them, and stores them. Instruments the source could not ask for keep their last candles.
        A source that fails leaves the last candles in place (logged), and the next try waits
        ``RETRY_SECONDS``."""
        if time.monotonic() < self._retry_at.get(market, 0.0):
            return
        # Set before: also a refresh that fails unexpectedly waits before the next try.
        self._retry_at[market] = time.monotonic() + RETRY_SECONDS
        settled = closed_at + SETTLE_SECONDS
        if await self._refresh(market, fetch, lambda fetched_at: fetched_at < settled):
            del self._retry_at[market]

    @override
    def _changed(self) -> None:
        self._days = None


def _days(entries: dict[Market, Entry]) -> dict[Market, list[int]]:
    """The last ``SPARK_DAYS`` days with a candle of each market, oldest first: the slots of its
    mini charts (CPU work, run in a thread)."""
    return {
        market: entry.frame.get_column("ts").unique().sort().tail(SPARK_DAYS).to_list()
        for market, entry in entries.items()
    }


def _sparks(
    entries: dict[Market, Entry],
    days: dict[Market, list[int]],
    instruments: Sequence[Instrument],
    now: float,
) -> list[Spark | None]:
    """The mini charts of the instruments from the stored candles younger than
    ``KEEP_SECONDS``: a slot per day of the market, a gap where the instrument has no candle
    (CPU work, run in a thread)."""
    found: dict[tuple[Market, str], Spark] = {}
    for market, entry in entries.items():
        slots = {day: index for index, day in enumerate(days.get(market, []))}
        symbols = [i.symbol for i in instruments if i.market is market]
        if not slots or not symbols:
            continue
        rows = entry.frame.filter(
            pl.col("symbol").is_in(symbols),
            pl.col("ts").is_in(list(slots)),
            pl.col("fetched_at") > now - KEEP_SECONDS,
        ).select(*SPARK_SCHEMA)
        for symbol, ts, open_, high, low, close in rows.iter_rows():
            spark = found.setdefault((market, symbol), [None] * len(slots))
            spark[slots[ts]] = (ts, open_, high, low, close)
    return [found.get((i.market, i.symbol)) for i in instruments]

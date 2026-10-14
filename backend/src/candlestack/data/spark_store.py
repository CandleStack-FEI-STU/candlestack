"""The last daily candles of the instruments, for the mini charts of the list, kept in Redis and
in process memory like the stats (``MarketFrames``) and refreshed in the background once a day.

Each market's candles are one Redis value (``data:v1:spark:<market>``) that a refresh replaces
after the market's daily close: crypto after 00:00 UTC, stocks after the New York close, each
``SETTLE_SECONDS`` later so that the source has the day's candle. Candles that are missing (a new
environment, evicted from Redis) or from before the last daily close are fetched at once. The
instruments a refresh could not ask for keep their last candles and are asked again every
``RETRY_SECONDS`` until they are answered or the next daily close; a refresh that fails is tried
again ``RETRY_SECONDS`` later. Candles are shown until ``GRACE_SECONDS`` after the market's next
daily close (after its next session for stocks: weekends and holidays keep them). A search looks
up the candles of its page only, in an index built once per stored frame.
"""

from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass
from functools import partial
from typing import override

import polars as pl

from candlestack.data.cache import Cache
from candlestack.data.models import (
    SPARK_DAYS,
    SPARK_SCHEMA,
    Instrument,
    Market,
    SourceStats,
    Spark,
)
from candlestack.data.stats_store import Entry, MarketFrames

# A day's candle is asked for this long after the day closed: Binance has it at once, Alpaca's
# IEX daily bar may take a few minutes.
SETTLE_SECONDS = 900
# Candles are shown until this long after the next daily close settled: time for its refresh and
# retries before they count as outdated.
GRACE_SECONDS = 12 * 3600
# How long Redis and the process keep stored candles at most: the longest wait for a next stock
# session (a long weekend with a holiday) and the grace.
KEEP_SECONDS = 7 * 86_400
# How long the next try waits after a refresh that failed or left some instruments unanswered.
RETRY_SECONDS = 1800

# The candles as stored: ``SPARK_SCHEMA`` and until when they are shown (epoch seconds).
SPARK_STORED_SCHEMA = pl.Schema({**SPARK_SCHEMA, "shown_until": pl.Int64})

DailyFetch = Callable[[frozenset[str] | None], Awaitable[SourceStats]]
"""Fetches a market's daily candles from its source: of every instrument, or of the given
symbols only."""


@dataclass(frozen=True, slots=True)
class _Index:
    """A market's stored candles ready for a page: the slot of each day in a mini chart, the
    candles sorted by symbol and day, and for each symbol its first row, its number of rows and
    until when they are shown."""

    slots: dict[int, int]
    frame: pl.DataFrame
    rows: dict[str, tuple[int, int, int]]


@dataclass(frozen=True, slots=True)
class _Pending:
    """The instruments the refresh of one daily close could not ask for, asked again from
    ``retry_at`` on."""

    settled: int
    symbols: frozenset[str]
    retry_at: float


class SparkStore(MarketFrames):
    kind = "spark"
    schema = SPARK_STORED_SCHEMA
    keep_seconds = KEEP_SECONDS

    def __init__(self, cache: Cache, markets: Iterable[Market]) -> None:
        super().__init__(cache, markets)
        self._retry_at: dict[Market, float] = {}
        self._pending: dict[Market, _Pending] = {}
        self._index: dict[Market, _Index] = {}

    async def sparks(self, instruments: Sequence[Instrument]) -> list[Spark | None]:
        """The mini chart of each instrument, ``None`` without any candle shown. Reads Redis at
        most once a minute per market, never a source."""
        await self._current()
        now = self._now()
        found: dict[tuple[Market, str], Spark] = {}
        for market, index in self._index.items():
            symbols = [i.symbol for i in instruments if i.market is market]
            for symbol, spark in _lookup(index, symbols, now):
                found[market, symbol] = spark
        return [found.get((i.market, i.symbol)) for i in instruments]

    async def refresh(
        self, market: Market, fetch: DailyFetch, closed_at: int, next_close: int
    ) -> None:
        """Fetches the market's daily candles when the stored ones are missing or were fetched
        before the day that closed at ``closed_at`` settled, and no other process is fetching
        them, and stores them, shown until ``GRACE_SECONDS`` after ``next_close`` settles. The
        instruments the source could not ask for keep their last candles and are asked again
        every ``RETRY_SECONDS`` until the next daily close. A source that fails leaves the last
        candles in place (logged), and the next try waits ``RETRY_SECONDS``."""
        now = self._now()
        if now < self._retry_at.get(market, 0.0):
            return
        # Set before: also a refresh that fails unexpectedly waits before the next try.
        self._retry_at[market] = now + RETRY_SECONDS
        settled = closed_at + SETTLE_SECONDS
        shown_until = next_close + SETTLE_SECONDS + GRACE_SECONDS
        failed: list[frozenset[str]] = []

        async def marked(only: frozenset[str] | None) -> SourceStats:
            found = await fetch(only)
            failed.append(found.failed)
            frame = found.frame.with_columns(shown_until=pl.lit(shown_until, pl.Int64))
            return SourceStats(frame, found.failed)

        ok = await self._refresh(
            market, partial(marked, None), lambda fetched_at: fetched_at < settled
        )
        pending = self._pending.get(market)
        if pending is not None and pending.settled != settled:
            del self._pending[market]  # the next daily close asks for every instrument
            pending = None
        if ok and not failed and pending is not None and now >= pending.retry_at:
            ok = await self._refresh(
                market,
                partial(marked, pending.symbols),
                lambda _fetched_at: True,
                only=pending.symbols,
            )
        if not ok:
            return
        del self._retry_at[market]
        if failed and failed[0]:
            self._pending[market] = _Pending(settled, failed[0], now + RETRY_SECONDS)
        elif failed:
            self._pending.pop(market, None)

    @override
    def _merged(
        self,
        found: SourceStats,
        last: Entry | None,
        started: int,
        now: int,
        only: frozenset[str] | None = None,
    ) -> pl.DataFrame:
        # Stored by symbol, so that the index needs no copy of the candles.
        return super()._merged(found, last, started, now, only).sort("symbol", "ts")

    @override
    def _changed(self, market: Market) -> None:
        # Built at once, before anything else reads it, so a search never sees the index of
        # another frame than the market's (some 20 ms for the stocks, once a day).
        entry = self._entries.get(market)
        if entry is None:
            self._index.pop(market, None)
        else:
            self._index[market] = _indexed(entry)


def _indexed(entry: Entry) -> _Index:
    """The index of a market's stored candles: its last ``SPARK_DAYS`` days with a candle are
    the slots of its mini charts, oldest first."""
    frame = entry.frame
    if not frame.get_column("symbol").is_sorted():
        frame = frame.sort("symbol", "ts")
    days = frame.get_column("ts").unique().sort().tail(SPARK_DAYS).to_list()
    groups = (
        frame.with_row_index("row")
        .group_by("symbol", maintain_order=True)
        .agg(pl.col("row").first(), pl.len(), pl.col("shown_until").min())
    )
    return _Index(
        {day: slot for slot, day in enumerate(days)},
        frame.select(*SPARK_SCHEMA),
        {symbol: (row, count, until) for symbol, row, count, until in groups.iter_rows()},
    )


def _lookup(index: _Index, symbols: Iterable[str], now: float) -> Iterable[tuple[str, Spark]]:
    """The mini charts of the symbols whose candles are still shown: a slot per day of the
    market, a gap where the symbol has no candle."""
    rows = [
        row
        for symbol in symbols
        if (found := index.rows.get(symbol)) is not None and found[2] > now
        for row in range(found[0], found[0] + found[1])
    ]
    sparks: dict[str, Spark] = {}
    for symbol, ts, open_, high, low, close in index.frame[rows].iter_rows():
        slot = index.slots.get(ts)
        if slot is not None:
            spark = sparks.setdefault(symbol, [None] * len(index.slots))
            spark[slot] = (ts, open_, high, low, close)
    return sparks.items()

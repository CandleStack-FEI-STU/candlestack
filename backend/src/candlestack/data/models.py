"""Instruments, timeframes and candle sets: the vocabulary of the data module.

Times are UTC epoch seconds everywhere; a candle is labelled by its open time.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Self

import polars as pl

from candlestack.data.errors import InvalidRequest

Source = Literal["binance", "alpaca"]
Feed = Literal["spot", "iex"]

_ID_EXAMPLE = "for example crypto:BTCUSDT or stock:AAPL"
_SYMBOL_MAX = 32
# Letters and digits of any script (Binance lists pairs such as 币安人生USDT) and dots
# (BRK.B); the first character is a letter or digit.
_SYMBOL = re.compile(r"[^\W_](?:[^\W_]|\.)*")


class Market(StrEnum):
    CRYPTO = "crypto"
    STOCK = "stock"


class Timeframe(StrEnum):
    """Candle durations; iteration goes from the shortest to the longest."""

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"

    @property
    def seconds(self) -> int:
        return _SECONDS[self]

    def larger(self) -> "list[Timeframe]":
        """The longer timeframes, shortest first."""
        members = list(Timeframe)
        return members[members.index(self) + 1 :]


_SECONDS = {
    Timeframe.M1: 60,
    Timeframe.M5: 300,
    Timeframe.M15: 900,
    Timeframe.H1: 3600,
    Timeframe.H4: 14400,
    Timeframe.D1: 86400,
}


@dataclass(frozen=True, slots=True)
class InstrumentId:
    """``<market>:<symbol>``, e.g. ``crypto:BTCUSDT``; build it from text with ``parse``."""

    market: Market
    symbol: str

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parses an id, trimming whitespace, lower-casing the market and upper-casing the symbol.

        Raises ``InvalidRequest`` (a ``ValueError``) with a message for the user.
        """
        market, colon, symbol = value.partition(":")
        market, symbol = market.strip().lower(), symbol.strip().upper()
        if not colon or not symbol:
            raise InvalidRequest(
                f"Instrument id '{value}' must be <market>:<symbol>, {_ID_EXAMPLE}."
            )
        if market not in Market:
            raise InvalidRequest(
                f"Unknown market '{market}' in instrument id '{value}'. "
                f"The markets are crypto and stock, {_ID_EXAMPLE}."
            )
        if len(symbol) > _SYMBOL_MAX or not _SYMBOL.fullmatch(symbol):
            raise InvalidRequest(
                f"Symbol '{symbol}' in instrument id '{value}' is not valid: use letters, "
                f"digits and dots, at most {_SYMBOL_MAX} characters, {_ID_EXAMPLE}."
            )
        return cls(Market(market), symbol)

    def __str__(self) -> str:
        return f"{self.market}:{self.symbol}"


@dataclass(frozen=True, slots=True)
class Instrument:
    """One tradable instrument of a source's catalog.

    ``exchange`` is set for stocks (``NASDAQ``, ``NYSE``, ...), ``base`` and ``quote`` for
    crypto pairs (``BTC``, ``USDT``).
    """

    id: InstrumentId
    name: str
    source: Source
    feed: Feed
    exchange: str | None = None
    base: str | None = None
    quote: str | None = None

    @property
    def market(self) -> Market:
        return self.id.market

    @property
    def symbol(self) -> str:
        return self.id.symbol


CANDLE_SCHEMA = pl.Schema(
    {
        "ts": pl.Int64,  # open time, UTC epoch seconds
        "open": pl.Float64,
        "high": pl.Float64,
        "low": pl.Float64,
        "close": pl.Float64,
        "volume": pl.Float64,
    }
)


def empty_candles() -> pl.DataFrame:
    return pl.DataFrame(schema=CANDLE_SCHEMA)


@dataclass(frozen=True, eq=False)
class CandleSet:
    """The answer to one candles request: ``[start, end)`` of one instrument and timeframe.

    ``frame`` has ``CANDLE_SCHEMA`` and holds only closed candles, sorted by ``ts``. ``gaps``
    lists merged ``(start, end)`` ranges of missing candles, earliest first and capped (see
    ``find_gaps``); ``gaps_total`` counts all missing candles.
    """

    instrument: InstrumentId
    timeframe: Timeframe
    start: int
    end: int
    source: Source
    feed: Feed
    frame: pl.DataFrame
    gaps: list[tuple[int, int]]
    gaps_total: int
    fingerprint: str


@dataclass(frozen=True)
class SearchResult:
    """Instruments found, best first, and the searched markets that were left out because
    their catalog cannot be loaded right now (their source is down)."""

    items: list[Instrument]
    unavailable: list[Market]


@dataclass(frozen=True)
class InstrumentInfo:
    """An instrument plus what a client needs to build a valid candles request.

    ``available_from`` is the open time of the first candle (``None`` when the source has none
    or could not be asked), ``available_to`` the open time of the newest closed 1m bin at the
    time of the answer (for stocks the last minute of the latest session that has begun).
    """

    instrument: Instrument
    timeframes: tuple[Timeframe, ...]
    available_from: int | None
    available_to: int
    max_candles: int


@dataclass(frozen=True)
class SourceHealth:
    """Whether a source answered its cheapest request; ``detail`` says why not."""

    ok: bool
    latency_ms: int | None
    detail: str | None

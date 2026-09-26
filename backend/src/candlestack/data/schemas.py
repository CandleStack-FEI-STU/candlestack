"""Response bodies of the data API, with the descriptions and examples the API reference shows.

The candles body is the exception on the way out: ``candles_json`` serializes it with orjson
straight from the Polars columns, and ``CandlesOut`` only documents it.
"""

from collections.abc import Mapping
from typing import Literal, Self

import orjson
from pydantic import BaseModel, Field

from candlestack.data.models import (
    CandleSet,
    Feed,
    Instrument,
    InstrumentInfo,
    Market,
    Source,
    SourceHealth,
    Timeframe,
)


class InstrumentOut(BaseModel):
    """One instrument of a source's catalog."""

    id: str = Field(description="Instrument id, `<market>:<symbol>`.", examples=["crypto:BTCUSDT"])
    market: Market = Field(examples=["crypto"])
    symbol: str = Field(description="Symbol as the source spells it.", examples=["BTCUSDT"])
    name: str = Field(
        description="Crypto: `<base>/<quote>`. Stocks: the company or fund name from Alpaca.",
        examples=["BTC/USDT"],
    )
    source: Source = Field(examples=["binance"])
    feed: Feed = Field(
        description="`spot` (Binance spot) or `iex` (Alpaca IEX: IEX trades only).",
        examples=["spot"],
    )
    exchange: str | None = Field(
        description="Listing exchange of a stock (`NASDAQ`, `NYSE`, `ARCA`, ...); null for crypto.",
        examples=[None],
    )
    base: str | None = Field(
        description="Base asset of a crypto pair; null for stocks.", examples=["BTC"]
    )
    quote: str | None = Field(
        description="Quote asset of a crypto pair; null for stocks.", examples=["USDT"]
    )

    @classmethod
    def of(cls, instrument: Instrument) -> Self:
        return cls(
            id=str(instrument.id),
            market=instrument.market,
            symbol=instrument.symbol,
            name=instrument.name,
            source=instrument.source,
            feed=instrument.feed,
            exchange=instrument.exchange,
            base=instrument.base,
            quote=instrument.quote,
        )


class InstrumentSearchOut(BaseModel):
    items: list[InstrumentOut] = Field(description="Best matches first.")
    count: int = Field(description="Number of items.", examples=[1])


class InstrumentDetailOut(InstrumentOut):
    """An instrument and what a valid `/candles` request for it can ask for."""

    timeframes: list[Timeframe] = Field(examples=[list(Timeframe)])
    available_from: int | None = Field(
        description="Open time of the first candle, UTC epoch seconds; null when not known.",
        examples=[1502928000],
    )
    available_to: int = Field(
        description="Open time of the newest closed 1m candle, UTC epoch seconds.",
        examples=[1790424000],
    )
    max_candles: int = Field(
        description="Most candles one `/candles` response may hold.", examples=[50000]
    )

    @classmethod
    def of_info(cls, info: InstrumentInfo) -> Self:
        return cls(
            **InstrumentOut.of(info.instrument).model_dump(),
            timeframes=list(info.timeframes),
            available_from=info.available_from,
            available_to=info.available_to,
            max_candles=info.max_candles,
        )


class CandlesMeta(BaseModel):
    instrument: str = Field(description="Instrument id, normalised.", examples=["crypto:BTCUSDT"])
    timeframe: Timeframe = Field(examples=["1h"])
    start: int = Field(
        description="Start of the period (inclusive), UTC epoch seconds.", examples=[1717200000]
    )
    end: int = Field(
        description="End of the period (exclusive), UTC epoch seconds.", examples=[1717214400]
    )
    source: Source = Field(examples=["binance"])
    feed: Feed = Field(examples=["spot"])
    fingerprint: str = Field(
        description="`sha256:<hex>` over the request and its candles: the same candles give the "
        "same value, any changed number another.",
        examples=["sha256:3b1f0c9e5d7a4b2c8e6f1a0d9c7b5e3f2a4c6e8d0b1f3a5c7e9d2b4f6a8c0e1d"],
    )
    count: int = Field(description="Number of candles returned.", examples=[3])
    gaps: list[tuple[int, int]] = Field(
        description="Missing candles as merged `[start, end)` ranges in UTC epoch seconds, "
        "earliest first, at most 100.",
        examples=[[[1717207200, 1717210800]]],
    )
    gaps_total: int = Field(description="Number of missing candles in total.", examples=[1])


class CandlesOut(BaseModel):
    """Candles as columns: index `i` of every array is one candle, oldest first."""

    meta: CandlesMeta
    t: list[int] = Field(
        description="Open times, UTC epoch seconds, strictly increasing.",
        examples=[[1717200000, 1717203600, 1717210800]],
    )
    o: list[float] = Field(description="Open prices.", examples=[[67491.0, 67612.5, 67580.1]])
    h: list[float] = Field(description="High prices.", examples=[[67700.0, 67650.0, 67640.0]])
    l: list[float] = Field(description="Low prices.", examples=[[67420.2, 67510.0, 67488.8]])  # noqa: E741
    c: list[float] = Field(description="Close prices.", examples=[[67612.4, 67540.3, 67601.9]])
    v: list[float] = Field(
        description="Volumes: base asset for crypto, shares (IEX only) for stocks.",
        examples=[[512.31, 398.07, 421.55]],
    )


def candles_json(candles: CandleSet) -> bytes:
    """The ``CandlesOut`` body of a candle set, serialized from its columns in one pass."""
    frame = candles.frame
    return orjson.dumps(
        {
            "meta": {
                "instrument": str(candles.instrument),
                "timeframe": str(candles.timeframe),
                "start": candles.start,
                "end": candles.end,
                "source": candles.source,
                "feed": candles.feed,
                "fingerprint": candles.fingerprint,
                "count": frame.height,
                "gaps": candles.gaps,
                "gaps_total": candles.gaps_total,
            },
            "t": frame["ts"].to_list(),
            "o": frame["open"].to_list(),
            "h": frame["high"].to_list(),
            "l": frame["low"].to_list(),
            "c": frame["close"].to_list(),
            "v": frame["volume"].to_list(),
        }
    )


class SourceHealthOut(BaseModel):
    status: Literal["ok", "error"]
    latency_ms: int | None = Field(
        description="Duration of the check; null when the source did not answer.", examples=[84]
    )
    detail: str | None = Field(description="What failed; null when ok.", examples=[None])


class SourcesHealthOut(BaseModel):
    """Reachability of the market data sources, checked at most once a minute."""

    status: Literal["ok", "error"] = Field(description="`ok` when every source is reachable.")
    sources: dict[Source, SourceHealthOut]

    @classmethod
    def of(cls, health: Mapping[str, SourceHealth]) -> Self:
        sources = {
            name: SourceHealthOut(
                status="ok" if check.ok else "error",
                latency_ms=check.latency_ms,
                detail=check.detail,
            )
            for name, check in health.items()
        }
        ok = all(check.ok for check in health.values())
        return cls.model_validate({"status": "ok" if ok else "error", "sources": sources})

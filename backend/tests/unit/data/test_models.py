import dataclasses

import polars as pl
import pytest

from candlestack.data import (
    CANDLE_SCHEMA,
    CandleSet,
    Instrument,
    InstrumentId,
    InvalidRequest,
    Market,
    Timeframe,
    empty_candles,
)


def test_timeframes_in_order_with_seconds() -> None:
    assert [(tf.value, tf.seconds) for tf in Timeframe] == [
        ("1m", 60),
        ("5m", 300),
        ("15m", 900),
        ("1h", 3600),
        ("4h", 14400),
        ("1d", 86400),
    ]


def test_timeframe_larger() -> None:
    assert Timeframe.H1.larger() == [Timeframe.H4, Timeframe.D1]
    assert Timeframe.D1.larger() == []


def test_timeframe_from_text() -> None:
    assert Timeframe("15m") is Timeframe.M15
    with pytest.raises(ValueError, match="2h"):
        Timeframe("2h")


@pytest.mark.parametrize(
    ("text", "market", "symbol"),
    [
        ("crypto:BTCUSDT", Market.CRYPTO, "BTCUSDT"),
        ("crypto:btcusdt", Market.CRYPTO, "BTCUSDT"),
        ("  Stock : aapl ", Market.STOCK, "AAPL"),
        ("stock:brk.b", Market.STOCK, "BRK.B"),
        ("crypto:币安人生usdt", Market.CRYPTO, "币安人生USDT"),
    ],
)
def test_instrument_id_parse_normalises(text: str, market: Market, symbol: str) -> None:
    instrument_id = InstrumentId.parse(text)

    assert instrument_id == InstrumentId(market, symbol)
    assert str(instrument_id) == f"{market}:{symbol}"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "must be <market>:<symbol>"),
        ("BTCUSDT", "must be <market>:<symbol>"),
        ("crypto:", "must be <market>:<symbol>"),
        (":BTCUSDT", "Unknown market ''"),
        ("forex:EURUSD", "Unknown market 'forex'"),
        ("crypto:BTC:USDT", "Symbol 'BTC:USDT'"),
        ("crypto:BTC USDT", "Symbol 'BTC USDT'"),
        ("crypto:BTC/USDT", "Symbol 'BTC/USDT'"),
        ("stock:.A", "Symbol '.A'"),
        ("crypto:" + "A" * 33, "at most 32 characters"),
    ],
)
def test_instrument_id_parse_rejects(text: str, message: str) -> None:
    with pytest.raises(InvalidRequest, match=message) as error:
        InstrumentId.parse(text)

    assert isinstance(error.value, ValueError)
    assert "crypto:BTCUSDT" in error.value.detail


def test_instrument_id_is_hashable_and_frozen() -> None:
    instrument_id = InstrumentId.parse("stock:AAPL")

    assert {instrument_id: 1}[InstrumentId(Market.STOCK, "AAPL")] == 1
    with pytest.raises(dataclasses.FrozenInstanceError):
        instrument_id.symbol = "MSFT"  # ty: ignore[invalid-assignment]


def test_instrument() -> None:
    crypto = Instrument(
        id=InstrumentId.parse("crypto:BTCUSDT"),
        name="BTC/USDT",
        source="binance",
        feed="spot",
        base="BTC",
        quote="USDT",
    )
    stock = Instrument(
        id=InstrumentId.parse("stock:AAPL"),
        name="Apple Inc. Common Stock",
        source="alpaca",
        feed="iex",
        exchange="NASDAQ",
    )

    assert (crypto.market, crypto.symbol, crypto.exchange) == (Market.CRYPTO, "BTCUSDT", None)
    assert (stock.market, stock.symbol, stock.base, stock.quote) == (
        Market.STOCK,
        "AAPL",
        None,
        None,
    )


def test_empty_candles_has_the_schema() -> None:
    frame = empty_candles()

    assert frame.schema == CANDLE_SCHEMA
    assert frame.columns == ["ts", "open", "high", "low", "close", "volume"]
    assert frame.height == 0
    assert CANDLE_SCHEMA["ts"] == pl.Int64
    assert CANDLE_SCHEMA["volume"] == pl.Float64


def test_candle_set() -> None:
    candles = CandleSet(
        instrument=InstrumentId.parse("crypto:BTCUSDT"),
        timeframe=Timeframe.H1,
        start=0,
        end=7200,
        source="binance",
        feed="spot",
        frame=empty_candles(),
        gaps=[(0, 7200)],
        gaps_total=2,
        fingerprint="sha256:" + "0" * 64,
    )

    assert candles.gaps_total == 2
    with pytest.raises(dataclasses.FrozenInstanceError):
        candles.start = 1  # ty: ignore[invalid-assignment]

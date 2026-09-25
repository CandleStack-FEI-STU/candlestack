import pytest

from candlestack.data import (
    DataError,
    DataIntegrityError,
    InstrumentId,
    InstrumentNotFound,
    InvalidRequest,
    PeriodOutOfRange,
    SourceUnavailable,
    Timeframe,
    TooManyCandles,
)

BTC = InstrumentId.parse("crypto:BTCUSDT")


def test_every_error_is_a_data_error_with_a_detail() -> None:
    errors: list[DataError] = [
        InstrumentNotFound(BTC),
        InvalidRequest("start must be before end"),
        PeriodOutOfRange(BTC, Timeframe.H1, 1502942400, 1790424000),
        TooManyCandles(131040, 50000, "Use 5m or a larger timeframe."),
        SourceUnavailable("alpaca", "Alpaca did not answer in time. Try again in a minute."),
        DataIntegrityError("1 candle has negative volume"),
    ]

    for error in errors:
        assert isinstance(error, DataError)
        assert error.detail
        assert str(error) == error.detail


def test_invalid_request_is_a_value_error() -> None:
    assert isinstance(InvalidRequest("bad"), ValueError)


def test_instrument_not_found() -> None:
    error = InstrumentNotFound(InstrumentId.parse("crypto:FOOBAR"))

    assert error.instrument == "crypto:FOOBAR"
    assert error.detail == (
        "Instrument crypto:FOOBAR does not exist. Search the instruments to find a valid id."
    )


def test_period_out_of_range_before_the_first_candle() -> None:
    error = PeriodOutOfRange(BTC, Timeframe.H1, 1502942400, 1790424000, start=1500000000)

    assert (error.instrument, error.timeframe) == ("crypto:BTCUSDT", "1h")
    assert (error.available_from, error.available_to) == (1502942400, 1790424000)
    assert error.detail == (
        "crypto:BTCUSDT has 1h candles from 2017-08-17T04:00:00Z (1502942400). "
        "Set start to 1502942400 or later."
    )


def test_period_out_of_range_in_the_future() -> None:
    error = PeriodOutOfRange(BTC, Timeframe.H1, 1502942400, 1790424000, end=1790500000)

    assert error.detail == (
        "crypto:BTCUSDT has 1h candles up to 2026-09-26T12:00:00Z (1790424000). "
        "Set end to 1790424000 or earlier."
    )


def test_period_out_of_range_both_sides() -> None:
    error = PeriodOutOfRange(
        BTC, Timeframe.H1, 1502942400, 1790424000, start=1500000000, end=1790500000
    )

    assert "Set start to 1502942400 or later." in error.detail
    assert "Set end to 1790424000 or earlier." in error.detail


@pytest.mark.parametrize(
    ("available_from", "expected"),
    [
        (
            1502942400,
            "crypto:BTCUSDT has 1h candles from 2017-08-17T04:00:00Z (1502942400) "
            "to 2026-09-26T12:00:00Z (1790424000). Choose start and end within this period.",
        ),
        (
            None,
            "crypto:BTCUSDT has 1h candles up to 2026-09-26T12:00:00Z (1790424000). "
            "Choose start and end within this period.",
        ),
    ],
)
def test_period_out_of_range_without_the_request(available_from: int | None, expected: str) -> None:
    error = PeriodOutOfRange(BTC, Timeframe.H1, available_from, 1790424000)

    assert error.detail == expected


def test_too_many_candles() -> None:
    error = TooManyCandles(131040, 50000, "Use 5m or a larger timeframe.")

    assert (error.requested, error.maximum) == (131040, 50000)
    assert error.suggestion == "Use 5m or a larger timeframe."
    assert error.detail == (
        "Requested 131040 candles, the maximum is 50000. Use 5m or a larger timeframe."
    )


def test_source_unavailable() -> None:
    error = SourceUnavailable("binance", "Binance weight budget is spent.", retry_after=17)

    assert (error.source, error.retry_after) == ("binance", 17)
    assert error.detail == "Binance weight budget is spent."
    assert SourceUnavailable("alpaca", "down").retry_after is None


def test_data_integrity_error() -> None:
    assert DataIntegrityError("bad").source is None
    assert DataIntegrityError("bad", source="binance").source == "binance"

"""The engine is deterministic: the same input gives the same trades and series, down to the
bytes of their Parquet files, with both fills and with a stop and costs."""

import io
import random

import polars as pl
import pytest

from candlestack.engine import Settings, backtest

INPUT_SCHEMA = {
    "ts": pl.Int64,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "signal": pl.Float64,
}
ROWS = 1000
SEEDS = range(5)
SETTINGS = [
    Settings(fill="signal_close", stop_loss=0.02, fee_bps=5, slippage_bps=3),
    Settings(fill="next_open", stop_loss=0.02, fee_bps=5, slippage_bps=3),
]
IDS = ["signal_close", "next_open"]


def random_candles(rng: random.Random) -> pl.DataFrame:
    """A random walk of 30-minute candles that gaps between them, with a signal that changes on
    about a third of the rows; big enough moves for 2% stops to fire, at the open too."""
    rows = []
    price, signal = 100.0, 0
    for row in range(ROWS):
        open_ = price * (1 + rng.gauss(0, 0.01))
        close = open_ * (1 + rng.gauss(0, 0.02))
        high = max(open_, close) * (1 + abs(rng.gauss(0, 0.01)))
        low = min(open_, close) * (1 - abs(rng.gauss(0, 0.01)))
        if rng.random() < 0.3:
            signal = rng.choice((-1, 0, 1))
        rows.append((row * 1800, open_, high, low, close, float(signal)))
        price = close
    return pl.DataFrame(rows, schema=INPUT_SCHEMA, orient="row")


def parquet(frame: pl.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.write_parquet(buffer)
    return buffer.getvalue()


@pytest.mark.parametrize("settings", SETTINGS, ids=IDS)
@pytest.mark.parametrize("seed", SEEDS)
def test_the_same_input_gives_byte_identical_trades_and_series(
    seed: int, settings: Settings
) -> None:
    frame = random_candles(random.Random(seed))

    first = backtest(frame, settings)
    second = backtest(frame, settings)

    # The stops and costs took part: there is something to differ.
    assert {"stop", "gap"} <= set(first.trades["exit_reason"])
    assert first.trades.equals(second.trades)
    assert first.series.equals(second.series)
    assert parquet(first.trades) == parquet(second.trades)
    assert parquet(first.series) == parquet(second.series)


@pytest.mark.parametrize("settings", SETTINGS, ids=IDS)
def test_an_equal_input_built_anew_gives_byte_identical_trades_and_series(
    settings: Settings,
) -> None:
    first = backtest(random_candles(random.Random(0)), settings)
    second = backtest(random_candles(random.Random(0)), settings)

    assert parquet(first.trades) == parquet(second.trades)
    assert parquet(first.series) == parquet(second.series)

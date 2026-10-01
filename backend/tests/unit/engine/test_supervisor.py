"""The engine against the supervisor's own backtest: on his candles and predictions it makes his
trades. His data is not public, so these tests run only where ``CANDLESTACK_SUPERVISOR_DATA``
names a local copy of it, one folder per stock (the layout of issue #119)::

    <CANDLESTACK_SUPERVISOR_DATA>/AAPL/candles.parquet
                                      /predictions.parquet
                                      /trades.parquet

Never commit that data. Without the variable the tests are skipped, as in CI. From
``backend/`` in Git Bash (in PowerShell, set ``$env:CANDLESTACK_SUPERVISOR_DATA`` first)::

    CANDLESTACK_SUPERVISOR_DATA=/path/to/data uv run pytest tests/unit/engine/test_supervisor.py -v

Every stock folder found is checked (one without all three files is skipped, the reason says
which), and each stock, model, threshold and stop loss is a test of its own (10 models x 4
thresholds x 3 stop losses = 120 for AAPL).

What only his data needs stays here, not in the engine or signals: his candles and predictions
label a 30-minute candle by its close in ``unix`` seconds, his trades by its close in New York
time, and he leaves out the trade still open at the end of the data.
"""

import functools
import os
from pathlib import Path

import polars as pl
import pytest

from candlestack.engine import Settings, backtest
from candlestack.signals import align, relabel, threshold

DATA = os.environ.get("CANDLESTACK_SUPERVISOR_DATA", "")
ROOT = Path(DATA)
FILES = ("candles", "predictions", "trades")
HALF_HOUR = 1800  # his timeframe: the shift from his close labels to our open labels
LIMITS = (0.0, 0.01, 0.05, 0.1)
STOP_LOSSES = (0.05, 0.07, 0.1)
EXIT_REASONS = {0: "signal", 1: "stop", 2: "gap"}  # his operation_end_type
SIDES = {"LONG": 1, "SHORT": -1}  # his action_open
KEYS = ["open_ts", "close_ts", "side", "exit_reason"]

pytestmark = pytest.mark.skipif(
    not DATA, reason="CANDLESTACK_SUPERVISOR_DATA does not name the supervisor's data"
)


def stock_folders() -> list[str]:
    if not DATA or not ROOT.is_dir():
        return []
    return sorted(path.name for path in ROOT.iterdir() if path.is_dir())


def missing_files(stock: str) -> list[str]:
    return [f"{name}.parquet" for name in FILES if not (ROOT / stock / f"{name}.parquet").is_file()]


def models_of(stock: str) -> list[str]:
    return sorted(
        pl.read_parquet(ROOT / stock / "predictions.parquet", columns=["model"])["model"].unique()
    )


STOCKS = stock_folders()
COMPLETE = [stock for stock in STOCKS if not missing_files(stock)]
COMBINATIONS = [
    pytest.param(stock, model, limit, stop_loss, id=f"{stock}-{model}-limit{limit}-stop{stop_loss}")
    for stock in COMPLETE
    for model in models_of(stock)
    for limit in LIMITS
    for stop_loss in STOP_LOSSES
]


# The tests run stock by stock and model by model: the caches hold one of each, so the data of
# all stocks never sits in memory at once.
@functools.lru_cache(maxsize=1)
def candles(stock: str) -> pl.DataFrame:
    frame = pl.read_parquet(ROOT / stock / "candles.parquet").rename({"unix": "ts"})
    return relabel(frame, HALF_HOUR).select("ts", "open", "high", "low", "close")


@functools.lru_cache(maxsize=1)
def predictions(stock: str) -> pl.DataFrame:
    frame = pl.read_parquet(ROOT / stock / "predictions.parquet").rename({"unix": "ts"})
    return relabel(frame, HALF_HOUR).select("ts", "model", "prediction")


@functools.lru_cache(maxsize=1)
def aligned(stock: str, model: str) -> pl.DataFrame:
    # AAPL has no gaps. On a stock with one, the candle repeats the previous prediction (align's
    # rule), and his trades show whether he did the same.
    rows, _ = align(candles(stock), predictions(stock), model=model, strict=False)
    return rows


@functools.lru_cache(maxsize=1)
def his_trades(stock: str) -> pl.DataFrame:
    """His trades in the engine's terms: open and close as the open time of the candle in UTC
    seconds, side +1 or -1 and our exit reasons."""
    trades = pl.read_parquet(ROOT / stock / "trades.parquet")
    return trades.select(
        "model",
        "limit",
        "stop_loss",
        open_ts=pl.col("open_date").dt.epoch("s") - HALF_HOUR,
        close_ts=pl.col("close_date").dt.epoch("s") - HALF_HOUR,
        side=pl.col("action_open").replace_strict(SIDES, return_dtype=pl.Int8),
        exit_reason=pl.col("operation_end_type").replace_strict(
            EXIT_REASONS, return_dtype=pl.String
        ),
        trade_gain=pl.col("trade_gain"),
    ).sort("open_ts")


def test_aapl_is_among_the_stocks() -> None:
    incomplete = {stock: missing_files(stock) for stock in STOCKS if stock not in COMPLETE}
    assert "AAPL" in COMPLETE, (
        f"No complete AAPL folder in {ROOT}; stock folders found: {STOCKS or 'none'}, "
        f"missing files: {incomplete}"
    )


@pytest.mark.parametrize("stock", STOCKS)
def test_every_trade_of_his_is_checked(stock: str) -> None:
    if missing := missing_files(stock):
        pytest.skip(f"{stock} has no {', '.join(missing)}")
    checked = {
        (model, limit, stop)
        for model in models_of(stock)
        for limit in LIMITS
        for stop in STOP_LOSSES
    }
    his = set(his_trades(stock).select("model", "limit", "stop_loss").unique().rows())

    assert his - checked == set()


@pytest.mark.parametrize(("stock", "model", "limit", "stop_loss"), COMBINATIONS)
def test_the_engine_makes_his_trades(
    stock: str, model: str, limit: float, stop_loss: float
) -> None:
    rows = aligned(stock, model)
    frame = rows.with_columns(threshold(rows["prediction"], limit))
    result = backtest(frame, Settings(fill="signal_close", stop_loss=stop_loss))
    ours = result.trades.filter(pl.col("exit_reason") != "end")  # he leaves it out
    his = his_trades(stock).filter(
        (pl.col("model") == model) & (pl.col("limit") == limit) & (pl.col("stop_loss") == stop_loss)
    )

    # The same number of trades, each with his times, side and exit reason, and his return.
    assert ours.select(KEYS).rows() == his.select(KEYS).rows()
    assert (1 + ours["return"]).to_list() == pytest.approx(his["trade_gain"].to_list(), abs=1e-4)

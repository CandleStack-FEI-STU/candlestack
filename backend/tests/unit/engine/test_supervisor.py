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
which; a folder whose name starts with ``_`` holds no stock and is ignored), and each stock,
model, threshold and stop loss is a test of its own (10 models x 4 thresholds x 3 stop losses =
120 per stock).

What only his data needs stays here, not in the engine or signals: his candles and predictions
label a 30-minute candle by its close in ``unix`` seconds, his trades by its close in New York
time, and his candles mark the last candle of a session with ``end_bar`` 1.

His backtest leaves out two trades at the end of the data, and the check leaves them out of
ours too: the trade still open at the end, and the last trade when a stop or a gap closed it
and the signal did not change on its candle or later. Both are trades that no signal closed
before the data ran out.

Two more conventions of his make trades the engine does not copy. A combination whose first
different trade comes from one of them is marked xfail, with the convention, the stock, the
candle and the prices in the reason; any other difference fails:

- An intraday gap: a candle that opens beyond the stop level while the candle before it is of
  the same session. The engine exits at that open (``gap``); he exits at the stop level
  (``stop``). At the first candle of a session (an overnight gap) both exit at the open.
- A touch to the cent: the low (long) or high (short) of a candle equals the stop level within
  floating point, and the rounding decides whether it touched, so one side stops there and
  the other does not; or its open does, and one side exits at the open (``gap``), the other
  at the level (``stop``).
"""

import functools
import os
from datetime import UTC, datetime
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
TOUCH = 1e-9  # how close, relative to the stop level, a low or high counts as touching it

pytestmark = pytest.mark.skipif(
    not DATA, reason="CANDLESTACK_SUPERVISOR_DATA does not name the supervisor's data"
)


def stock_folders() -> list[str]:
    if not DATA or not ROOT.is_dir():
        return []
    return sorted(
        path.name for path in ROOT.iterdir() if path.is_dir() and not path.name.startswith("_")
    )


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
    return relabel(frame, HALF_HOUR).select("ts", "open", "high", "low", "close", "end_bar")


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


def as_he_lists(trades: pl.DataFrame, frame: pl.DataFrame) -> pl.DataFrame:
    """Our trades without the two he leaves out at the end of the data (see the module
    docstring)."""
    closed = trades.filter(pl.col("exit_reason") != "end")
    if closed.is_empty() or closed["exit_reason"][-1] not in ("stop", "gap"):
        return closed
    exit_row = frame["ts"].search_sorted(closed["close_ts"][-1])
    # The signals from the row before the exit on: a change among them followed the exit.
    if (frame["signal"][exit_row - 1 :].diff().drop_nulls() != 0).any():
        return closed
    return closed.head(-1)


def when(ts: int) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%d %H:%M UTC")


def known_difference(ours: pl.DataFrame, his: pl.DataFrame, frame: pl.DataFrame) -> str | None:
    """Names the convention of his that makes the first different trade, or ``None`` when
    neither does."""
    pairs = zip(ours.select(KEYS).rows(), his.select(KEYS).rows(), strict=False)
    first = next((i for i, (a, b) in enumerate(pairs) if a != b), None)
    if first is None:
        return None  # the same trades, one list longer: no convention explains that
    our, its = ours.row(first, named=True), his.row(first, named=True)
    if (our["open_ts"], our["side"]) != (its["open_ts"], its["side"]):
        return None
    # The candle where the first of the two trades ends; it is never the first row, as both
    # trades opened before it.
    row = frame["ts"].search_sorted(min(our["close_ts"], its["close_ts"]))
    exits = {
        who: trade["exit_reason"]
        for who, trade in (("we", our), ("he", its))
        if trade["close_ts"] == frame["ts"][row]
    }
    if not exits:
        return None  # his trade ends on a candle we do not have
    level, side = our["stop_price"], our["side"]
    return intraday_gap(exits, frame, row, level, side) or touch(exits, frame, row, level, side)


def intraday_gap(
    exits: dict[str, str], frame: pl.DataFrame, row: int, level: float, side: int
) -> str | None:
    """We exit at an open beyond the stop level inside a session, he at the level."""
    candle = frame.row(row, named=True)
    beyond = candle["open"] <= level if side > 0 else candle["open"] >= level
    if exits == {"we": "gap", "he": "stop"} and beyond and frame["end_bar"][row - 1] == 0:
        return (
            f"his intraday gap convention: on {when(candle['ts'])} the candle opens at "
            f"{candle['open']} beyond the stop level {level} inside the session; we exit at the "
            "open (gap), he at the level (stop)"
        )
    return None


def touch(
    exits: dict[str, str], frame: pl.DataFrame, row: int, level: float, side: int
) -> str | None:
    """A touch to the cent makes one side stop where the other does not, or stop at the level
    where the other exits at the open."""
    candle = frame.row(row, named=True)
    reasons = sorted(exits.values())
    if reasons == ["gap", "stop"]:
        name = "open"
        gaps = "we exit" if exits["we"] == "gap" else "he exits"
        how = f"{gaps} at the open (gap), the other at the level (stop)"
    elif reasons in (["stop"], ["signal", "stop"]):
        name = "low" if side > 0 else "high"
        stops = "we stop" if exits.get("we") == "stop" else "he stops"
        how = f"{stops} there, the other does not"
    else:
        return None
    if abs(candle[name] - level) > TOUCH * level:
        return None
    return (
        f"a touch to the cent: on {when(candle['ts'])} the {name} {candle[name]} equals the "
        f"stop level {level} within floating point; {how}"
    )


@pytest.mark.parametrize(("stock", "model", "limit", "stop_loss"), COMBINATIONS)
def test_the_engine_makes_his_trades(
    stock: str, model: str, limit: float, stop_loss: float
) -> None:
    rows = aligned(stock, model)
    frame = rows.with_columns(threshold(rows["prediction"], limit))
    result = backtest(frame, Settings(fill="signal_close", stop_loss=stop_loss))
    ours = as_he_lists(result.trades, frame)
    his = his_trades(stock).filter(
        (pl.col("model") == model) & (pl.col("limit") == limit) & (pl.col("stop_loss") == stop_loss)
    )
    if reason := known_difference(ours, his, frame):
        pytest.xfail(f"{stock}: {reason}")

    # The same number of trades, each with his times, side and exit reason, and his return.
    assert ours.select(KEYS).rows() == his.select(KEYS).rows()
    assert (1 + ours["return"]).to_list() == pytest.approx(his["trade_gain"].to_list(), abs=1e-4)

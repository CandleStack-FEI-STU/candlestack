"""The worked example of docs/engine.md, run: the numbers the document shows are the ones the
engine, the metrics, the signals and the command give. A change here goes into the document
too, and the other way round. Values are compared to the decimals the document prints."""

from pathlib import Path
from typing import Any

import polars as pl
import pytest

from candlestack.cli import main
from candlestack.engine import Result, Settings, backtest
from candlestack.metrics import stats
from candlestack.signals import long_only, threshold

PRINTED = 5e-7  # the document prints at least 6 decimals
START = 1_717_421_400  # 2024-06-03 13:30 UTC, the 09:30 open in New York
TS = [START + 1800 * row for row in range(5)]  # five 30-minute candles

CANDLES = pl.DataFrame(
    {
        "ts": TS,
        "open": [100.0, 100.0, 102.0, 99.0, 97.0],
        "high": [101.0, 102.0, 104.0, 99.5, 98.0],
        "low": [99.0, 99.5, 101.0, 96.0, 96.5],
        "close": [100.0, 101.0, 103.0, 97.0, 98.0],
    }
)
EXAMPLE = CANDLES.with_columns(signal=pl.Series([0.0, 1.0, 1.0, 1.0, 1.0]))
COSTS = {"stop_loss": 0.05, "fee_bps": 10}


def trade(
    signal_row, open_row, close_row, open_price, close_price, stop, reason, result, fees
) -> dict[str, Any]:
    return {
        "signal_ts": TS[signal_row],
        "open_ts": TS[open_row],
        "close_ts": TS[close_row],
        "side": 1,
        "open_price": open_price,
        "close_price": close_price,
        "stop_price": stop,
        "exit_reason": reason,
        "return": result,
        "fees": fees,
    }


def check(
    result: Result, trades: list[dict[str, Any]], position: list[float], equity: list[float]
) -> None:
    assert result.trades.rows(named=True) == [pytest.approx(row, abs=PRINTED) for row in trades]
    assert result.series["position"].to_list() == position
    assert result.series["equity"].to_list() == pytest.approx(equity, abs=PRINTED)


def test_signal_close_holds_the_long_to_the_end() -> None:
    check(
        backtest(EXAMPLE, Settings(fill="signal_close", **COSTS)),
        [trade(1, 1, 4, 101, 98, 95.95, "end", -0.031673, 0.001970)],
        position=[0, 1, 1, 1, 0],
        equity=[1, 0.999, 1.018802, 0.959396, 0.968327],
    )


def test_next_open_is_stopped_out_on_the_low() -> None:
    check(
        backtest(EXAMPLE, Settings(fill="next_open", **COSTS)),
        [trade(1, 2, 3, 102, 96.9, 96.9, "stop", -0.05195, 0.00195)],
        position=[0, 0, 1, 0, 0],
        equity=[1, 1, 1.008804, 0.94805, 0.94805],
    )


def test_slippage_moves_the_prices_and_the_stop_level() -> None:
    check(
        backtest(EXAMPLE, Settings(fill="next_open", slippage_bps=10, **COSTS)),
        [trade(1, 2, 3, 102.102, 96.8999031, 96.9969, "stop", -0.05289905, 0.00194905)],
        position=[0, 0, 1, 0, 0],
        equity=[1, 1, 1.007795, 0.947101, 0.947101],
    )


def test_the_statistics_of_the_signal_close_run() -> None:
    result = backtest(EXAMPLE, Settings(fill="signal_close", **COSTS))

    assert stats(result.trades, result.series, EXAMPLE) == pytest.approx(
        {
            "total_return": -0.031673,
            "max_drawdown": 0.058310,
            "sharpe": None,
            "sortino": None,
            "num_trades": 1,
            "win_rate": 0.0,
            "avg_trade_return": -0.031673,
            "best_trade_return": -0.031673,
            "worst_trade_return": -0.031673,
            "exposure": 0.6,
            "fees_paid": 0.001970,
            "buy_and_hold_return": -0.02,
        },
        abs=PRINTED,
    )


def test_threshold_and_long_only() -> None:
    signal = threshold(pl.Series([0.01, 0.3, -0.02, -0.08, 0.05]), 0.05)

    assert signal.to_list() == [0.0, 1.0, 0.0, -1.0, 1.0]
    assert long_only(signal).to_list() == [0.0, 1.0, 0.0, 0.0, 1.0]


def test_the_command_runs_the_example(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    CANDLES.write_parquet(tmp_path / "candles.parquet")
    pl.DataFrame({"ts": TS, "prediction": [0.01, 0.3, 0.2, 0.1, 0.4]}).write_parquet(
        tmp_path / "predictions.parquet"
    )
    out = tmp_path / "runs" / "example"

    code = main(
        [
            "run",
            "--candles",
            str(tmp_path / "candles.parquet"),
            "--predictions",
            str(tmp_path / "predictions.parquet"),
            "--threshold",
            "0.05",
            "--fill",
            "signal_close",
            "--stop-loss",
            "0.05",
            "--fee-bps",
            "10",
            "--out",
            str(out),
        ]
    )

    assert code == 0
    assert capsys.readouterr().out == (
        f"Wrote trades.parquet, series.parquet, stats.json and run.json to {out}\n"
        "  trades        1\n"
        "  win rate      0.00%\n"
        "  total return  -3.17%\n"
        "  max drawdown  5.83%\n"
        "  sharpe        n/a\n"
        "  buy and hold  -2.00%\n"
    )

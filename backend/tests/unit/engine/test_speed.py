"""How fast a backtest runs, both fills with a stop and costs, each the best of several runs:
the supervisor's test period of one stock (2,314 half-hour candles) in under 10 ms, a million
candles in under 2 s.

Run by hand, not in CI, where shared runners time badly: ``uv run pytest -m slow -s`` prints
the times for the pull request.
"""

import functools
import random
import sys
import time

import polars as pl
import pytest

from candlestack.engine import Settings, backtest

pytestmark = [
    pytest.mark.slow,
    # Coverage or a debugger slows every line it watches, so the times would say nothing.
    pytest.mark.skipif(
        sys.gettrace() is not None
        or sys.monitoring.get_tool(sys.monitoring.COVERAGE_ID) is not None,
        reason="a tracer (coverage, a debugger) is running",
    ),
]

SETTINGS = [
    Settings(fill="signal_close", stop_loss=0.02, fee_bps=5, slippage_bps=3),
    Settings(fill="next_open", stop_loss=0.02, fee_bps=5, slippage_bps=3),
]
IDS = ["signal_close", "next_open"]


@functools.cache
def random_candles(rows: int) -> pl.DataFrame:
    """A random walk of 30-minute candles that gaps between them, with a signal that changes on
    about a third of the rows; big enough moves for 2% stops to fire, at the open too."""
    rng = random.Random(rows)
    columns: dict[str, list[float]] = {name: [] for name in ("open", "high", "low", "close")}
    signals = []
    price, signal = 100.0, 0
    for _ in range(rows):
        open_ = price * (1 + rng.uniform(-0.01, 0.01))
        close = open_ * (1 + rng.uniform(-0.02, 0.02))
        columns["open"].append(open_)
        columns["high"].append(max(open_, close) * (1 + rng.uniform(0, 0.01)))
        columns["low"].append(min(open_, close) * (1 - rng.uniform(0, 0.01)))
        columns["close"].append(close)
        if rng.random() < 0.3:
            signal = rng.choice((-1, 0, 1))
        signals.append(float(signal))
        price = close
    return pl.DataFrame({"ts": pl.int_range(rows, eager=True) * 1800, **columns, "signal": signals})


def best_time(rows: int, settings: Settings, runs: int) -> float:
    frame = random_candles(rows)
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        result = backtest(frame, settings)
        times.append(time.perf_counter() - start)
        assert {"signal", "stop", "gap"} <= set(result.trades["exit_reason"])
    best = min(times)
    sys.stdout.write(
        f"\n{rows:,} candles, {settings.fill}: best of {runs} runs {best * 1000:.1f} ms "
        f"(slowest {max(times) * 1000:.1f} ms)\n"
    )
    return best


@pytest.mark.parametrize("settings", SETTINGS, ids=IDS)
def test_a_stock_test_period_runs_in_under_10_ms(settings: Settings) -> None:
    assert best_time(2_314, settings, runs=20) < 0.010


@pytest.mark.parametrize("settings", SETTINGS, ids=IDS)
def test_a_million_candles_run_in_under_2_s(settings: Settings) -> None:
    assert best_time(1_000_000, settings, runs=3) < 2.0

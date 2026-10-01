import json
import math
from datetime import UTC, datetime

import polars as pl
import pytest

from candlestack.metrics import drawdown, stats

# The engine's output and the candles, as the data contract defines them.
TRADES_SCHEMA = {
    "signal_ts": pl.Int64,
    "open_ts": pl.Int64,
    "close_ts": pl.Int64,
    "side": pl.Int8,
    "open_price": pl.Float64,
    "close_price": pl.Float64,
    "stop_price": pl.Float64,
    "exit_reason": pl.String,
    "return": pl.Float64,
    "fees": pl.Float64,
}
SERIES_SCHEMA = {"ts": pl.Int64, "signal": pl.Float64, "position": pl.Float64, "equity": pl.Float64}
CANDLES_SCHEMA = {
    "ts": pl.Int64,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
}
HOUR = 3600
NAMES = [
    "total_return",
    "max_drawdown",
    "sharpe",
    "sortino",
    "num_trades",
    "win_rate",
    "avg_trade_return",
    "best_trade_return",
    "worst_trade_return",
    "exposure",
    "fees_paid",
    "buy_and_hold_return",
]
SERIES_NAMES = ["total_return", "max_drawdown", "sharpe", "sortino", "exposure"]
TRADE_NAMES = ["win_rate", "avg_trade_return", "best_trade_return", "worst_trade_return"]


def utc(text: str) -> int:
    return int(datetime.fromisoformat(text).replace(tzinfo=UTC).timestamp())


def make_trades(*rows: tuple[float, float, str]) -> pl.DataFrame:
    """Closed trades with these ``(return, fees, exit_reason)``: one long trade per hour from
    2026-01-05 (stats reads only return and fees; the other columns are filler)."""
    start = utc("2026-01-05 14:00")
    return pl.DataFrame(
        [
            (
                start + i * HOUR,
                start + i * HOUR + 1800,
                start + i * HOUR + 3600,
                1,
                100.0,
                100.0 * (1 + result),
                None,
                reason,
                result,
                fees,
            )
            for i, (result, fees, reason) in enumerate(rows)
        ],
        schema=TRADES_SCHEMA,
        orient="row",
    )


def make_series(*rows: tuple[str, float, float]) -> pl.DataFrame:
    """A series from ``(UTC time, position, equity)``. Metrics only read the columns, so the
    numbers are picked for easy hand computation, not taken from a run of the engine."""
    return pl.DataFrame(
        [(utc(time), position, position, equity) for time, position, equity in rows],
        schema=SERIES_SCHEMA,
        orient="row",
    )


def make_candles(*rows: tuple[str, float]) -> pl.DataFrame:
    """Flat candles from ``(UTC time, close)``."""
    return pl.DataFrame(
        [(utc(time), close, close, close, close) for time, close in rows],
        schema=CANDLES_SCHEMA,
        orient="row",
    )


def candles_of(series: pl.DataFrame) -> pl.DataFrame:
    """A flat candle at 100 under each row of ``series``."""
    return series.select(
        "ts", *(pl.lit(100.0).alias(name) for name in ["open", "high", "low", "close"])
    )


def stats_of(series: pl.DataFrame) -> dict[str, float | int | None]:
    return stats(make_trades(), series, candles_of(series))


def assert_valid_json(result: dict[str, float | int | None]) -> None:
    json.dumps(result, allow_nan=False)  # raises on NaN and infinity


# Three UTC days of two candles each; the last one of a day ends it. Days end at 1.10, 0.99 and
# 1.089, so the daily returns are 0.1, -0.1 and 0.1 (the first from the starting 1.0, not from
# the first candle's 1.05): mean 1/30, std (ddof 1) 1/sqrt(75), downside deviation
# sqrt(0.01 / 3).
SERIES = make_series(
    ("2026-01-05 14:30", 1, 1.05),
    ("2026-01-05 20:30", 1, 1.10),
    ("2026-01-06 14:30", -1, 0.95),
    ("2026-01-06 20:30", 0, 0.99),
    ("2026-01-07 14:30", 1, 1.20),
    ("2026-01-07 20:30", 1, 1.089),
)
# A trade that returns exactly 0 is no win; the end trade counts.
TRADES = make_trades(
    (0.1, 0.001, "signal"),
    (-0.05, 0.001, "stop"),
    (0.0, 0.002, "signal"),
    (0.02, 0.001, "end"),
)
# Candles before and after the series do not count for buy and hold: 125 / 100 - 1.
CANDLES = make_candles(
    ("2026-01-02 20:30", 50.0),
    ("2026-01-05 14:30", 100.0),
    ("2026-01-05 20:30", 104.0),
    ("2026-01-06 14:30", 108.0),
    ("2026-01-06 20:30", 99.0),
    ("2026-01-07 14:30", 118.0),
    ("2026-01-07 20:30", 125.0),
    ("2026-01-08 14:30", 200.0),
)


# stats


def test_stats_of_a_run_match_the_hand_computed_values() -> None:
    result = stats(TRADES, SERIES, CANDLES)

    assert list(result) == NAMES
    assert result == {
        "total_return": pytest.approx(0.089),
        # Lowest point 0.95 under the peak 1.10: 1 - 0.95 / 1.10 = 3 / 22.
        "max_drawdown": pytest.approx(3 / 22),
        # (1/30) / (1/sqrt(75)) * sqrt(252) = sqrt(21)
        "sharpe": pytest.approx(math.sqrt(21)),
        # (1/30) / sqrt(0.01 / 3) * sqrt(252) = sqrt(84)
        "sortino": pytest.approx(math.sqrt(84)),
        "num_trades": 4,
        "win_rate": 0.5,
        "avg_trade_return": pytest.approx(0.0175),
        "best_trade_return": 0.1,
        "worst_trade_return": -0.05,
        # 5 of 6 candles close with a position, short ones included.
        "exposure": pytest.approx(5 / 6),
        "fees_paid": pytest.approx(0.005),
        "buy_and_hold_return": 0.25,
    }
    assert isinstance(result["num_trades"], int)


def test_periods_per_year_scales_sharpe_and_sortino() -> None:
    result = stats(TRADES, SERIES, CANDLES, periods_per_year=365)

    assert result["sharpe"] == pytest.approx(math.sqrt(21) * math.sqrt(365 / 252))
    assert result["sortino"] == pytest.approx(math.sqrt(84) * math.sqrt(365 / 252))


def test_a_day_is_a_utc_date() -> None:
    # One second apart, but two UTC dates: returns 0.1 and 1 / 1.1 - 1 = -1/11, mean 1/220,
    # std (1/10 + 1/11) / sqrt(2), downside deviation (1/11) / sqrt(2): Sharpe sqrt(14) / 7,
    # Sortino 3 * sqrt(14) / 10.
    series = make_series(("2026-01-05 23:59:59", 1, 1.1), ("2026-01-06 00:00:00", 0, 1.0))

    result = stats_of(series)

    assert result["sharpe"] == pytest.approx(math.sqrt(14) / 7)
    assert result["sortino"] == pytest.approx(3 * math.sqrt(14) / 10)


def test_max_drawdown_counts_a_loss_from_the_starting_capital() -> None:
    series = make_series(("2026-01-05 14:30", 1, 0.8), ("2026-01-05 15:00", 1, 0.9))

    assert stats_of(series)["max_drawdown"] == pytest.approx(0.2)


def test_max_drawdown_is_zero_while_equity_only_rises() -> None:
    series = make_series(("2026-01-05 14:30", 1, 1.0), ("2026-01-05 15:00", 1, 1.5))

    assert str(stats_of(series)["max_drawdown"]) == "0.0"  # not -0.0


def test_one_day_has_no_sharpe_or_sortino() -> None:
    series = make_series(
        ("2026-01-05 14:30", 1, 0.9), ("2026-01-05 15:00", 1, 1.2), ("2026-01-05 15:30", 0, 1.1)
    )

    result = stats_of(series)

    assert result["sharpe"] is None
    assert result["sortino"] is None
    assert result["total_return"] == pytest.approx(0.1)
    assert_valid_json(result)


def test_flat_equity_has_no_sharpe_or_sortino() -> None:
    series = make_series(
        ("2026-01-05 14:30", 0, 1.0), ("2026-01-06 14:30", 0, 1.0), ("2026-01-07 14:30", 0, 1.0)
    )

    result = stats_of(series)

    assert result["sharpe"] is None
    assert result["sortino"] is None
    assert result["total_return"] == 0
    assert result["max_drawdown"] == 0
    assert result["exposure"] == 0
    assert_valid_json(result)


def test_identical_daily_returns_have_no_sharpe() -> None:
    # 1.5 and 2.25 / 1.5: exactly 0.5 twice, so std is exactly 0; no losing day either.
    series = make_series(("2026-01-05 14:30", 1, 1.5), ("2026-01-06 14:30", 1, 2.25))

    result = stats_of(series)

    assert result["sharpe"] is None
    assert result["sortino"] is None
    assert result["total_return"] == 1.25
    assert_valid_json(result)


def test_without_a_losing_day_sortino_is_none() -> None:
    # Returns 0.1 and 1.32 / 1.1 - 1 = 0.2: mean 0.15, std 0.1 / sqrt(2).
    series = make_series(("2026-01-05 14:30", 1, 1.1), ("2026-01-06 14:30", 1, 1.32))

    result = stats_of(series)

    assert result["sharpe"] == pytest.approx(0.15 / (0.1 / math.sqrt(2)) * math.sqrt(252))
    assert result["sortino"] is None


def test_after_equity_reaches_zero_there_are_no_daily_returns() -> None:
    series = make_series(
        ("2026-01-05 14:30", -1, 0.0), ("2026-01-06 14:30", 0, 0.0), ("2026-01-07 14:30", 0, 0.0)
    )

    result = stats_of(series)

    assert result["sharpe"] is None
    assert result["sortino"] is None
    assert result["total_return"] == -1
    assert result["max_drawdown"] == 1
    assert_valid_json(result)


def test_without_trades_the_trade_statistics_are_none() -> None:
    result = stats(make_trades(), SERIES, CANDLES)

    assert result["num_trades"] == 0
    assert [result[name] for name in TRADE_NAMES] == [None] * len(TRADE_NAMES)
    assert result["fees_paid"] == 0
    assert result["total_return"] == pytest.approx(0.089)
    assert_valid_json(result)


def test_win_rate_counts_only_positive_returns() -> None:
    trades = make_trades((0.0, 0.0, "signal"), (-0.01, 0.0, "signal"), (0.0, 0.0, "end"))

    assert stats(trades, SERIES, CANDLES)["win_rate"] == 0


def test_an_empty_series_has_no_series_statistics() -> None:
    series = make_series()

    result = stats(make_trades(), series, CANDLES)

    assert [result[name] for name in SERIES_NAMES] == [None] * len(SERIES_NAMES)
    assert result["buy_and_hold_return"] is None
    assert result["num_trades"] == 0
    assert_valid_json(result)


def test_a_value_that_is_not_finite_is_none() -> None:
    candles = make_candles(("2026-01-05 14:30", 0.0), ("2026-01-07 20:30", 125.0))

    result = stats(TRADES, SERIES, candles)

    assert result["buy_and_hold_return"] is None  # 125 / 0 - 1
    assert_valid_json(result)


# drawdown


def test_drawdown_is_equity_under_its_running_peak() -> None:
    series = make_series(
        ("2026-01-05 14:30", 1, 0.9),
        ("2026-01-05 15:00", 1, 1.1),
        ("2026-01-05 15:30", 1, 0.99),
        ("2026-01-05 16:00", 1, 1.21),
    )

    result = drawdown(series)

    assert result.name == "drawdown"
    assert result.dtype == pl.Float64
    # Peaks 1.0 (the starting capital), 1.1, 1.1, 1.21.
    assert result.to_list() == pytest.approx([-0.1, 0.0, -0.1, 0.0])


def test_drawdown_of_an_empty_series_is_empty() -> None:
    result = drawdown(make_series())

    assert result.len() == 0
    assert result.dtype == pl.Float64

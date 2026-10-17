import math
from datetime import date

import pytest
from pydantic import ValidationError

from candlestack.experiments.models import Backtest
from candlestack.experiments.schemas import (
    EQUITY_POINTS,
    BacktestSetup,
    BacktestUpdate,
    EquitySeries,
)

SETUP = {
    "timeframe": "30m",
    "period_start": "2021-01-04",
    "period_end": "2024-12-31",
    "direction": "long",
    "threshold": 0.05,
    "stop_loss_pct": 7,
    "fees_pct": 0.1,
    "slippage_pct": 0.02,
    "benchmark": "bh",
}


def test_a_setup_reads_what_settings_save() -> None:
    setup = BacktestSetup.model_validate(SETUP)

    assert setup.period_start == date(2021, 1, 4)
    assert setup.model_dump(mode="json") == SETUP


@pytest.mark.parametrize(
    "change",
    [
        {"period_end": "2021-01-04"},
        {"timeframe": "2h"},
        {"direction": "short"},
        {"threshold": 0.6},
        {"stop_loss_pct": 0},
        {"fees_pct": -1},
        {"slippage_pct": 6},
        {"benchmark": "VTI"},
    ],
)
def test_a_setup_is_checked(change: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        BacktestSetup.model_validate({**SETUP, **change})


def test_a_backtest_keeps_a_checked_equity_series() -> None:
    backtest = Backtest()

    backtest.set_equity((0.0, 0.1), [0, -0.05])

    assert backtest.equity == {"strategy": [0.0, 0.1], "benchmark": [0.0, -0.05]}


@pytest.mark.parametrize(
    ("strategy", "benchmark"),
    [
        ([0.0, 0.1], [0.0, 0.1, 0.2]),
        ([0.0] * 61, [0.0] * 61),
        ([0.0], [0.0]),
        ([0.0, math.nan], [0.0, 0.1]),
        ([0.0, 0.1], [0.0, math.inf]),
        ([0.0, -math.inf], [0.0, 0.1]),
        ([0.0, "x"], [0.0, 0.1]),
    ],
    ids=["unequal", "too-long", "too-short", "nan", "inf", "minus-inf", "text"],
)
def test_an_equity_series_is_checked(strategy: list[object], benchmark: list[object]) -> None:
    backtest = Backtest()

    with pytest.raises(ValidationError):
        backtest.set_equity(strategy, benchmark)  # ty: ignore[invalid-argument-type]
    assert backtest.equity is None


def test_sixty_points_fit() -> None:
    series = EquitySeries(strategy=[0.0] * 60, benchmark=[0.0] * 60)

    assert len(series.strategy) == EQUITY_POINTS == 60


def test_a_star_has_only_the_star() -> None:
    assert BacktestUpdate.model_validate({"starred": False}).starred is False
    with pytest.raises(ValidationError):
        BacktestUpdate.model_validate({"starred": True, "name": "x"})

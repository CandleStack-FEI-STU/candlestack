from datetime import date

import pytest
from pydantic import ValidationError

from candlestack.experiments.schemas import BacktestSetup, BacktestUpdate

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


def test_a_star_has_only_the_star() -> None:
    assert BacktestUpdate.model_validate({"starred": False}).starred is False
    with pytest.raises(ValidationError):
        BacktestUpdate.model_validate({"starred": True, "name": "x"})

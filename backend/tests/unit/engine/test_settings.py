from typing import Any

import pytest
from pydantic import ValidationError

from candlestack.engine import Settings


def test_defaults_fill_at_the_next_open_without_stop_or_costs() -> None:
    settings = Settings()

    assert settings.fill == "next_open"
    assert settings.stop_loss is None
    assert settings.fee_bps == 0
    assert settings.slippage_bps == 0


def test_valid_settings_are_kept() -> None:
    settings = Settings(fill="signal_close", stop_loss=0.05, fee_bps=5, slippage_bps=2.5)

    assert settings.model_dump() == {
        "fill": "signal_close",
        "stop_loss": 0.05,
        "fee_bps": 5.0,
        "slippage_bps": 2.5,
    }


@pytest.mark.parametrize(
    "fields",
    [
        {"fill": "close"},
        {"stop_loss": 0},
        {"stop_loss": 1},
        {"stop_loss": -0.05},
        {"stop_loss": float("nan")},
        {"fee_bps": -1},
        {"fee_bps": float("inf")},
        {"slippage_bps": -0.5},
        {"slippage_bps": float("nan")},
        {"capital": 1000},
    ],
)
def test_invalid_settings_are_rejected(fields: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Settings(**fields)


def test_settings_are_frozen() -> None:
    settings = Settings()

    with pytest.raises(ValidationError):
        settings.fee_bps = 5  # ty: ignore[invalid-assignment]

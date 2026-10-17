"""The bodies of Settings: what they accept and their defaults."""

from datetime import date

import pytest
from pydantic import BaseModel, ValidationError

from candlestack.accounts.schemas import (
    Appearance,
    AppearanceUpdate,
    BacktestDefaults,
    BacktestDefaultsIn,
    MeUpdate,
)


def test_a_display_name_is_stripped() -> None:
    assert MeUpdate(display_name="\t Ada King \n").display_name == "Ada King"


@pytest.mark.parametrize("name", ["", "   ", "A" * 81, " " + "A" * 81])
def test_a_display_name_needs_1_to_80_characters(name: str) -> None:
    with pytest.raises(ValidationError):
        MeUpdate(display_name=name)


def test_80_characters_with_spaces_around_fit() -> None:
    assert MeUpdate(display_name=f"  {'A' * 80}  ").display_name == "A" * 80


def test_the_defaults_are_valid() -> None:
    assert BacktestDefaults().period_start < BacktestDefaults().period_end
    assert Appearance().model_dump(mode="json") == {
        "theme": "dark",
        "time_zone": "ny",
        "date_format": "dmy",
        "time_format": "24",
        "reduce_motion": False,
    }


@pytest.mark.parametrize("end", [date(2022, 5, 1), date(2022, 4, 30)])
def test_a_period_must_move_forward(end: date) -> None:
    with pytest.raises(ValidationError, match="period_start must be before period_end"):
        BacktestDefaults(period_start=date(2022, 5, 1), period_end=end)


@pytest.mark.parametrize("threshold", [0.0, 0.07, 0.29, 0.5])
def test_thresholds_in_steps_of_a_hundredth(threshold: float) -> None:
    assert BacktestDefaults(threshold=threshold).threshold == threshold


def test_saved_backtest_defaults_need_every_field() -> None:
    saved = BacktestDefaults().model_dump()

    assert BacktestDefaultsIn.model_validate(saved).model_dump() == saved
    for name in saved:
        with pytest.raises(ValidationError, match="Field required"):
            BacktestDefaultsIn.model_validate({k: v for k, v in saved.items() if k != name})


def test_saved_backtest_defaults_are_checked_like_the_read_ones() -> None:
    saved = BacktestDefaults().model_dump()

    with pytest.raises(ValidationError, match="period_start must be before period_end"):
        BacktestDefaultsIn.model_validate({**saved, "period_end": saved["period_start"]})
    with pytest.raises(ValidationError, match="less than or equal to 20"):
        BacktestDefaultsIn.model_validate({**saved, "stop_loss_pct": 21})


@pytest.mark.parametrize(
    ("model", "body"),
    [
        (MeUpdate, {"display_name": "Ada", "email": "eve@example.com"}),
        (BacktestDefaultsIn, {**BacktestDefaults().model_dump(), "stop_loss": 5}),
        (AppearanceUpdate, {"theme": "light", "colour": "red"}),
    ],
)
def test_a_request_body_with_an_unknown_field_is_refused(
    model: type[BaseModel], body: dict[str, object]
) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model.model_validate(body)


def test_a_saved_document_with_a_retired_field_still_reads() -> None:
    assert BacktestDefaults.model_validate({"retired_setting": 1}) == BacktestDefaults()

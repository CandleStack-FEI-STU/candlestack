import math
import random
from collections.abc import Callable

import polars as pl
import pytest

from candlestack.signals import confirm, ema, hysteresis, long_only, threshold

ROWS = 60
SEEDS = range(20)


def floats(values: list[float], dtype: type[pl.DataType] = pl.Float64) -> pl.Series:
    return pl.Series("prediction", values, dtype=dtype)


def random_predictions(rng: random.Random, limit: float = 0.05) -> pl.Series:
    """Random predictions that often sit exactly on a limit, on 0 or on -0.0: the edges of the
    rules, which a plain Gaussian would never hit."""
    edges = [limit, -limit, limit / 2, -limit / 2, 0.0, -0.0, 2 * limit, -2 * limit]
    values = [
        rng.choice(edges) if rng.random() < 0.5 else rng.gauss(0, 2 * limit) for _ in range(ROWS)
    ]
    return floats(values)


# ema


def test_ema_is_the_recursive_average_from_the_first_prediction() -> None:
    # alpha = 2 / (3 + 1) = 0.5: each value is half the prediction and half the previous value.
    result = ema(floats([1.0, 3.0, 3.0, -1.0]), 3)

    assert result.name == "prediction"
    assert result.dtype == pl.Float64
    assert result.to_list() == [1.0, 2.0, 2.5, 0.75]


def test_ema_of_span_1_is_the_predictions_as_float64() -> None:
    result = ema(floats([0.2, -0.2, 0.0], dtype=pl.Float32), 1)

    assert result.dtype == pl.Float64
    assert result.to_list() == floats([0.2, -0.2, 0.0], dtype=pl.Float32).to_list()


def test_ema_matches_the_formula_on_random_predictions() -> None:
    rng = random.Random(0)
    values = [rng.gauss(0, 1) for _ in range(ROWS)]
    span = 10
    alpha = 2 / (span + 1)
    expected = [values[0]]
    for value in values[1:]:
        expected.append(alpha * value + (1 - alpha) * expected[-1])

    assert ema(floats(values), span).to_list() == expected


def test_ema_keeps_the_name_and_takes_integer_predictions() -> None:
    result = ema(pl.Series("p", [2, 4, 4], dtype=pl.Int64), 3)

    assert result.name == "p"
    assert result.to_list() == [2.0, 3.0, 3.5]


def test_ema_gives_a_plain_zero() -> None:
    result = ema(floats([-0.0, -0.0, 0.0]), 3).to_list()

    assert [math.copysign(1.0, value) for value in result] == [1.0, 1.0, 1.0]


def test_ema_of_no_predictions_is_empty() -> None:
    result = ema(floats([]), 5)

    assert result.dtype == pl.Float64
    assert result.is_empty()


@pytest.mark.parametrize("span", [0, -1])
def test_ema_rejects_a_span_under_1(span: int) -> None:
    with pytest.raises(ValueError, match="span must be 1 or more"):
        ema(floats([0.1]), span)


@pytest.mark.parametrize("span", [True, 2.0, "3"])
def test_ema_rejects_a_span_that_is_not_an_int(span: object) -> None:
    with pytest.raises(ValueError, match="span must be an int"):
        ema(floats([0.1]), span)  # ty: ignore[invalid-argument-type]


@pytest.mark.parametrize("values", [[0.1, None], [0.1, math.nan]])
def test_ema_rejects_a_missing_or_nan_prediction(values: list[float | None]) -> None:
    with pytest.raises(ValueError, match="A prediction is missing or NaN"):
        ema(pl.Series(values, dtype=pl.Float64), 3)


def test_ema_rejects_predictions_that_are_not_numbers() -> None:
    with pytest.raises(ValueError, match="Predictions must be numbers, not String"):
        ema(pl.Series(["0.1"]), 3)


@pytest.mark.parametrize("value", [math.inf, -math.inf])
def test_ema_rejects_an_infinite_prediction(value: float) -> None:
    # One infinite prediction would make every average after it inf or NaN.
    with pytest.raises(ValueError, match="A prediction is infinite"):
        ema(floats([0.1, value]), 1)


# hysteresis


def test_hysteresis_keeps_a_position_between_the_limits() -> None:
    # Enter at 0.1, exit under 0.05: the position opens at 0.1, holds through 0.06 and 0.05,
    # closes at 0.04 and does not reopen at 0.06.
    result = hysteresis(
        floats([0.06, 0.1, 0.06, 0.05, 0.04, 0.06, -0.1, -0.05, -0.04, 0.1]), 0.1, 0.05
    )

    assert result.name == "signal"
    assert result.dtype == pl.Float64
    assert result.to_list() == [0.0, 1.0, 1.0, 1.0, 0.0, 0.0, -1.0, -1.0, 0.0, 1.0]


def test_hysteresis_turns_around_only_at_the_enter_limit() -> None:
    # From long, -0.06 is not enough to go short (exit is for staying, enter for opening),
    # so the position closes; -0.1 opens the short.
    result = hysteresis(floats([0.1, -0.06, -0.1, 0.06, 0.1]), 0.1, 0.05)

    assert result.to_list() == [1.0, 0.0, -1.0, 0.0, 1.0]


def test_hysteresis_with_exit_0_holds_until_the_sign_turns() -> None:
    result = hysteresis(floats([0.1, 0.001, 0.0, -0.001, -0.1, 0.0]), 0.1, 0.0)

    assert result.to_list() == [1.0, 1.0, 0.0, 0.0, -1.0, 0.0]


def test_hysteresis_gives_a_plain_zero_and_compares_in_float64() -> None:
    # float32(0.7) is below 0.7 in float64, as in threshold.
    result = hysteresis(floats([0.7, -0.0, 0.0], dtype=pl.Float32), 0.7, 0.7)

    assert result.to_list() == [0.0, 0.0, 0.0]
    assert [math.copysign(1.0, value) for value in result] == [1.0, 1.0, 1.0]


def test_hysteresis_of_no_predictions_is_an_empty_signal() -> None:
    result = hysteresis(floats([]), 0.1, 0.05)

    assert result.dtype == pl.Float64
    assert result.is_empty()


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("limit", [0.0, 0.05, 0.1])
def test_hysteresis_with_one_limit_is_threshold(seed: int, limit: float) -> None:
    predictions = random_predictions(random.Random(seed), limit or 0.05)

    assert hysteresis(predictions, limit, limit).equals(threshold(predictions, limit))


@pytest.mark.parametrize(
    ("enter", "exit_"),
    [
        (0.05, 0.1),
        (0.1, -0.01),
        (-0.1, -0.2),
        (math.nan, 0.05),
        (0.1, math.nan),
        (math.inf, 0.05),
        (math.inf, math.inf),
    ],
)
def test_hysteresis_rejects_limits_that_are_not_finite_with_0_exit_enter(
    enter: float, exit_: float
) -> None:
    with pytest.raises(ValueError, match="enter and exit must be finite with 0 <= exit <= enter"):
        hysteresis(floats([0.1]), enter, exit_)


@pytest.mark.parametrize("values", [[0.1, None], [0.1, math.nan]])
def test_hysteresis_rejects_a_missing_or_nan_prediction(values: list[float | None]) -> None:
    with pytest.raises(ValueError, match="A prediction is missing or NaN"):
        hysteresis(pl.Series(values, dtype=pl.Float64), 0.1, 0.05)


def test_hysteresis_rejects_predictions_that_are_not_numbers() -> None:
    with pytest.raises(ValueError, match="Predictions must be numbers, not String"):
        hysteresis(pl.Series(["0.1"]), 0.1, 0.05)


# confirm


def test_confirm_counts_a_value_once_it_has_held_for_the_candles() -> None:
    signal = pl.Series("signal", [0.0, 1.0, 1.0, 1.0, -1.0, -1.0, 0.0, 0.0, 0.0, 1.0])

    result = confirm(signal, 3)

    assert result.name == "signal"
    assert result.dtype == pl.Float64
    assert result.to_list() == [0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0]


def test_confirm_counts_the_first_row_at_once() -> None:
    # The engine never trades on its first row, so nothing is confirmed early.
    result = confirm(pl.Series("signal", [1.0, 1.0, 0.0, 0.0]), 2)

    assert result.to_list() == [1.0, 1.0, 1.0, 0.0]


def test_confirm_with_1_candle_is_the_signal_as_float64() -> None:
    result = confirm(pl.Series("signal", [1, -1, 0], dtype=pl.Int8), 1)

    assert result.dtype == pl.Float64
    assert result.to_list() == [1.0, -1.0, 0.0]


def test_confirm_takes_any_finite_values_and_keeps_the_name() -> None:
    result = confirm(pl.Series("weight", [0.5, 0.25, 0.25, 0.75, 0.5, 0.5]), 2)

    assert result.name == "weight"
    assert result.to_list() == [0.5, 0.5, 0.25, 0.25, 0.25, 0.5]


def test_confirm_starts_a_new_count_on_every_change() -> None:
    # 1 never holds for two rows, so it never counts.
    result = confirm(pl.Series("signal", [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]), 2)

    assert result.to_list() == [0.0] * 6


def test_confirm_gives_a_plain_zero() -> None:
    result = confirm(pl.Series("signal", [-0.0, -0.0, 1.0]), 2).to_list()

    assert [math.copysign(1.0, value) for value in result] == [1.0, 1.0, 1.0]


def test_confirm_of_no_signal_is_empty() -> None:
    result = confirm(pl.Series("signal", [], dtype=pl.Float64), 3)

    assert result.dtype == pl.Float64
    assert result.is_empty()


@pytest.mark.parametrize("candles", [0, -2])
def test_confirm_rejects_candles_under_1(candles: int) -> None:
    with pytest.raises(ValueError, match="candles must be 1 or more"):
        confirm(pl.Series("signal", [1.0]), candles)


@pytest.mark.parametrize("candles", [False, 2.0, "3"])
def test_confirm_rejects_candles_that_are_not_an_int(candles: object) -> None:
    with pytest.raises(ValueError, match="candles must be an int"):
        confirm(pl.Series("signal", [1.0]), candles)  # ty: ignore[invalid-argument-type]


@pytest.mark.parametrize("values", [[1.0, None], [1.0, math.nan]])
def test_confirm_rejects_a_missing_or_nan_signal_value(values: list[float | None]) -> None:
    with pytest.raises(ValueError, match="A signal value is missing or NaN"):
        confirm(pl.Series(values, dtype=pl.Float64), 2)


def test_confirm_rejects_a_signal_that_is_not_numbers() -> None:
    with pytest.raises(ValueError, match="Signal values must be numbers, not String"):
        confirm(pl.Series(["1.0"]), 2)


# The example of docs/engine.md, section "Signals"


def test_the_doc_example_of_the_post_processing_order() -> None:
    predictions = floats([0.0, 0.2, 0.2, -0.2, -0.2, -0.2])

    smoothed = ema(predictions, 3)
    raw = threshold(smoothed, 0.05)
    signal = long_only(raw)
    confirmed = confirm(signal, 2)

    assert smoothed.to_list() == pytest.approx([0.0, 0.1, 0.15, -0.025, -0.1125, -0.15625])
    assert raw.to_list() == [0.0, 1.0, 1.0, 0.0, -1.0, -1.0]
    assert signal.to_list() == [0.0, 1.0, 1.0, 0.0, 0.0, 0.0]
    # The long opens one row late and closes one row late.
    assert confirmed.to_list() == [0.0, 0.0, 1.0, 1.0, 0.0, 0.0]


# No look-ahead: the values after a row never change the output up to it.

FILTERS: list[Callable[[pl.Series], pl.Series]] = [
    lambda p: ema(p, 5),
    lambda p: hysteresis(p, 0.1, 0.05),
    lambda p: confirm(threshold(p, 0.05), 3),
]


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("apply", FILTERS, ids=["ema", "hysteresis", "confirm"])
def test_values_after_a_row_change_nothing_up_to_it(
    seed: int, apply: Callable[[pl.Series], pl.Series]
) -> None:
    rng = random.Random(seed)
    predictions = random_predictions(rng, 0.1)
    full = apply(predictions)

    for row in rng.sample(range(ROWS - 1), 5):
        changed = pl.concat(
            [predictions.head(row + 1), random_predictions(rng, 0.1).slice(row + 1)]
        )

        result = apply(changed)

        assert result.head(row + 1).equals(full.head(row + 1))

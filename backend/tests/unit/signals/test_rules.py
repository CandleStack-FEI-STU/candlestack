import math

import polars as pl
import pytest

from candlestack.signals import long_only, threshold


def signal(values: list[float], limit: float, dtype: type[pl.DataType] = pl.Float64) -> list[float]:
    return threshold(pl.Series(values, dtype=dtype), limit).to_list()


# threshold


@pytest.mark.parametrize(
    ("p", "limit", "expected"),
    [
        (0.05, 0.05, 1.0),
        (0.3, 0.05, 1.0),
        (0.049, 0.05, 0.0),
        (-0.049, 0.05, 0.0),
        (-0.05, 0.05, -1.0),
        (-0.3, 0.05, -1.0),
        (0.0, 0.05, 0.0),
        (0.0, 0.0, 0.0),
        (-0.0, 0.0, 0.0),
        (1e-12, 0.0, 1.0),
        (-1e-12, 0.0, -1.0),
        (math.inf, 0.05, 1.0),
        (-math.inf, 0.05, -1.0),
        (1e9, math.inf, 0.0),
    ],
)
def test_threshold(p: float, limit: float, expected: float) -> None:
    assert signal([p], limit) == [expected]


def test_threshold_gives_a_plain_zero_for_a_zero_prediction() -> None:
    # sign(-0.0) would be -0.0: equal to 0.0, but printed and stored as "-0.0".
    result = signal([0.0, -0.0], 0.0)

    assert [math.copysign(1.0, value) for value in result] == [1.0, 1.0]


def test_threshold_returns_a_float64_signal() -> None:
    result = threshold(pl.Series("prediction", [0.2, -0.2, 0.0], dtype=pl.Float32), 0.1)

    assert result.name == "signal"
    assert result.dtype == pl.Float64
    assert result.to_list() == [1.0, -1.0, 0.0]


def test_threshold_compares_float32_predictions_in_float64() -> None:
    # 0.7 has no exact float32: float32(0.7) is 0.699999988... A prediction of that value is
    # exactly at a limit of that value, but below the limit 0.7, which a comparison in float32
    # would round to the same float32 and call equal.
    float32_limit = pl.Series([0.7], dtype=pl.Float32).item()

    assert signal([0.7, -0.7], float32_limit, pl.Float32) == [1.0, -1.0]
    assert signal([0.7, -0.7], 0.7, pl.Float32) == [0.0, 0.0]


def test_threshold_takes_integer_predictions() -> None:
    assert signal([2, -2, 0], 1, pl.Int64) == [1.0, -1.0, 0.0]


def test_threshold_of_no_predictions_is_an_empty_signal() -> None:
    result = threshold(pl.Series([], dtype=pl.Float64), 0.1)

    assert result.dtype == pl.Float64
    assert result.is_empty()


@pytest.mark.parametrize("limit", [-0.01, math.nan])
def test_threshold_rejects_a_negative_or_nan_limit(limit: float) -> None:
    with pytest.raises(ValueError, match="limit must be 0 or more"):
        threshold(pl.Series([0.1]), limit)


@pytest.mark.parametrize("values", [[0.1, None], [0.1, math.nan]])
def test_threshold_rejects_a_missing_or_nan_prediction(values: list[float | None]) -> None:
    with pytest.raises(ValueError, match="A prediction is missing or NaN"):
        threshold(pl.Series(values, dtype=pl.Float64), 0.1)


def test_threshold_rejects_predictions_that_are_not_numbers() -> None:
    with pytest.raises(ValueError, match="Predictions must be numbers, not String"):
        threshold(pl.Series(["0.1"]), 0.1)


# long_only


def test_long_only_turns_short_positions_into_none() -> None:
    result = long_only(pl.Series("signal", [-1.0, 0.0, 1.0, -0.5, 0.5]))

    assert result.name == "signal"
    assert result.dtype == pl.Float64
    assert result.to_list() == [0.0, 0.0, 1.0, 0.0, 0.5]


def test_long_only_makes_an_integer_signal_float64() -> None:
    result = long_only(pl.Series("signal", [-1, 0, 1], dtype=pl.Int8))

    assert result.dtype == pl.Float64
    assert result.to_list() == [0.0, 0.0, 1.0]

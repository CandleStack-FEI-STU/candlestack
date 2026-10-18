import math
import random
import statistics
from collections.abc import Callable

import polars as pl
import pytest

from candlestack.signals import rank, threshold, zscore

ROWS = 80
SEEDS = range(10)
WINDOWS = [2, 3, 7, 50]
Calibration = Callable[[pl.Series, int], pl.Series]


def zscores(values: list[float], window: int) -> list[float]:
    return zscore(pl.Series(values, dtype=pl.Float64), window).to_list()


def ranks(values: list[float], window: int) -> list[float]:
    return rank(pl.Series(values, dtype=pl.Float64), window).to_list()


def random_predictions(rng: random.Random, rows: int = ROWS) -> pl.Series:
    """Predictions on the supervisor's scale, a fifth of them from a few repeated values so
    that windows hold ties and, now and then, equal predictions only."""
    values = [
        rng.choice((0.1, -0.1, 0.0)) if rng.random() < 0.2 else rng.gauss(0, 0.4)
        for _ in range(rows)
    ]
    return pl.Series("prediction", values)


def slow_zscore(values: list[float], window: int) -> list[float]:
    """The definition row by row: the window ending at t, p[t] included, sample std."""
    out = []
    for t, p in enumerate(values):
        if t < window - 1:
            out.append(0.0)
            continue
        own = values[t - window + 1 : t + 1]
        std = statistics.stdev(own)
        out.append((p - statistics.fmean(own)) / std if std > 0 else 0.0)
    return out


def slow_rank(values: list[float], window: int) -> list[float]:
    """The definition row by row: p[t] against the other window-1 predictions before it."""
    out = []
    for t, p in enumerate(values):
        if t < window - 1:
            out.append(0.0)
            continue
        others = values[t - window + 1 : t]
        below = sum(1 for other in others if other < p)
        equal = sum(1 for other in others if other == p)
        # 2r - 1 with r = (below + equal / 2) / (window - 1), rounded once.
        out.append((2 * below + equal - (window - 1)) / (window - 1))
    return out


# zscore


def test_zscore_measures_each_prediction_in_standard_deviations_of_its_window() -> None:
    # Every window of three consecutive integers has mean p - 1 and sample std 1.
    assert zscores([1.0, 2.0, 3.0, 4.0, 5.0], 3) == [0.0, 0.0, 1.0, 1.0, 1.0]


def test_zscore_includes_the_prediction_in_its_own_window() -> None:
    # The window of the last row is [1, 3]: mean 2, sample std sqrt(2).
    result = zscores([1.0, 3.0], 2)

    assert result[0] == 0.0
    assert result[1] == pytest.approx(1 / math.sqrt(2))


def test_zscore_feeds_threshold_as_one_standard_deviation() -> None:
    # 3 is one standard deviation above the mean of [1, 2, 3], 6 is 1.12 above the mean of
    # [2, 3, 6], and 5 is 0.22 above the mean of [3, 6, 5].
    z = zscore(pl.Series("prediction", [1.0, 2.0, 3.0, 6.0, 5.0]), 3)

    assert threshold(z, 1.0).to_list() == [0.0, 0.0, 1.0, 1.0, 0.0]


def test_zscore_is_flat_before_the_first_full_window_and_on_a_window_without_spread() -> None:
    assert zscores([5.0, 5.0, 5.0, 5.0], 3) == [0.0, 0.0, 0.0, 0.0]

    # Once the window is 0.7 three times the std is exactly 0, even after other values.
    result = zscores([0.1, 0.3, 0.7, 0.7, 0.7, 0.7], 3)

    assert result[:2] == [0.0, 0.0]
    assert result[2] == pytest.approx(1.091, abs=0.001)
    assert result[3] == pytest.approx(1 / math.sqrt(3))
    assert result[4:] == [0.0, 0.0]


def test_zscore_of_fewer_predictions_than_the_window_is_flat() -> None:
    assert zscores([0.1, 0.2, 0.3], 4) == [0.0, 0.0, 0.0]


@pytest.mark.parametrize("window", [2, 3, 10])
def test_zscore_is_flat_on_a_window_whose_spread_is_only_rounding(window: int) -> None:
    # The rolling mean carries about 1e-10 of rounding from the large predictions forward,
    # while the std of the 0.3 ± 1 ulp stretch is about 4e-17: without the scale check the
    # quotient reached 1.6e7, while a sample z-score never exceeds (window - 1) / sqrt(window).
    rng = random.Random(0)
    ulps = [0.3, math.nextafter(0.3, 1.0), math.nextafter(math.nextafter(0.3, 1.0), 1.0)]
    values = [rng.gauss(0, 1e6) for _ in range(3000)] + [ulps[i % 3] for i in range(30)]

    result = zscores(values, window)

    assert result[3000 + window - 1 :] == [0.0] * (30 - window + 1)
    assert max(map(abs, result)) <= (window - 1) / math.sqrt(window)


def test_zscore_gives_a_plain_zero() -> None:
    # Rows 2 and 5 are at the mean 0.0 of their window: -0.0 - 0.0 is -0.0, and dividing by the
    # std would keep its sign.
    result = zscores([1.0, -1.0, -0.0, 1.0, -1.0, 0.0], 3)

    assert (result[2], result[5]) == (0.0, 0.0)
    assert [math.copysign(1.0, value) for value in (result[2], result[5])] == [1.0, 1.0]


def test_zscore_keeps_the_name_and_returns_float64() -> None:
    result = zscore(pl.Series("prediction", [1, 2, 3], dtype=pl.Int64), 3)

    assert result.name == "prediction"
    assert result.dtype == pl.Float64
    assert result.to_list() == [0.0, 0.0, 1.0]


# rank


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([1.0, 2.0, 3.0], 1.0),
        ([3.0, 2.0, 1.0], -1.0),
        ([1.0, 3.0, 2.0], 0.0),
        ([2.0, 2.0, 2.0], 0.0),
        ([1.0, 2.0, 2.0], 0.5),
        ([2.0, 1.0, 2.0], 0.5),
        ([2.0, 3.0, 2.0], -0.5),
    ],
)
def test_rank_places_the_last_prediction_among_its_window(
    values: list[float], expected: float
) -> None:
    assert ranks(values, 3) == [0.0, 0.0, expected]


def test_rank_of_a_window_of_two_is_the_sign_of_the_change() -> None:
    assert ranks([1.0, 2.0, 2.0, 1.0, 1.5], 2) == [0.0, 1.0, 0.0, -1.0, 1.0]


def test_rank_feeds_threshold_as_the_top_and_bottom_of_the_window() -> None:
    r = rank(pl.Series("prediction", [0.1, 0.3, 0.2, 0.4, 0.0]), 3)

    assert threshold(r, 1.0).to_list() == [0.0, 0.0, 0.0, 1.0, -1.0]


def test_rank_of_fewer_predictions_than_the_window_is_flat() -> None:
    assert ranks([0.1, 0.2, 0.3], 4) == [0.0, 0.0, 0.0]


@pytest.mark.parametrize("window", [50, 99, 104])
def test_rank_of_the_largest_and_the_smallest_is_exactly_one(window: int) -> None:
    # Dividing by the scalar window - 1 goes through its reciprocal in Polars, which for these
    # windows gives 0.9999999999999999: threshold at 1.0 would miss the top of the window.
    rising = pl.Series(range(window), dtype=pl.Float64)

    assert rank(rising, window)[-1] == 1.0
    assert rank(rising.reverse(), window)[-1] == -1.0


def test_rank_gives_a_plain_zero() -> None:
    result = ranks([-0.0, -0.0, -0.0, 1.0, -1.0, -0.0], 3)

    assert result == [0.0, 0.0, 0.0, 1.0, -1.0, 0.0]
    zeros = [value for value in result if value == 0]
    assert [math.copysign(1.0, value) for value in zeros] == [1.0] * 4


def test_rank_keeps_the_name_and_returns_float64() -> None:
    result = rank(pl.Series("prediction", [3, 1, 2], dtype=pl.Int64), 3)

    assert result.name == "prediction"
    assert result.dtype == pl.Float64
    assert result.to_list() == [0.0, 0.0, 0.0]


# both


@pytest.mark.parametrize("calibrate", [zscore, rank])
def test_calibration_of_no_predictions_is_empty(calibrate: Calibration) -> None:
    result = calibrate(pl.Series([], dtype=pl.Float64), 3)

    assert result.dtype == pl.Float64
    assert result.is_empty()


@pytest.mark.parametrize("calibrate", [zscore, rank])
def test_calibration_takes_float32_predictions(calibrate: Calibration) -> None:
    result = calibrate(pl.Series([1.0, 2.0, 3.0], dtype=pl.Float32), 3)

    assert result.dtype == pl.Float64
    assert result.to_list() == [0.0, 0.0, 1.0]


@pytest.mark.parametrize("calibrate", [zscore, rank])
@pytest.mark.parametrize("window", [True, 3.0, "3", None])
def test_calibration_rejects_a_window_that_is_not_an_int(
    calibrate: Calibration, window: object
) -> None:
    with pytest.raises(ValueError, match="window must be an int"):
        calibrate(pl.Series([0.1, 0.2]), window)  # ty: ignore[invalid-argument-type]


@pytest.mark.parametrize("calibrate", [zscore, rank])
@pytest.mark.parametrize("window", [1, 0, -2])
def test_calibration_rejects_a_window_under_two(calibrate: Calibration, window: int) -> None:
    with pytest.raises(ValueError, match="window must be 2 or more"):
        calibrate(pl.Series([0.1, 0.2]), window)


@pytest.mark.parametrize("calibrate", [zscore, rank])
@pytest.mark.parametrize("values", [[0.1, None], [0.1, math.nan]])
def test_calibration_rejects_a_missing_or_nan_prediction(
    calibrate: Calibration, values: list[float | None]
) -> None:
    with pytest.raises(ValueError, match="A prediction is missing or NaN"):
        calibrate(pl.Series(values, dtype=pl.Float64), 2)


@pytest.mark.parametrize("calibrate", [zscore, rank])
def test_calibration_rejects_predictions_that_are_not_numbers(calibrate: Calibration) -> None:
    with pytest.raises(ValueError, match="Predictions must be numbers, not String"):
        calibrate(pl.Series(["0.1", "0.2"]), 2)


# properties on random predictions


@pytest.mark.parametrize("window", WINDOWS)
@pytest.mark.parametrize("seed", SEEDS)
def test_zscore_matches_the_definition(seed: int, window: int) -> None:
    predictions = random_predictions(random.Random(seed))

    result = zscore(predictions, window).to_list()

    assert result == pytest.approx(slow_zscore(predictions.to_list(), window))


@pytest.mark.parametrize("window", WINDOWS)
@pytest.mark.parametrize("seed", SEEDS)
def test_rank_matches_the_definition(seed: int, window: int) -> None:
    predictions = random_predictions(random.Random(seed))

    result = rank(predictions, window).to_list()

    assert result == slow_rank(predictions.to_list(), window)


def test_the_random_predictions_hold_ties_and_windows_without_spread() -> None:
    values = [random_predictions(random.Random(seed)).to_list() for seed in SEEDS]

    assert any(len(set(v[t : t + 3])) < 3 for v in values for t in range(ROWS - 2))
    assert any(len(set(v[t : t + 2])) == 1 for v in values for t in range(ROWS - 1))


@pytest.mark.parametrize("calibrate", [zscore, rank])
@pytest.mark.parametrize("window", WINDOWS)
@pytest.mark.parametrize("seed", SEEDS)
def test_predictions_after_a_row_change_nothing_up_to_it(
    seed: int, window: int, calibrate: Calibration
) -> None:
    rng = random.Random(seed)
    predictions = random_predictions(rng)
    full = calibrate(predictions, window)

    for row in rng.sample(range(ROWS - 1), 5):
        changed = pl.concat([predictions.head(row + 1), random_predictions(rng).slice(row + 1)])
        result = calibrate(changed, window)

        assert result.head(row + 1).equals(full.head(row + 1))

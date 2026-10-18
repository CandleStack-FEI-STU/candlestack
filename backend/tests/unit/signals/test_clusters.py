import math
import random

import polars as pl
import pytest

from candlestack.signals import kmeans

# Three clear groups at 1, 5 and 9 (centers exactly 1, 5, 9; midpoints 3 and 7).
GROUPS = [1.0, 5.0, 9.0, 9.0, 1.0, 5.0, 5.0, 1.0, 9.0, 1.0, 9.0, 5.0]


def signal(
    values: list[float],
    k: int,
    window: int,
    refit_every: int = 10**6,
    dtype: type[pl.DataType] = pl.Float64,
) -> list[float]:
    return kmeans(pl.Series(values, dtype=dtype), k, window, refit_every).to_list()


def test_kmeans_labels_the_lowest_and_highest_group_and_warms_up_flat() -> None:
    probes = [0.0, 1.0, 4.0, 5.0, 6.0, 9.0, 100.0]

    result = signal(GROUPS + probes, 3, 12)

    assert result == [0.0] * 12 + [-1.0, -1.0, 0.0, 0.0, 0.0, 1.0, 1.0]


def test_kmeans_gives_a_value_at_the_midpoint_to_the_lower_group() -> None:
    probes = [3.0, 3.0000001, 7.0, 7.0000001]

    assert signal(GROUPS + probes, 3, 12)[12:] == [-1.0, 0.0, 0.0, 1.0]


def test_kmeans_moves_the_centers_from_the_quantile_start() -> None:
    # k=2 on 0..9, 100, 101: the start centers are the sorted values at index 3 and 9 (3 and 9),
    # the midpoint 6 gives the means 3 and 45, the midpoint 24 gives 4.5 and 100.5, where the
    # groups stop changing. The final midpoint is 52.5, not 6.
    window = [float(value) for value in range(10)] + [100.0, 101.0]

    assert signal([*window, 52.5, 52.6, 7.0], 2, 12)[12:] == [-1.0, 1.0, -1.0]


def test_kmeans_refits_on_the_schedule_and_keeps_the_fit_in_between() -> None:
    # window=4, refit_every=3: fits at rows 4 (on rows 0-3, midpoint 5), 7 (rows 3-6, midpoint
    # 55) and 10 (rows 6-9, midpoint 75). Row 9 and row 10 hold the same 60: the fit of row 7
    # calls it high, the fit of row 10 calls it low.
    values = [0.0, 0.0, 10.0, 10.0, 100.0, 100.0, 100.0, 50.0, 50.0, 60.0, 60.0]

    result = signal(values, 2, 4, 3)

    assert result == [0.0] * 4 + [1.0, 1.0, 1.0, -1.0, -1.0, 1.0, -1.0]


def test_kmeans_fits_on_the_rows_before_the_refit_row_only() -> None:
    # Refit every row: the fit of row 6 sees rows 2-5, all 10, so it is degenerate and the row
    # is flat even though its own 3 would have made a low group. Row 7 sees that 3.
    values = [0.0, 0.0, 10.0, 10.0, 10.0, 10.0, 3.0, 7.0]

    assert signal(values, 2, 4, 1)[4:] == [1.0, 1.0, 0.0, 1.0]


def test_kmeans_gives_flat_rows_from_a_window_of_equal_values() -> None:
    result = signal([2.0] * 6 + [1.0, 2.0, 3.0], 2, 6)

    assert result == [0.0] * 9
    assert [math.copysign(1.0, value) for value in result] == [1.0] * 9


def test_kmeans_with_two_groups_has_no_flat_rows_after_the_warm_up() -> None:
    rng = random.Random(1)
    values = [rng.gauss(0, 1) for _ in range(200)]

    result = signal(values, 2, 20, 7)

    assert set(result[20:]) == {-1.0, 1.0}


def test_kmeans_gives_a_value_at_the_midpoint_inside_the_fit_to_the_lower_group() -> None:
    # Start centers 2 and 6: the 4 at their midpoint joins 0 and 2, so the centers end at 2
    # and 6 (midpoint 4) rather than at 1 and 5 (midpoint 3), and 3.5 is low, not high.
    assert signal([6.0, 2.0, 0.0, 4.0, 3.5], 2, 4)[4] == -1.0


def test_kmeans_keeps_an_empty_group_at_its_center() -> None:
    # Start centers 8 and 8 (the sorted values at index 1 and 3): every value is as near to
    # one as to the other and goes to the lower one, whose mean is 7.5, while the empty upper
    # group keeps 8. The next round splits 6 from the three 8s, so the midpoint ends at 7.
    assert signal([8.0, 6.0, 8.0, 8.0, 5.0], 2, 4)[4] == -1.0


def test_kmeans_leaves_the_upper_of_two_equal_centers_empty() -> None:
    # Start centers 5 and 5: with every value in the lower group its mean is 4.875, and the
    # next rounds split 0 from the rest, so the centers end at 0 and about 5.57 and 4.0 is
    # high. Had the values above 5 gone to the upper center, it would have ended at 9 with
    # the lower one at about 4.29, and 4.0 would be low.
    assert signal([0.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 9.0, 4.0], 2, 8)[8] == 1.0


def test_kmeans_starts_the_centers_at_the_quantiles() -> None:
    # The sorted window is 1, 4, 4, 5 and the start centers are its values at index 1 and 3
    # (4 and 5), which end at 3 and 5, midpoint 4. Starting at index 0 and 2 (1 and 4) would
    # end at 1 and about 4.33, midpoint about 2.67, and 3.0 would be high.
    assert signal([4.0, 1.0, 4.0, 5.0, 3.0], 2, 4)[4] == -1.0


def test_kmeans_takes_the_floor_of_the_start_index() -> None:
    # Five values and two centers: the indexes are floor(1.25) = 1 and floor(3.75) = 3 of the
    # sorted 0, 2, 4, 4, 9, so the centers start at 2 and 4 and end at 1 and about 5.67.
    # Rounding to 1 and 4 would start at 2 and 9 and end at 2.5 and 9, calling 5.0 low.
    assert signal([2.0, 4.0, 9.0, 4.0, 0.0, 5.0], 2, 5)[5] == 1.0


def test_kmeans_returns_a_float64_signal() -> None:
    result = kmeans(pl.Series("prediction", [*GROUPS, 0.0, 9.0], dtype=pl.Float32), 3, 12, 1)

    assert result.name == "signal"
    assert result.dtype == pl.Float64
    assert result.to_list()[12:] == [-1.0, 1.0]


def test_kmeans_takes_integer_predictions() -> None:
    assert signal([0, 0, 10, 10, 0, 10], 2, 4, dtype=pl.Int64)[4:] == [-1.0, 1.0]


def test_kmeans_of_fewer_predictions_than_the_window_is_all_flat() -> None:
    assert signal([1.0, 2.0, 3.0], 2, 4) == [0.0, 0.0, 0.0]


def test_kmeans_of_no_predictions_is_an_empty_signal() -> None:
    result = kmeans(pl.Series([], dtype=pl.Float64), 2, 4, 1)

    assert result.dtype == pl.Float64
    assert result.is_empty()


@pytest.mark.parametrize("k", [1, 6, 0, -1])
def test_kmeans_rejects_k_outside_2_to_5(k: int) -> None:
    with pytest.raises(ValueError, match="k must be between 2 and 5"):
        kmeans(pl.Series(GROUPS), k, 12, 1)


def test_kmeans_rejects_a_window_under_twice_k() -> None:
    with pytest.raises(ValueError, match=r"window must be at least 2 \* k \(6\), got 5"):
        kmeans(pl.Series(GROUPS), 3, 5, 1)


def test_kmeans_rejects_a_refit_every_under_1() -> None:
    with pytest.raises(ValueError, match="refit_every must be at least 1, got 0"):
        kmeans(pl.Series(GROUPS), 3, 12, 0)


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ((2.0, 12, 1), "k must be an int, got 2.0"),
        ((True, 12, 1), "k must be an int, got True"),
        ((2, 12.0, 1), "window must be an int, got 12.0"),
        ((2, 12, "1"), "refit_every must be an int, got '1'"),
    ],
)
def test_kmeans_rejects_arguments_that_are_not_ints(
    arguments: tuple[int, int, int], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        kmeans(pl.Series(GROUPS), *arguments)


@pytest.mark.parametrize("values", [[0.1, None], [0.1, math.nan]])
def test_kmeans_rejects_a_missing_or_nan_prediction(values: list[float | None]) -> None:
    with pytest.raises(ValueError, match="A prediction is missing or NaN"):
        kmeans(pl.Series(values, dtype=pl.Float64), 2, 4, 1)


@pytest.mark.parametrize("value", [math.inf, -math.inf])
def test_kmeans_rejects_an_infinite_prediction(value: float) -> None:
    with pytest.raises(ValueError, match="A prediction is infinite"):
        kmeans(pl.Series([0.1, value]), 2, 4, 1)


def test_kmeans_rejects_predictions_that_are_not_numbers() -> None:
    with pytest.raises(ValueError, match="Predictions must be numbers, not String"):
        kmeans(pl.Series(["0.1"]), 2, 4, 1)


# Properties on random predictions with fixed seeds: the signal up to a row never depends on
# the predictions after it, every value is -1, 0 or 1, and the fast fit on the sorted window
# gives what a plain one does, value by value.

ROWS = 120
WINDOW = 20
REFIT_EVERY = 7


def random_predictions(rng: random.Random, *, discrete: bool = False) -> list[float]:
    """Normal predictions, or a few repeated integer values, which make equal centers and
    exact ties common."""
    if discrete:
        return [float(rng.randint(0, 4)) for _ in range(ROWS)]
    return [rng.gauss(0, 1) for _ in range(ROWS)]


def plain_nearest(value: float, centers: list[float]) -> int:
    """The index of the nearest of all centers, the lower index on a tie."""
    return min(range(len(centers)), key=lambda i: (abs(value - centers[i]), i))


def plain_fit(values: list[float], k: int) -> list[float] | None:
    """The centers by the rules spelled out one value at a time: a plain mean per group, an
    empty group keeping its center, sorted, until the groups stop changing or 100 rounds."""
    ordered = sorted(values)
    if ordered[0] == ordered[-1]:
        return None
    centers = [ordered[(2 * i + 1) * len(ordered) // (2 * k)] for i in range(k)]
    groups: list[int] = []
    for _ in range(100):
        new_groups = [plain_nearest(value, centers) for value in ordered]
        if new_groups == groups:
            break
        groups = new_groups
        members = [[v for v, g in zip(ordered, groups, strict=True) if g == i] for i in range(k)]
        centers = sorted(
            sum(own) / len(own) if own else center
            for center, own in zip(centers, members, strict=True)
        )
    return centers


def plain_kmeans(values: list[float], k: int, window: int, refit_every: int) -> list[float]:
    result = [0.0] * len(values)
    centers = None
    for t in range(window, len(values)):
        if (t - window) % refit_every == 0:
            centers = plain_fit(values[t - window : t], k)
        if centers is not None:
            group = plain_nearest(values[t], centers)
            result[t] = -1.0 if group == 0 else 1.0 if group == k - 1 else 0.0
    return result


@pytest.mark.parametrize("discrete", [False, True], ids=["continuous", "discrete"])
@pytest.mark.parametrize("k", [2, 3, 5])
@pytest.mark.parametrize("seed", range(10))
def test_kmeans_gives_what_the_plain_rules_give(seed: int, k: int, *, discrete: bool) -> None:
    rng = random.Random(seed)
    values = random_predictions(rng, discrete=discrete)
    window, refit_every = rng.randint(2 * k, 24), rng.randint(1, 9)

    assert signal(values, k, window, refit_every) == plain_kmeans(values, k, window, refit_every)


@pytest.mark.parametrize("k", [2, 3, 5])
@pytest.mark.parametrize("seed", range(10))
def test_predictions_after_a_row_change_nothing_up_to_it(seed: int, k: int) -> None:
    rng = random.Random(seed)
    values = random_predictions(rng)
    full = signal(values, k, WINDOW, REFIT_EVERY)

    for row in rng.sample(range(ROWS - 1), 5):
        changed = values[: row + 1] + random_predictions(rng)[row + 1 :]

        assert signal(changed, k, WINDOW, REFIT_EVERY)[: row + 1] == full[: row + 1]


@pytest.mark.parametrize("k", [2, 3, 5])
@pytest.mark.parametrize("seed", range(10))
def test_the_signal_is_minus_one_zero_or_one(seed: int, k: int) -> None:
    result = signal(random_predictions(random.Random(seed)), k, WINDOW, REFIT_EVERY)

    assert set(result) <= {-1.0, 0.0, 1.0}
    assert {-1.0, 1.0} <= set(result[WINDOW:])

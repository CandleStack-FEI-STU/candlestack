"""``min_hold`` by hand, and its properties on random signals with fixed seeds: it never looks
ahead, every run it starts is at least ``candles`` long, and with one candle it changes nothing."""

import math
import random
from typing import Any

import polars as pl
import pytest

from candlestack.signals import min_hold

ROWS = 60
SEEDS = range(20)
CANDLES = [1, 2, 3, 5, 8]


def held(values: list[float], candles: int) -> list[float]:
    return min_hold(pl.Series(values), candles).to_list()


def random_signal(rng: random.Random) -> list[float]:
    """A signal of -1, 0 and +1 that changes on about a third of the rows."""
    values, signal = [], 0
    for _ in range(ROWS):
        if rng.random() < 0.3:
            signal = rng.choice((-1, 0, 1))
        values.append(float(signal))
    return values


# by hand


def test_min_hold_keeps_an_entry_whatever_the_input_says() -> None:
    assert held([1.0, 0.0, -1.0, 1.0, 0.0], 3) == [1.0, 1.0, 1.0, 1.0, 0.0]


def test_min_hold_keeps_a_flip_whatever_the_input_says() -> None:
    assert held([1.0, 1.0, 1.0, -1.0, 1.0, 0.0, 0.0], 3) == [1.0, 1.0, 1.0, -1.0, -1.0, -1.0, 0.0]


def test_min_hold_does_not_hold_a_change_to_flat() -> None:
    assert held([1.0, 1.0, 1.0, 0.0, 1.0, 0.0], 2) == [1.0, 1.0, 1.0, 0.0, 1.0, 1.0]


def test_min_hold_follows_the_input_again_after_the_hold() -> None:
    # The input flipped during the hold: once it ends, the flip is taken and starts a new hold.
    assert held([1.0, -1.0, -1.0, -1.0], 2) == [1.0, 1.0, -1.0, -1.0]


def test_min_hold_starts_a_new_hold_at_each_change_to_a_position() -> None:
    assert held([1.0, 0.0, 0.0, 1.0, 0.0], 2) == [1.0, 1.0, 0.0, 1.0, 1.0]


def test_min_hold_does_not_extend_a_position_the_input_keeps() -> None:
    # Only a change starts a hold: a signal that stays at +1 is not held again when it ends.
    assert held([1.0, 1.0, 1.0, 0.0], 2) == [1.0, 1.0, 1.0, 0.0]


def test_min_hold_starts_a_hold_on_a_non_zero_first_row() -> None:
    assert held([-1.0, 1.0, 1.0], 2) == [-1.0, -1.0, 1.0]


def test_min_hold_leaves_a_flat_first_row_alone() -> None:
    assert held([0.0, 0.0, 1.0, 0.0], 2) == [0.0, 0.0, 1.0, 1.0]


def test_min_hold_stops_with_the_series() -> None:
    assert held([0.0, 1.0, 0.0], 5) == [0.0, 1.0, 1.0]


def test_min_hold_with_one_candle_is_the_signal() -> None:
    assert held([1.0, -1.0, 0.0, 1.0, 1.0], 1) == [1.0, -1.0, 0.0, 1.0, 1.0]


def test_min_hold_holds_any_non_zero_value() -> None:
    assert held([0.5, 0.0, 2.0, 0.0], 2) == [0.5, 0.5, 2.0, 2.0]


def test_min_hold_keeps_the_name_and_returns_float64() -> None:
    result = min_hold(pl.Series("signal", [1, 0, -1], dtype=pl.Int8), 2)

    assert result.name == "signal"
    assert result.dtype == pl.Float64
    assert result.to_list() == [1.0, 1.0, -1.0]


def test_min_hold_gives_a_plain_zero() -> None:
    # -0.0 is flat, held or not: it comes out as a plain 0.0, as in threshold.
    result = min_hold(pl.Series([-0.0, 0.0, 1.0, -0.0, -0.0]), 2).to_list()

    assert result == [0.0, 0.0, 1.0, 1.0, 0.0]
    assert [math.copysign(1.0, value) for value in result] == [1.0, 1.0, 1.0, 1.0, 1.0]


def test_min_hold_of_no_signal_is_an_empty_signal() -> None:
    result = min_hold(pl.Series([], dtype=pl.Float64), 3)

    assert result.dtype == pl.Float64
    assert result.is_empty()


@pytest.mark.parametrize("candles", [0, -1, 1.0, 2.5, True, False, "2", None])
def test_min_hold_rejects_candles_that_are_not_an_int_of_one_or_more(candles: Any) -> None:
    with pytest.raises(ValueError, match="candles must be an int of 1 or more"):
        min_hold(pl.Series([1.0]), candles)


@pytest.mark.parametrize("values", [[1.0, None], [1.0, math.nan]])
def test_min_hold_rejects_a_missing_or_nan_signal_value(values: list[float | None]) -> None:
    with pytest.raises(ValueError, match="A signal value is missing or NaN"):
        min_hold(pl.Series(values, dtype=pl.Float64), 2)


def test_min_hold_rejects_a_signal_that_is_not_numbers() -> None:
    with pytest.raises(ValueError, match="Signal values must be numbers, not String"):
        min_hold(pl.Series(["1.0"]), 2)


# properties


@pytest.mark.parametrize("candles", CANDLES)
@pytest.mark.parametrize("seed", SEEDS)
def test_data_after_a_row_changes_nothing_up_to_it(seed: int, candles: int) -> None:
    rng = random.Random(seed)
    values = random_signal(rng)
    full = held(values, candles)

    for row in rng.sample(range(1, ROWS - 1), 5):
        changed = values[: row + 1] + random_signal(rng)[row + 1 :]

        assert held(changed, candles)[: row + 1] == full[: row + 1]


@pytest.mark.parametrize("candles", CANDLES)
@pytest.mark.parametrize("seed", SEEDS)
def test_every_run_that_starts_at_a_change_is_at_least_candles_long(
    seed: int, candles: int
) -> None:
    result = held(random_signal(random.Random(seed)), candles)

    starts = [
        row
        for row, value in enumerate(result)
        if value != 0 and (row == 0 or value != result[row - 1])
    ]
    assert starts
    for row in starts:
        run = result[row:]
        length = next((i for i, value in enumerate(run) if value != run[0]), len(run))
        assert length >= min(candles, len(run))


@pytest.mark.parametrize("seed", SEEDS)
def test_with_one_candle_the_signal_is_unchanged(seed: int) -> None:
    values = random_signal(random.Random(seed))

    assert held(values, 1) == values

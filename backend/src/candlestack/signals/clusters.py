"""Signals from groups of predictions: k-means fitted on the past only."""

from bisect import bisect_left, bisect_right
from itertools import accumulate, pairwise

import polars as pl

from candlestack.signals.rules import _float64

_ITERATIONS = 100


def kmeans(predictions: pl.Series, k: int, window: int, refit_every: int) -> pl.Series:
    """The ``signal`` of each prediction from its group among ``k`` groups of earlier ones.

    The groups are one-dimensional k-means (Lloyd) on the ``window`` predictions before a refit
    row: a prediction in the lowest group gives -1.0, in the highest 1.0, in between 0.0. The
    fit in use at row t is the one made at the latest refit row f <= t, on rows f-window to
    f-1 (so no prediction is in its own fit); refits happen at rows ``window``, ``window +
    refit_every``, and so on. The rows before ``window`` have no fit yet and give 0.0.

    The fit is deterministic. The centers start at the quantiles (i + 0.5) / k of the window's
    values, i = 0..k-1: the sorted value at index floor((i + 0.5) * n / k), capped at n-1. Then,
    until the groups stop changing or 100 rounds: each value goes to its nearest center, a
    value at the midpoint of two neighbouring centers to the lower one, and each center moves
    to the mean of its group; a group that is empty keeps its center. The centers are kept
    sorted ascending, and a prediction is assigned to a center by the same midpoint rule. When
    all values of a window are equal, the groups mean nothing: every row using that fit gives
    0.0.

    Args:
        predictions: the predictions in time order, as numbers.
        k: the number of groups, 2 to 5. With 2 there is no flat group.
        window: how many earlier predictions a fit uses, at least 2 * k.
        refit_every: how many rows a fit is used for, at least 1.

    Returns:
        A Float64 Series named ``signal`` with the values -1.0, 0.0 or 1.0 (a plain 0.0, never
        -0.0), as long as ``predictions``.

    Raises:
        ValueError: ``k``, ``window`` or ``refit_every`` is not an int or out of its range, or
            a prediction is not a number or missing.
    """
    _check_arguments(k, window, refit_every)
    values = _float64(predictions, "predictions", "prediction").to_list()
    signal = [0.0] * len(values)
    cuts: list[float] | None = None
    for t in range(window, len(values)):
        if (t - window) % refit_every == 0:
            cuts = _fit(values[t - window : t], k)
        if cuts is not None:
            signal[t] = _label(bisect_left(cuts, values[t]), k)
    return pl.Series("signal", signal, dtype=pl.Float64)


def _fit(values: list[float], k: int) -> list[float] | None:
    """The k-1 midpoints between the sorted centers of a k-means on ``values``, or None when
    all values are equal (the degenerate fit)."""
    ordered = sorted(values)
    n = len(ordered)
    if ordered[0] == ordered[-1]:
        return None
    sums = [0.0, *accumulate(ordered)]
    # floor((i + 0.5) * n / k) in integer arithmetic, so no rounding picks another index.
    centers = [ordered[min((2 * i + 1) * n // (2 * k), n - 1)] for i in range(k)]
    edges: list[int] = []
    for _ in range(_ITERATIONS):
        cuts = _midpoints(centers)
        new_edges = [0, *(bisect_right(ordered, cut) for cut in cuts), n]
        if new_edges == edges:
            break
        edges = new_edges
        centers = sorted(
            (sums[hi] - sums[lo]) / (hi - lo) if hi > lo else center
            for center, (lo, hi) in zip(centers, pairwise(edges), strict=True)
        )
    return _midpoints(centers)


def _midpoints(centers: list[float]) -> list[float]:
    """The midpoints between neighbouring centers: a value at or below one goes to the lower
    center, so a tie goes to the lower center."""
    return [(low + high) / 2 for low, high in pairwise(centers)]


def _label(group: int, k: int) -> float:
    """-1.0 for the lowest group, 1.0 for the highest, else 0.0."""
    if group == 0:
        return -1.0
    return 1.0 if group == k - 1 else 0.0


def _check_arguments(k: int, window: int, refit_every: int) -> None:
    """Raises ``ValueError`` unless all three are ints (not bools) in their ranges."""
    for name, value in (("k", k), ("window", window), ("refit_every", refit_every)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} must be an int, got {value!r}")
    if not 2 <= k <= 5:
        raise ValueError(f"k must be between 2 and 5, got {k}")
    if window < 2 * k:
        raise ValueError(f"window must be at least 2 * k ({2 * k}), got {window}")
    if refit_every < 1:
        raise ValueError(f"refit_every must be at least 1, got {refit_every}")

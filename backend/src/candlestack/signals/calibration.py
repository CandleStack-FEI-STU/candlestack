"""Calibration: predictions rescaled from their own past, so one threshold fits every model.

Models predict on different scales (the supervisor's stay within about ±0.4, another may give
±5), so a limit that is right for one is never reached by another. ``zscore`` and ``rank``
express each prediction relative to the ``window`` predictions ending at it, nothing later, so
they add no look-ahead.
"""

import polars as pl

from candlestack.signals.rules import _float64


def zscore(predictions: pl.Series, window: int) -> pl.Series:
    """Each prediction as standard deviations from the mean of the ``window`` predictions ending
    at it: (p[t] - mean) / std over rows t-window+1..t, with the sample std (ddof=1).

    A prediction counts in its own window: it is known at t. The first window-1 rows have no
    full window yet and give 0.0 (flat), and so does a window whose predictions are all equal
    (std 0). A plain 0.0, never -0.0.

    Raises:
        ValueError: ``window`` is not an int of 2 or more, or a prediction is not a number or
            missing.
    """
    _check_window(window)
    p = _float64(predictions, "predictions", "prediction")
    value, mean, std = pl.col("p"), pl.col("mean"), pl.col("std")
    z = (value - mean) / std
    return (
        p.to_frame("p")
        .with_columns(mean=value.rolling_mean(window), std=value.rolling_std(window, ddof=1))
        # std is null before the first full window; z != 0 keeps -0.0 out.
        .select(pl.when((std > 0) & (z != 0)).then(z).otherwise(0.0).alias(p.name))
        .to_series()
    )


def rank(predictions: pl.Series, window: int) -> pl.Series:
    """Where each prediction ranks among the ``window`` predictions ending at it, in [-1, 1]:
    the largest of the window gives 1.0, the smallest -1.0, the median 0.0.

    With ``below`` the other window-1 predictions smaller than p[t] and ``equal`` those equal to
    it, the rank is r = (below + equal / 2) / (window - 1), and the output 2r - 1: tied
    predictions share the middle of their places. The first window-1 rows have no full window
    yet and give 0.0 (flat). A plain 0.0, never -0.0.

    Raises:
        ValueError: ``window`` is not an int of 2 or more, or a prediction is not a number or
            missing.
    """
    _check_window(window)
    p = _float64(predictions, "predictions", "prediction")
    below = pl.zeros(p.len(), pl.Int64, eager=True)
    equal = below.clone()
    # One lag at a time: each compares p[t] with p[t - lag] over the whole series, so the memory
    # stays at a few columns, and a window of 500 on 100k rows takes under a second.
    for lag in range(1, min(window, p.len() + 1)):
        other = p.shift(lag)
        below = below + (other < p).fill_null(value=False).cast(pl.Int64)
        equal = equal + (other == p).fill_null(value=False).cast(pl.Int64)
    # 2r - 1 as one division of integers, by a column: Polars divides by a scalar through its
    # reciprocal, which for some windows (50) leaves the largest prediction a bit under 1.0.
    places = 2 * below + equal - (window - 1)
    out = places.cast(pl.Float64) / pl.repeat(float(window - 1), p.len(), eager=True)
    value, warm_up = pl.col("r"), pl.int_range(pl.len()) < window - 1
    return (
        out.to_frame("r")
        .select(pl.when(warm_up | (value == 0)).then(0.0).otherwise(value).alias(p.name))
        .to_series()
    )


def _check_window(window: int) -> None:
    """Raises ``ValueError`` unless ``window`` is an int of 2 or more."""
    if isinstance(window, bool) or not isinstance(window, int):
        raise ValueError(f"window must be an int, got {window!r}")
    if window < 2:
        raise ValueError(f"window must be 2 or more, got {window}")

"""Rules that turn predictions into a ``signal`` in {-1.0, 0.0, 1.0}."""

import math

import polars as pl


def threshold(predictions: pl.Series, limit: float) -> pl.Series:
    """The ``signal`` of each prediction p: 1.0 if p >= limit, -1.0 if p <= -limit, else 0.0.

    A prediction of exactly 0 gives 0.0, even with ``limit`` 0. The comparison is in float64:
    a float32 prediction is widened first (exactly), so it meets the limit only when its value
    does, not when it merely rounds to the limit in float32.

    Raises:
        ValueError: ``limit`` is negative or NaN, or a prediction is not a number or missing.
    """
    if math.isnan(limit) or limit < 0:
        raise ValueError(f"limit must be 0 or more, got {limit}")
    if not predictions.dtype.is_numeric():
        raise ValueError(f"Predictions must be numbers, not {predictions.dtype}")
    p = predictions.cast(pl.Float64)
    if p.null_count() or p.is_nan().any():
        raise ValueError("A prediction is missing or NaN")
    value = pl.col("p")
    return (
        p.to_frame("p")
        .select(
            pl.when((value > 0) & (value >= limit))
            .then(1.0)
            .when((value < 0) & (value <= -limit))
            .then(-1.0)
            .otherwise(0.0)
            .alias("signal")
        )
        .to_series()
    )


def long_only(signal: pl.Series) -> pl.Series:
    """The signal without short positions: a negative value becomes 0.0, the rest stays."""
    return signal.cast(pl.Float64).clip(lower_bound=0.0)

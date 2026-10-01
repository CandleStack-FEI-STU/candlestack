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
    p = _float64(predictions, "predictions", "prediction")
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
    """The signal without short positions: a negative value becomes 0.0, the rest stays.

    Like ``threshold``, it gives a plain 0.0, never -0.0.

    Raises:
        ValueError: a signal value is not a number, or is missing or NaN.
    """
    value = pl.col("signal")
    return (
        _float64(signal, "signal values", "signal value")
        .to_frame("signal")
        .select(pl.when(value > 0).then(value).otherwise(0.0).alias(signal.name))
        .to_series()
    )


def _float64(values: pl.Series, plural: str, singular: str) -> pl.Series:
    """``values`` as Float64; raises ``ValueError`` unless all are numbers, none missing or NaN."""
    if not values.dtype.is_numeric():
        raise ValueError(f"{plural.capitalize()} must be numbers, not {values.dtype}")
    floats = values.cast(pl.Float64)
    if floats.null_count() or floats.is_nan().any():
        raise ValueError(f"A {singular} is missing or NaN")
    return floats

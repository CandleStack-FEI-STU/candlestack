"""Post-processing of predictions and signals: smoothing, hysteresis and confirmation.

Each function is one pass forward over its series: a value at row t comes from the values up
to t only, so none of them looks ahead.
"""

import math

import polars as pl

from candlestack.signals.rules import _float64


def ema(predictions: pl.Series, span: int) -> pl.Series:
    """The exponential moving average of the predictions, with ``alpha = 2 / (span + 1)``.

    The first average is the first prediction, then ``e[t] = alpha * p[t] + (1 - alpha) * e[t-1]``
    (no adjustment for the short start): each value uses only the predictions up to its row. A
    span of 1 gives the predictions back, as Float64. Keeps the name of the input and gives a
    plain 0.0, never -0.0.

    Raises:
        ValueError: ``span`` is not an int of 1 or more, or a prediction is not a number,
            missing or infinite.
    """
    _check_count(span, "span")
    p = _float64(predictions, "predictions", "prediction")
    # An infinite prediction would make every average after it inf or NaN.
    if p.is_infinite().any():
        raise ValueError("A prediction is infinite")
    alpha = 2 / (span + 1)
    average = None
    averages = []
    for value in p.to_list():
        average = value if average is None else alpha * value + (1 - alpha) * average
        averages.append(average + 0.0)  # + 0.0 turns a -0.0 into the plain 0.0
    return pl.Series(predictions.name, averages, dtype=pl.Float64)


def hysteresis(predictions: pl.Series, enter: float, exit: float) -> pl.Series:  # noqa: A002 (the trader's pair of limits)
    """The ``signal`` of the predictions with two limits: a position opens at ``enter`` and
    closes below ``exit``, so a prediction between the two keeps the position it is in.

    A state machine that starts flat. Flat goes long when ``p > 0`` and ``p >= enter``, short
    when ``p < 0`` and ``p <= -enter``. Long stays long while ``p > 0`` and ``p >= exit``;
    otherwise it goes short when ``p < 0`` and ``p <= -enter``, else flat. Short mirrors long.
    With ``exit`` equal to ``enter`` it is ``threshold``. Compares in float64, like
    ``threshold``.

    Raises:
        ValueError: the limits are not finite with ``0 <= exit <= enter``, or a prediction is
            not a number or missing.
    """
    if not (math.isfinite(enter) and math.isfinite(exit) and 0 <= exit <= enter):
        raise ValueError(
            f"enter and exit must be finite with 0 <= exit <= enter, got enter {enter} and "
            f"exit {exit}"
        )
    state = 0.0
    signal = []
    for value in _float64(predictions, "predictions", "prediction").to_list():
        # The side the position is on keeps it at the exit limit; the other side needs enter.
        long_limit = exit if state > 0 else enter
        short_limit = exit if state < 0 else enter
        if value > 0 and value >= long_limit:
            state = 1.0
        elif value < 0 and value <= -short_limit:
            state = -1.0
        else:
            state = 0.0
        signal.append(state)
    return pl.Series("signal", signal, dtype=pl.Float64)


def confirm(signal: pl.Series, candles: int) -> pl.Series:
    """The signal with a value counted only once it has held for ``candles`` rows in a row;
    until then the last counted value stays.

    The first row counts at once: it is the engine's warm-up row, which never trades. A
    ``candles`` of 1 gives the signal back, as Float64. Keeps the name of the input and gives a
    plain 0.0, never -0.0.

    Raises:
        ValueError: ``candles`` is not an int of 1 or more, or a signal value is not a number
            or missing.
    """
    _check_count(candles, "candles")
    counted = previous = None
    held = 0  # rows in a row with the current value, this one included
    confirmed = []
    for value in _float64(signal, "signal values", "signal value").to_list():
        held = held + 1 if value == previous else 1
        previous = value
        if counted is None or held >= candles:
            counted = value
        confirmed.append(counted + 0.0)  # + 0.0 turns a -0.0 into the plain 0.0
    return pl.Series(signal.name, confirmed, dtype=pl.Float64)


def _check_count(value: int, name: str) -> None:
    """Raises ``ValueError`` unless ``value`` is an int of 1 or more (a bool is not an int here)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an int, got {value!r}")
    if value < 1:
        raise ValueError(f"{name} must be 1 or more, got {value}")

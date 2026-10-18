"""A minimum holding period: a new position in the ``signal`` is kept for a number of candles."""

import polars as pl

from candlestack.signals.rules import _float64


def min_hold(signal: pl.Series, candles: int) -> pl.Series:
    """The signal with each new position kept for at least ``candles`` rows.

    Once the output changes to a non-zero value at row r (an entry from flat, or a flip from
    +1 to -1 or back), it stays at that value through row r + candles - 1: during the hold the
    input's changes are ignored, a flat one like any other. From row r + candles on it follows
    the input again, and a change there may start a new hold. Going flat starts no hold, and
    neither does the first row: it only sets the starting value, as the engine's warm-up row
    (rule 1) opens nothing there either. With ``candles`` 1 the signal comes back as it is.
    Like ``threshold``, it gives a plain 0.0, never -0.0.

    The output up to a row depends only on the input up to it: a plain loop forward, so it
    cannot look ahead.

    Raises:
        ValueError: ``candles`` is not an int of 1 or more, or a signal value is not a number,
            or is missing or NaN.
    """
    if isinstance(candles, bool) or not isinstance(candles, int) or candles < 1:
        raise ValueError(f"candles must be an int of 1 or more, got {candles!r}")
    values = _float64(signal, "signal values", "signal value").to_list()
    held: list[float] = []
    previous, until = 0.0, 0  # the last output, and the first row after its hold
    for row, value in enumerate(values):
        if row < until:
            current = previous
        else:
            current = 0.0 if value == 0 else value  # -0.0 is flat too
            if row and current and current != previous:  # a change to a position: a new hold
                until = row + candles
        held.append(current)
        previous = current
    return pl.Series(signal.name, held, dtype=pl.Float64)

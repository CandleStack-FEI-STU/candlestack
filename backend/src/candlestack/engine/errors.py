"""The engine's error."""


class InvalidInput(ValueError):
    """The frame given to ``backtest`` breaks the input contract: a missing column, a column of
    the wrong type, a ``ts`` that does not increase, a missing or non-positive price, or a signal
    other than -1, 0 and +1. The message names every broken rule."""

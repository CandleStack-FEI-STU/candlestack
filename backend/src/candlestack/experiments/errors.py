"""Errors of the backtests service. They know nothing about HTTP: the API turns each into its
problem."""


class BacktestNotFound(Exception):
    """The user has no backtest with the ID (another user's backtest included)."""


class UnknownUser(Exception):
    """No user has the email (the seed command)."""

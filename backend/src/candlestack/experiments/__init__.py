"""Experiments: the users' backtests, stored with their setup and results, listed on the
Backtests page and summed up on the Dashboard. Putting runs together (preprocessing, ml,
signals, engine, metrics) comes later, with the backtest builder.

Other modules import only from here (``from candlestack.experiments import backtests_router``),
never from the submodules. ``candlestack.main`` puts ``model_usage`` on ``app.state.model_usage``,
so the models list of ``ml``, which cannot import this module, shows how the backtests used
each model. A user's backtests go with the account by the foreign key's cascade: no hook.
"""

from candlestack.experiments.api import router as backtests_router
from candlestack.experiments.models import Backtest
from candlestack.experiments.schemas import BacktestOut, BacktestsPage, DashboardOut
from candlestack.experiments.store import model_usage

__all__ = [
    "Backtest",
    "BacktestOut",
    "BacktestsPage",
    "DashboardOut",
    "backtests_router",
    "model_usage",
]

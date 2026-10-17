"""Experiments: the users' backtests, stored with their setup and results, listed on the
Backtests page and summed up on the Dashboard. Putting runs together (preprocessing, ml,
signals, engine, metrics) comes later, with the backtest builder.

Other modules import only from here (``from candlestack.experiments import backtests_router``),
never from the submodules. ``candlestack.main`` puts ``model_usage`` on ``app.state.model_usage``,
so the models list of ``ml``, which cannot import this module, shows how the backtests used
each model. A user's backtests go with the account by the foreign key's cascade: no hook.
Importing the module declares its table (``backend/migrations`` relies on it).

``python -m candlestack.experiments.seed --email <email>`` fills an account with test backtests
(stage and local only).
"""

from candlestack.experiments.api import router as backtests_router
from candlestack.experiments.store import model_usage

__all__ = ["backtests_router", "model_usage"]

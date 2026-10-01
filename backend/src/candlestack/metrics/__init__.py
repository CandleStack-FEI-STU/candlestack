"""Metrics: the statistics of one backtest run, from its trades and equity series.

It imports no other module and no server library. Other modules import only from here
(``from candlestack.metrics import stats``), never from the submodules.
"""

from candlestack.metrics.summary import drawdown, stats

__all__ = ["drawdown", "stats"]

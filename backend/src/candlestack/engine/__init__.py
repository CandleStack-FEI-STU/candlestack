"""The backtest engine: the loop that turns candles and signals into trades and an equity
series.

It imports no other module and no server library. Other modules import only from here
(``from candlestack.engine import ENGINE_VERSION``), never from the submodules.
"""

from candlestack.engine.version import ENGINE_VERSION

__all__ = ["ENGINE_VERSION"]

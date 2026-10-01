"""The backtest engine: the loop that turns candles and signals into trades and an equity
series.

It imports no other module and no server library. Other modules import only from here
(``from candlestack.engine import ENGINE_VERSION``), never from the submodules.
"""

from candlestack.engine.errors import InvalidInput
from candlestack.engine.run import Result, backtest
from candlestack.engine.settings import Settings
from candlestack.engine.version import ENGINE_VERSION

__all__ = ["ENGINE_VERSION", "InvalidInput", "Result", "Settings", "backtest"]

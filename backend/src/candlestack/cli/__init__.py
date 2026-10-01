"""The ``candlestack-bt`` command: backtests from the command line.

It wires signals, the engine and metrics together; no module imports it.
"""

from candlestack.cli.commands import main

__all__ = ["main"]

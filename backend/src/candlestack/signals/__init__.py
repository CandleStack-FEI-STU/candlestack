"""Signals: turn a model's predictions into the signals the engine trades on.

It imports no other module and no server library. Other modules import only from here, never
from the submodules.
"""

from candlestack.signals.alignment import AlignReport, align, relabel
from candlestack.signals.rules import long_only, threshold

__all__ = ["AlignReport", "align", "long_only", "relabel", "threshold"]

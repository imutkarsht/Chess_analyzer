"""Compatibility import for :class:`TimeManagementCard`.

The implementation lives in the ``time`` package; this module keeps existing
imports working.
"""

from src.gui.views.metrics.time.time_card import TimeManagementCard

__all__ = ["TimeManagementCard"]

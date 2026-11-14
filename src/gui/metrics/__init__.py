"""
Metrics package - Dashboard widgets and statistics.
"""

# Chart helpers intentionally live in ``charts`` and are imported directly by
# the cards that need them, so importing ``src.gui.metrics`` (e.g. for the card
# registry) does not pull Matplotlib into the first-launch path.
from .workers import InsightWorker, StatsWorker

__all__ = ["InsightWorker", "StatsWorker"]

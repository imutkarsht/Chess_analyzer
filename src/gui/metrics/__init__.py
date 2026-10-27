"""
Metrics package - Dashboard widgets and statistics.
"""

from .charts import (
    create_accuracy_trend_figure,
    create_donut_figure,
    fig_to_canvas,
    fig_to_pixmap,
)
from .workers import InsightWorker, StatsWorker

__all__ = [
    "InsightWorker",
    "StatsWorker",
    "create_donut_figure",
    "create_accuracy_trend_figure",
    "fig_to_pixmap",
    "fig_to_canvas",
]

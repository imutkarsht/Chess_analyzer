"""
Metrics package - Dashboard widgets and statistics.
"""
from .charts import (
    create_donut_figure,
    create_legend_widget,
    create_line_chart_figure,
    fig_to_canvas,
    fig_to_label,
    fig_to_pixmap,
)
from .workers import InsightWorker, StatsWorker

__all__ = [
    'InsightWorker', 'StatsWorker',
    'create_donut_figure', 'create_line_chart_figure',
    'fig_to_pixmap', 'fig_to_label', 'fig_to_canvas', 'create_legend_widget'
]

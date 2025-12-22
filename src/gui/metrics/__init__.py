"""
Metrics package - Dashboard widgets and statistics.
"""
from .workers import InsightWorker, StatsWorker
from .charts import (
    create_donut_figure, create_line_chart_figure, 
    fig_to_pixmap, fig_to_label, fig_to_canvas, create_legend_widget
)

__all__ = [
    'InsightWorker', 'StatsWorker',
    'create_donut_figure', 'create_line_chart_figure',
    'fig_to_pixmap', 'fig_to_label', 'fig_to_canvas', 'create_legend_widget'
]

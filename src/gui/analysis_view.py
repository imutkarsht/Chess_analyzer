"""
Analysis View Facade - Imports and re-exports components of the analysis view.
"""
from .analysis.move_list_panel import MoveListPanel
from .analysis.analysis_panel import AnalysisPanel

__all__ = [
    'MoveListPanel',
    'AnalysisPanel',
]

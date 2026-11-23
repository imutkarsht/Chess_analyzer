"""
Analysis View Facade - Imports and re-exports components of the analysis view.
"""
from src.gui.analysis.analysis_panel import AnalysisPanel
from src.gui.analysis.moves.panel import MoveListPanel

__all__ = [
    'MoveListPanel',
    'AnalysisPanel',
]

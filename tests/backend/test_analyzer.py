import pytest
from src.backend.analyzer import Analyzer
from src.backend.models import GameAnalysis, GameMetadata, MoveAnalysis
from src.backend.engine import EngineManager

def test_analyzer_init(mock_engine):
    """Test Analyzer initialization."""
    engine_manager = EngineManager("dummy_path")
    engine_manager.engine = mock_engine
    analyzer = Analyzer(engine_manager)
    assert analyzer is not None

def test_get_win_probability(mock_engine):
    """Test win probability calculation."""
    engine_manager = EngineManager("dummy_path")
    analyzer = Analyzer(engine_manager)
    
    # Test CP values
    assert 0.4 < analyzer.get_win_probability(0, None) < 0.6  # Equal position
    assert analyzer.get_win_probability(100, None) > 0.5      # White advantage
    assert analyzer.get_win_probability(-100, None) < 0.5     # Black advantage
    
    # Test Mate values
    assert analyzer.get_win_probability(None, 1) > 0.9        # Mate in 1 for White
    assert analyzer.get_win_probability(None, -1) < 0.1       # Mate in 1 for Black

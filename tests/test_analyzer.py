import pytest
from unittest.mock import MagicMock, patch
from src.backend.analyzer import Analyzer
from src.backend.models import GameAnalysis, MoveAnalysis
from src.backend.engine import EngineManager

@pytest.fixture
def mock_engine_manager():
    manager = MagicMock(spec=EngineManager)
    # Mock analyze_position to return dummy data
    manager.analyze_position.return_value = [
        {"score": MagicMock(relative=MagicMock(score=lambda mate_score: 50, mate=lambda: None)), "pv": []}
    ]
    return manager

@pytest.fixture
def analyzer(mock_engine_manager):
    return Analyzer(mock_engine_manager)

def test_win_probability_calculation(analyzer):
    # Test CP values
    assert analyzer.get_win_probability(0, None) == 0.5
    assert analyzer.get_win_probability(100, None) > 0.5
    assert analyzer.get_win_probability(-100, None) < 0.5
    
    # Test Mate values
    assert analyzer.get_win_probability(None, 1) == 1.0
    assert analyzer.get_win_probability(None, -1) == 0.0

def test_analyze_game_structure(analyzer):
    # Create a dummy game
    from src.backend.models import GameMetadata
    game = GameAnalysis(game_id="test_game", metadata=GameMetadata(white="W", black="B", date="2023.01.01"))
    
    # Add a dummy move
    move = MoveAnalysis(
        move_number=1,
        ply=1,
        san="e4",
        uci="e2e4",
        fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    )
    game.moves.append(move)
    
    # Mock cache to return None (force engine use) or mock it
    with patch.object(analyzer.cache, 'get_analysis', return_value=None):
        with patch.object(analyzer.cache, 'save_analysis'):
             analyzer.analyze_game(game)
    
    assert analyzer.engine_manager.start_engine.called
    assert analyzer.engine_manager.stop_engine.called
    assert game.summary is not None
    assert "white" in game.summary
    assert "black" in game.summary

import pytest
from src.backend.analysis.analyzer import Analyzer
from src.backend.storage.models import GameAnalysis, GameMetadata, MoveAnalysis
from src.backend.analysis.engine import EngineManager

def test_analyzer_init(mock_engine):
    """Test Analyzer initialization."""
    engine_manager = EngineManager("dummy_path")
    engine_manager.engine = mock_engine
    analyzer = Analyzer(engine_manager)
    assert analyzer is not None

from src.backend.analysis.math_utils import get_win_probability

def test_get_win_probability():
    """Test win probability calculation."""
    # Test CP values
    assert 0.4 < get_win_probability(0, None) < 0.6  # Equal position
    assert get_win_probability(100, None) > 0.5      # White advantage
    assert get_win_probability(-100, None) < 0.5     # Black advantage
    
    # Test Mate values
    assert get_win_probability(None, 1) > 0.9        # Mate in 1 for White
    assert get_win_probability(None, -1) < 0.1       # Mate in 1 for Black

def test_process_analysis_results(mock_engine):
    import chess
    engine_manager = EngineManager("dummy_path")
    analyzer = Analyzer(engine_manager)
    
    move_data = MoveAnalysis(
        move_number=1,
        ply=1,
        san="e4",
        uci="e2e4",
        fen_before=chess.STARTING_FEN
    )
    
    info_list = [
        {
            "pv": [chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")],
            "score": chess.engine.PovScore(chess.engine.Cp(32), chess.WHITE),
            "depth": 15
        }
    ]
    
    board = chess.Board()
    analyzer._process_analysis_results(move_data, info_list, is_white_turn=True, board=board)
    
    assert len(move_data.multi_pvs) == 1
    pv_data = move_data.multi_pvs[0]
    assert pv_data["depth"] == 15
    assert pv_data["pv_san"] == "1. e4 e5"
    assert pv_data["score_value"] == "0.32"

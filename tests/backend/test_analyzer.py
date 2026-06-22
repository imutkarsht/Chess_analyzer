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

def test_classify_move():
    """Test move classification logic in move_classifier.py."""
    from src.backend.analysis.move_classifier import classify_move
    
    # 1. Test checkmate SAN ends with '#'
    move = MoveAnalysis(move_number=1, ply=1, san="Qcb7#", uci="c6b7", fen_before="")
    classify_move(move, wpl=0.5, side="white")
    assert move.classification == "Best"
    assert move.explanation == "Delivered checkmate!"
    
    # 2. Test Missed opportunity (Miss) - solid advantage (>=65%) to equal/worse (<55%)
    move = MoveAnalysis(
        move_number=2, ply=2, san="Nxf4", uci="d5f4", fen_before="",
        win_chance_before=0.70, win_chance_after=0.50
    )
    classify_move(move, wpl=0.20, side="white")
    assert move.classification == "Miss"
    assert "Missed opportunity" in move.explanation

    # 3. Test thresholds: Good (wpl = 3.5%)
    move = MoveAnalysis(move_number=3, ply=3, san="a6", uci="a7a6", fen_before="")
    classify_move(move, wpl=0.035, side="white")
    assert move.classification == "Good"
    
    # 4. Test thresholds: Excellent (wpl = 2.5%)
    move = MoveAnalysis(move_number=4, ply=4, san="b6", uci="b7b6", fen_before="")
    classify_move(move, wpl=0.025, side="white")
    assert move.classification == "Excellent"

    # 5. Test thresholds: Inaccuracy (wpl = 7%)
    move = MoveAnalysis(move_number=5, ply=5, san="c6", uci="c7c6", fen_before="")
    classify_move(move, wpl=0.07, side="white")
    assert move.classification == "Inaccuracy"

    # 6. Test checkmate delay (mate in 3 to mate in 15) -> Best (since forced mate is maintained, not missed)
    move = MoveAnalysis(
        move_number=6, ply=6, san="Qf6+", uci="f7f6", fen_before="",
        eval_before_mate=3, eval_after_mate=15
    )
    classify_move(move, wpl=0.0, side="white")
    assert move.classification == "Best"

    # 6.5. Test losing mate entirely (mate in 3 to normal cp 150) -> Miss
    move = MoveAnalysis(
        move_number=6, ply=6, san="Qf6+", uci="f7f6", fen_before="",
        eval_before_mate=3, eval_after_mate=None, eval_before_cp=300, eval_after_cp=150
    )
    classify_move(move, wpl=0.10, side="white")
    assert move.classification == "Miss"
    assert move.explanation == "Missed a forced checkmate."

    # 7. Test blunder condition: WPL 20%, win chance after 55% -> Mistake (not lost)
    move = MoveAnalysis(
        move_number=7, ply=7, san="b6", uci="b7b6", fen_before="",
        win_chance_before=0.75, win_chance_after=0.55
    )
    classify_move(move, wpl=0.20, side="white")
    assert move.classification == "Mistake"

    # 8. Test blunder condition: WPL 25%, win chance after 40% -> Blunder (lost)
    move = MoveAnalysis(
        move_number=8, ply=8, san="b6", uci="b7b6", fen_before="",
        win_chance_before=0.65, win_chance_after=0.40
    )
    classify_move(move, wpl=0.25, side="white")
    assert move.classification == "Blunder"

    # 9. Test blunder condition: WPL 35%, win chance after 60% -> Blunder (extreme drop)
    move = MoveAnalysis(
        move_number=9, ply=9, san="b6", uci="b7b6", fen_before="",
        win_chance_before=0.95, win_chance_after=0.60
    )
    classify_move(move, wpl=0.35, side="white")
    assert move.classification == "Blunder"

    # 10. Test WPL safety guard: even if move is the engine's best_move,
    # if it drops win chance by >= 5%, it should not be Best (should be Mistake/Blunder/Miss)
    move = MoveAnalysis(
        move_number=10, ply=10, san="Nf5+", uci="g3f5", best_move="g3f5", fen_before="",
        win_chance_before=0.75, win_chance_after=0.50
    )
    classify_move(move, wpl=0.25, side="white")
    assert move.classification == "Miss"  # WPL 25%, win_chance_before > 70% -> Missed winning opportunity

def test_drawing_repetition_protection(mock_engine):
    """Test that drawing repetition moves in a drawn game are protected."""
    import chess
    engine_manager = EngineManager("dummy_path")
    engine_manager.engine = mock_engine
    analyzer = Analyzer(engine_manager)
    
    # Create a simple game ending in a draw by repetition
    metadata = GameMetadata(
        white="Player1", black="Player2",
        result="1/2-1/2", date="2026.06.21"
    )
    
    # We will simulate a simple repetition:
    # 1. Nf3 Nf6 2. Ng1 Ng8 3. Nf3 Nf6 4. Ng1
    board = chess.Board()
    uci_moves = ["g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1"]
    san_moves = ["Nf3", "Nf6", "Ng1", "Ng8", "Nf3", "Nf6", "Ng1"]
    
    moves = []
    for i, (uci, san) in enumerate(zip(uci_moves, san_moves)):
        moves.append(MoveAnalysis(
            move_number=(i // 2) + 1,
            ply=i,
            san=san,
            uci=uci,
            fen_before=board.fen()
        ))
        board.push_uci(uci)
    
    # Let's fake evaluations so we would normally have blunders (e.g. going from +5.00 to 0.0)
    for m in moves:
        m.eval_before_cp = 500  # +5.00
        m.eval_before_mate = None
    
    # Set the last move's next eval (which is final_score)
    final_score = chess.engine.PovScore(chess.engine.Cp(0), chess.WHITE)
    
    game = GameAnalysis(
        game_id="fake_game_123",
        metadata=metadata,
        moves=moves
    )
    
    summary_counts = {
        "white": {"Brilliant": 0, "Great": 0, "Best": 0, "Excellent": 0, "Good": 0, "Inaccuracy": 0, "Mistake": 0, "Blunder": 0, "Miss": 0, "Book": 0, "acpl": 0, "move_count": 0, "accuracies": [], "win_percents": []},
        "black": {"Brilliant": 0, "Great": 0, "Best": 0, "Excellent": 0, "Good": 0, "Inaccuracy": 0, "Mistake": 0, "Blunder": 0, "Miss": 0, "Book": 0, "acpl": 0, "move_count": 0, "accuracies": [], "win_percents": []}
    }
    
    # Run classification
    analyzer._classify_and_calculate_stats(game, summary_counts, final_score)
    
    # Let's check classifications of the repeating moves (ply 4, 5, 6)
    # They should be protected (WPL capped to 0), so they should be classified as Best/Excellent, NOT Blunder/Mistake.
    assert game.moves[4].classification in ["Best", "Excellent"]
    assert game.moves[5].classification in ["Best", "Excellent"]
    assert game.moves[6].classification in ["Best", "Excellent"]

def test_analyzer_progress_logging(caplog, mocker, mock_engine):
    """Test that analyzer logs move progress after gap of 10 moves."""
    import logging
    engine_manager = EngineManager("dummy_path")
    engine_manager.engine = mock_engine
    analyzer = Analyzer(engine_manager)
    
    mocker.patch.object(analyzer, '_get_position_analysis', return_value=[])
    mocker.patch.object(analyzer, '_analyze_final_position', return_value=None)
    mocker.patch.object(analyzer, '_classify_and_calculate_stats')
    mocker.patch.object(analyzer, '_calculate_final_accuracy')
    mocker.patch.object(analyzer, '_log_classification_summary')
    mocker.patch.object(engine_manager, 'start_engine')
    mocker.patch.object(engine_manager, 'stop_engine')
    
    moves = [
        MoveAnalysis(
            move_number=(i // 2) + 1,
            ply=i,
            san="e4",
            uci="e2e4",
            fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        )
        for i in range(25)
    ]
    metadata = GameMetadata(white="W", black="B", result="*", date="2026.06.21")
    game = GameAnalysis(game_id="log_test", metadata=metadata, moves=moves)
    
    with caplog.at_level(logging.INFO):
        analyzer._analyze_positions(game)
        
    log_messages = [rec.message for rec in caplog.records]
    assert "Analyzing move 1/25..." in log_messages
    assert "Analyzing move 10/25..." in log_messages
    assert "Analyzing move 20/25..." in log_messages
    assert "Analyzing move 25/25..." in log_messages
    
    # Ensure moves in between are not logged
    assert not any("Analyzing move 2/25..." in msg for msg in log_messages)
    assert not any("Analyzing move 11/25..." in msg for msg in log_messages)



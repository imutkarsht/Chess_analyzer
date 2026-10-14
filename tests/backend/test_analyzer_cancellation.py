"""Tests for Analyzer cancellation and partial analysis preservation."""

import threading
from unittest.mock import MagicMock

import chess

from src.backend.analysis.analyzer import Analyzer
from src.backend.analysis.engine import EngineManager
from src.backend.storage.models import GameAnalysis, GameMetadata, MoveAnalysis


def test_analyzer_cancellation_preserves_partial_results(mocker):
    """When cancel_token is set mid-game, analyzer stops early and preserves analyzed moves."""
    engine_manager = EngineManager("dummy_path")
    mock_engine = MagicMock()
    engine_manager.engine = mock_engine
    analyzer = Analyzer(engine_manager)

    mocker.patch.object(engine_manager, "start_engine")
    mocker.patch.object(engine_manager, "stop_engine")

    # Create a 4-move game
    moves = [
        MoveAnalysis(move_number=1, ply=1, san="e4", uci="e2e4", fen_before=chess.STARTING_FEN),
        MoveAnalysis(
            move_number=1,
            ply=2,
            san="e5",
            uci="e7e5",
            fen_before="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
        ),
        MoveAnalysis(
            move_number=2,
            ply=3,
            san="Nf3",
            uci="g1f3",
            fen_before="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2",
        ),
        MoveAnalysis(
            move_number=2,
            ply=4,
            san="Nc6",
            uci="b8c6",
            fen_before="rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
        ),
    ]
    game = GameAnalysis(
        game_id="partial_test",
        metadata=GameMetadata(white="White", black="Black", result="*"),
        moves=moves,
    )

    cancel_token = threading.Event()
    analyzed_calls = 0

    def fake_get_position_analysis(board, move_data):
        nonlocal analyzed_calls
        analyzed_calls += 1
        if analyzed_calls == 2:
            cancel_token.set()
        return [
            {
                "score": chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE),
                "pv": [chess.Move.from_uci("e2e4")],
            }
        ]

    mocker.patch.object(analyzer, "_get_position_analysis", side_effect=fake_get_position_analysis)

    analyzer.analyze_game(game, cancel_token=cancel_token)

    # Moves 0 and 1 were analyzed, moves 2 and 3 were skipped
    assert game.moves[0].eval_before_cp is not None
    assert game.moves[1].eval_before_cp is not None
    assert game.moves[2].eval_before_cp is None
    assert game.moves[3].eval_before_cp is None

    # Summary exists and covers the partial moves
    assert game.summary is not None
    assert "white" in game.summary
    assert "black" in game.summary
    assert game.summary["white"]["move_count"] >= 1


def test_engine_manager_cancel_current_analysis():
    """EngineManager.cancel_current_analysis cleanly calls stop on the active analysis."""
    manager = EngineManager("dummy_path")
    mock_analysis = MagicMock()
    manager._current_analysis = mock_analysis

    manager.cancel_current_analysis()

    mock_analysis.stop.assert_called_once()
    assert manager._current_analysis is None

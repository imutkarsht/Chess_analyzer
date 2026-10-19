import chess

from src.backend.analysis.analyzer import Analyzer
from src.backend.analysis.engine import EngineManager
from src.backend.analysis.local_book import BookResult
from src.backend.analysis.math_utils import (
    MIN_MOVE_ACCURACY,
    apply_accuracy_floor,
    calculate_move_accuracy,
)
from src.backend.storage.models import GameAnalysis, GameMetadata, MoveAnalysis


def test_analyzer_init(mock_engine):
    """Test Analyzer initialization."""
    engine_manager = EngineManager("dummy_path")
    engine_manager.engine = mock_engine
    analyzer = Analyzer(engine_manager)
    assert analyzer is not None


def test_process_analysis_results(mock_engine):
    import chess

    engine_manager = EngineManager("dummy_path")
    analyzer = Analyzer(engine_manager)

    move_data = MoveAnalysis(
        move_number=1,
        ply=1,
        san="e4",
        uci="e2e4",
        fen_before=chess.STARTING_FEN,
    )

    info_list = [
        {
            "pv": [chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")],
            "score": chess.engine.PovScore(chess.engine.Cp(32), chess.WHITE),
            "depth": 15,
        }
    ]

    board = chess.Board()
    analyzer._process_analysis_results(move_data, info_list, is_white_turn=True, board=board)

    assert len(move_data.multi_pvs) == 1
    pv_data = move_data.multi_pvs[0]
    assert pv_data["depth"] == 15
    assert pv_data["pv_san"] == "1. e4 e5"
    assert pv_data["score_value"] == "0.32"


def test_drawing_repetition_protection(mock_engine):
    """Test that drawing repetition moves in a drawn game are protected."""
    import chess

    engine_manager = EngineManager("dummy_path")
    engine_manager.engine = mock_engine
    analyzer = Analyzer(engine_manager)

    # Create a simple game ending in a draw by repetition
    metadata = GameMetadata(white="Player1", black="Player2", result="1/2-1/2", date="2026.06.21")

    # We will simulate a simple repetition:
    # 1. Nf3 Nf6 2. Ng1 Ng8 3. Nf3 Nf6 4. Ng1
    board = chess.Board()
    uci_moves = ["g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1"]
    san_moves = ["Nf3", "Nf6", "Ng1", "Ng8", "Nf3", "Nf6", "Ng1"]

    moves = []
    for i, (uci, san) in enumerate(zip(uci_moves, san_moves, strict=False)):
        moves.append(
            MoveAnalysis(move_number=(i // 2) + 1, ply=i, san=san, uci=uci, fen_before=board.fen())
        )
        board.push_uci(uci)

    # Let's fake evaluations so we would normally have blunders (e.g. going from +5.00 to 0.0)
    for m in moves:
        m.eval_before_cp = 500  # +5.00
        m.eval_before_mate = None

    # Set the last move's next eval (which is final_score)
    final_score = chess.engine.PovScore(chess.engine.Cp(0), chess.WHITE)

    game = GameAnalysis(game_id="fake_game_123", metadata=metadata, moves=moves)

    summary_counts = {
        "white": {
            "Brilliant": 0,
            "Great": 0,
            "Best": 0,
            "Excellent": 0,
            "Good": 0,
            "Inaccuracy": 0,
            "Mistake": 0,
            "Blunder": 0,
            "Miss": 0,
            "Book": 0,
            "acpl": 0,
            "move_count": 0,
            "accuracies": [],
            "win_percents": [],
        },
        "black": {
            "Brilliant": 0,
            "Great": 0,
            "Best": 0,
            "Excellent": 0,
            "Good": 0,
            "Inaccuracy": 0,
            "Mistake": 0,
            "Blunder": 0,
            "Miss": 0,
            "Book": 0,
            "acpl": 0,
            "move_count": 0,
            "accuracies": [],
            "win_percents": [],
        },
    }

    # Run classification
    analyzer._classify_and_calculate_stats(game, summary_counts, final_score)

    # Let's check classifications of the repeating moves (ply 4, 5, 6)
    # They should be protected (WPL capped to 0), so they should be classified as Best/Excellent/Book, NOT Blunder/Mistake.
    # Book is also valid since Nf3/Nf6 are common book moves picked up by the improved book detection.
    assert game.moves[4].classification in ["Best", "Excellent", "Book"]
    assert game.moves[5].classification in ["Best", "Excellent", "Book"]
    assert game.moves[6].classification in ["Best", "Excellent", "Book"]


def test_analyzer_progress_logging(caplog, mocker, mock_engine):
    """Test that analyzer logs move progress after gap of 10 moves."""
    import logging

    engine_manager = EngineManager("dummy_path")
    engine_manager.engine = mock_engine
    analyzer = Analyzer(engine_manager)

    mocker.patch.object(analyzer, "_get_position_analysis", return_value=[])
    mocker.patch.object(analyzer, "_analyze_final_position", return_value=None)
    mocker.patch.object(analyzer, "_classify_and_calculate_stats")
    mocker.patch.object(analyzer, "_calculate_final_accuracy")
    mocker.patch.object(analyzer, "_log_classification_summary")
    mocker.patch.object(engine_manager, "start_engine")
    mocker.patch.object(engine_manager, "stop_engine")

    moves = [
        MoveAnalysis(
            move_number=(i // 2) + 1,
            ply=i,
            san="e4",
            uci="e2e4",
            fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
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

    assert not any("Analyzing move 11/25..." in msg for msg in log_messages)


def test_check_book_move_merging(mocker, mock_engine):
    """Test that _check_book_move correctly merges Polyglot and SQLite book results."""
    engine_manager = EngineManager("dummy_path")
    engine_manager.engine = mock_engine
    analyzer = Analyzer(engine_manager)

    # Mock both books
    mock_polyglot = mocker.patch.object(analyzer.polyglot_book, "process_move")
    mock_local = mocker.patch.object(analyzer.local_book, "process_move")

    # Enable polyglot availability
    mocker.patch.object(analyzer.polyglot_book, "is_available", return_value=True)

    # Case 1: Both match
    mock_polyglot.return_value = BookResult(
        is_book=True, book_move_count=3, candidate_moves=["e7e5", "c7c5"]
    )
    mock_local.return_value = BookResult(
        is_book=True,
        book_move_count=2,
        current_eco="C20",
        current_opening="King's Pawn Game",
        candidate_moves=["e7e5"],
    )

    move = MoveAnalysis(move_number=1, ply=1, san="e4", uci="e2e4", fen_before=chess.STARTING_FEN)
    move.classification = "Best"
    summary_counts = {"white": {"Book": 0, "Best": 1}, "black": {"Book": 0, "Best": 0}}
    game_analysis = GameAnalysis(
        game_id="merge_test",
        metadata=GameMetadata(white="W", black="B", result="*", date="2026"),
        moves=[move],
    )

    is_book = analyzer._check_book_move(move, "white", summary_counts, game_analysis)

    assert is_book is True
    assert move.classification == "Book"
    assert move.is_book_move is True
    assert move.book_move_count == 3  # max(3, 2)
    assert move.candidate_continuations == ["e7e5", "c7c5"]  # Polyglot candidates preferred
    assert move.eco == "C20"  # from SQLite
    assert move.opening_name == "King's Pawn Game"  # from SQLite
    assert summary_counts["white"]["Book"] == 1
    assert summary_counts["white"]["Best"] == 0
    assert game_analysis.metadata.opening == "King's Pawn Game"
    assert game_analysis.metadata.eco == "C20"


def _side(accs: list[float]) -> dict:
    return {
        "accuracies": accs,
        "win_percents": [0.5] * len(accs),
        "move_count": len(accs),
        "acpl": 0,
    }


def test_mate_blunder_hits_accuracy_floor():
    acc = apply_accuracy_floor(calculate_move_accuracy(0.9, 0.0))
    assert acc == MIN_MOVE_ACCURACY == 10.0


def test_single_blunder_does_not_collapse_accuracy():
    blunder = apply_accuracy_floor(calculate_move_accuracy(0.9, 0.0))
    counts = {"white": _side([95.0] * 39 + [blunder]), "black": _side([95.0] * 40)}
    Analyzer._calculate_final_accuracy(None, counts)
    assert 80 < counts["white"]["accuracy"] < counts["black"]["accuracy"]


def test_analyzer_resume_skips_already_analyzed_moves(mocker, tmp_path):
    """Test that analyzer with resume=True resumes from first unanalyzed move."""
    from src.backend.storage.game_history import GameHistoryManager

    db_path = str(tmp_path / "resume_test.db")
    history_mgr = GameHistoryManager(db_path)

    engine_manager = EngineManager("dummy_path")
    analyzer = Analyzer(engine_manager)
    analyzer.history_manager = history_mgr

    mocker.patch.object(engine_manager, "start_engine")
    mocker.patch.object(engine_manager, "stop_engine")

    mock_score = chess.engine.PovScore(chess.engine.Cp(25), chess.WHITE)
    mocker.patch.object(
        analyzer,
        "_get_position_analysis",
        return_value=[{"pv": [chess.Move.from_uci("g1f3")], "score": mock_score, "depth": 10}],
    )
    mocker.patch.object(analyzer, "_analyze_final_position", return_value=mock_score)

    m1 = MoveAnalysis(
        move_number=1,
        ply=1,
        san="e4",
        uci="e2e4",
        fen_before=chess.STARTING_FEN,
        eval_before_cp=20,
        eval_after_cp=20,
        classification="Book",
    )
    b2 = chess.Board()
    b2.push_san("e4")
    m2 = MoveAnalysis(
        move_number=1,
        ply=2,
        san="e5",
        uci="e7e5",
        fen_before=b2.fen(),
        eval_before_cp=20,
        eval_after_cp=25,
        classification="Book",
    )
    b3 = b2.copy()
    b3.push_san("e5")
    m3 = MoveAnalysis(
        move_number=2,
        ply=3,
        san="Nf3",
        uci="g1f3",
        fen_before=b3.fen(),
    )
    game = GameAnalysis(
        game_id="resume_game",
        metadata=GameMetadata(white="W", black="B", result="*"),
        moves=[m1, m2, m3],
        pgn_content="1. e4 e5 2. Nf3 *",
    )

    analyzer.analyze_game(game, resume=True)

    # Move 3 was evaluated
    assert m3.eval_before_cp is not None
    assert game.status == "completed"
    assert game.summary.get("analysis_status") == "completed"
    # And saved to history manager
    saved = history_mgr.get_game("resume_game")
    assert saved is not None


def test_analyzer_persists_paused_on_cancellation(mocker, tmp_path):
    """Test that analyzer persists partial progress with paused status on cancel."""
    import threading

    from src.backend.storage.game_history import GameHistoryManager

    db_path = str(tmp_path / "cancel_test.db")
    history_mgr = GameHistoryManager(db_path)

    engine_manager = EngineManager("dummy_path")
    analyzer = Analyzer(engine_manager)
    analyzer.history_manager = history_mgr

    mocker.patch.object(engine_manager, "start_engine")
    mocker.patch.object(engine_manager, "stop_engine")

    mock_score = chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE)
    mocker.patch.object(
        analyzer,
        "_get_position_analysis",
        return_value=[{"pv": [chess.Move.from_uci("e2e4")], "score": mock_score, "depth": 10}],
    )

    cancel_token = threading.Event()

    def callback(current, total, data=None):
        if current >= 1:
            cancel_token.set()

    m1 = MoveAnalysis(move_number=1, ply=1, san="e4", uci="e2e4", fen_before=chess.STARTING_FEN)
    b2 = chess.Board()
    b2.push_san("e4")
    m2 = MoveAnalysis(move_number=1, ply=2, san="e5", uci="e7e5", fen_before=b2.fen())

    game = GameAnalysis(
        game_id="cancel_game",
        metadata=GameMetadata(white="W", black="B", result="*"),
        moves=[m1, m2],
        pgn_content="1. e4 e5 *",
    )

    analyzer.analyze_game(game, callback=callback, cancel_token=cancel_token)

    assert game.summary.get("analysis_status") == "paused"
    saved = history_mgr.get_game("cancel_game")
    assert saved is not None


def test_analyzer_pause_and_resume_never_skips_move(mocker, tmp_path):
    """Test that pausing when a move has partial eval does not skip it on resume."""
    from src.backend.storage.game_history import GameHistoryManager

    db_path = str(tmp_path / "pause_resume_test.db")
    history_mgr = GameHistoryManager(db_path)

    engine_manager = EngineManager("dummy_path")
    analyzer = Analyzer(engine_manager)
    analyzer.history_manager = history_mgr

    mocker.patch.object(engine_manager, "start_engine")
    mocker.patch.object(engine_manager, "stop_engine")

    mock_score = chess.engine.PovScore(chess.engine.Cp(25), chess.WHITE)
    mocker.patch.object(
        analyzer,
        "_get_position_analysis",
        return_value=[{"pv": [chess.Move.from_uci("g1f3")], "score": mock_score, "depth": 10}],
    )
    mocker.patch.object(analyzer, "_analyze_final_position", return_value=mock_score)

    # 4-move game
    b = chess.Board()
    moves = []
    for num, san in [(1, "e4"), (1, "e5"), (2, "Nf3"), (2, "Nc6")]:
        uci = b.parse_san(san).uci()
        moves.append(
            MoveAnalysis(move_number=num, ply=len(moves) + 1, san=san, uci=uci, fen_before=b.fen())
        )
        b.push_san(san)

    # Simulate pause: move 0 was classified, move 1 had partial eval_before_cp but was NOT classified
    moves[0].eval_before_cp = 20
    moves[0].eval_after_cp = 20
    moves[0].classification = "Book"
    moves[1].eval_before_cp = 20  # Partial eval before cancellation!
    moves[1].classification = ""  # Not classified yet

    game = GameAnalysis(
        game_id="skip_test_game",
        metadata=GameMetadata(white="W", black="B", result="*"),
        moves=moves,
        pgn_content="1. e4 e5 2. Nf3 Nc6 *",
    )

    # Must resume from index 1 (move 1), NOT skip to index 2!
    assert game.first_unanalyzed_index == 1

    reported_indices = []

    def callback(current, total, data=None):
        if data and "index" in data:
            reported_indices.append(data["index"])

    analyzer.analyze_game(game, callback=callback, resume=True)

    # All moves must be classified and have evaluations
    for idx, m in enumerate(game.moves):
        assert m.eval_before_cp is not None, f"Move {idx} ({m.san}) missing eval_before_cp"
        assert m.eval_after_cp is not None, f"Move {idx} ({m.san}) missing eval_after_cp"
        assert m.classification, f"Move {idx} ({m.san}) missing classification"

    # All moves from index 1 onwards must have been reported
    assert 1 in reported_indices, "Move 1 was skipped in callback updates!"
    assert 2 in reported_indices, "Move 2 was skipped in callback updates!"
    assert 3 in reported_indices, "Move 3 was skipped in callback updates!"
    assert game.status == "completed"

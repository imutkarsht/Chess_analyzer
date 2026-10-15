"""
Unit tests for tactics analysis: hanging piece detection, game phase classification,
and advantage conversion tracking.
"""

import chess

from src.backend.analysis.tactics import (
    analyze_game_tactics,
    classify_game_phase,
    get_hanging_pieces,
)


def test_hanging_piece_undefended():
    """Test that an undefended piece under attack is detected as hanging."""
    # 1. e4 e5 2. Nf3 (Nf3 attacks undefended e5)
    board = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2")
    hanging = get_hanging_pieces(board, chess.BLACK)
    hanging_sqs = [h["square"] for h in hanging]
    assert "e5" in hanging_sqs
    e5_item = next(h for h in hanging if h["square"] == "e5")
    assert e5_item["is_undefended"] is True
    assert e5_item["piece_name"] == "pawn"


def test_hanging_piece_attacked_by_lesser_value():
    """Test that a defended Queen attacked by a lower-value Bishop is detected as hanging."""
    # Queen on d4 defended by pawn on c3, but attacked by Bishop on b6
    board = chess.Board("rn1qk1nr/ppp1bppp/1b6/8/3q4/2P5/PP2PPPP/RNB1KBNR w KQkq - 0 5")
    hanging = get_hanging_pieces(board, chess.BLACK)
    hanging_sqs = [h["square"] for h in hanging]
    assert "d4" in hanging_sqs
    d4_item = next(h for h in hanging if h["square"] == "d4")
    assert d4_item["attacked_by_lesser"] is True
    assert d4_item["piece_name"] == "queen"


def test_defended_equal_exchange_not_hanging():
    """Test that an equally defended piece attacked by equal value is NOT hanging."""
    # Knight on d4 defended by pawn c3, attacked by Knight on c6
    board = chess.Board("r1bqkb1r/pppp1ppp/2n5/8/3N4/2P5/PPP1PPPP/R1BQKB1R w KQkq - 1 5")
    hanging = get_hanging_pieces(board, chess.WHITE)
    hanging_sqs = [h["square"] for h in hanging]
    # d4 is defended by c3 (1 defender) and attacked by c6 (1 attacker of equal value) -> not hanging
    assert "d4" not in hanging_sqs


def test_king_never_marked_hanging():
    """Test that King in check is NOT classified as a hanging piece."""
    # White king in check from Queen on e8 to e1
    board = chess.Board("4q3/8/8/8/8/8/8/4K3 w - - 0 1")
    hanging = get_hanging_pieces(board, chess.WHITE)
    assert len(hanging) == 0


def test_classify_game_phase_opening():
    """Test opening phase classification."""
    board = chess.Board()
    assert classify_game_phase(board, ply=4, is_book_move=True) == "opening"
    assert classify_game_phase(board, ply=10, is_book_move=False) == "opening"


def test_classify_game_phase_endgame():
    """Test endgame phase classification."""
    # Rook endgame with no queens
    board = chess.Board("8/4k3/8/8/8/4K3/4R3/4r3 w - - 0 1")
    assert classify_game_phase(board, ply=50, is_book_move=False) == "endgame"


def test_classify_game_phase_middlegame():
    """Test middlegame phase classification."""
    # Position out of book with queens and minor pieces
    board = chess.Board("r1bq1rk1/pp2bppp/2n1pn2/2pp4/2PP4/2N1PN2/PP2BPPP/R1BQ1RK1 w - - 4 8")
    assert classify_game_phase(board, ply=22, is_book_move=False) == "middlegame"


def test_analyze_game_tactics_advantage_conversion():
    """Test that advantage conversion and brilliancy tracking work correctly."""
    moves_data = [
        {
            "ply": 1,
            "move_number": 1,
            "san": "e4",
            "uci": "e2e4",
            "fen_before": chess.STARTING_FEN,
            "eval_before_cp": 20,
            "win_chance_before": 0.52,
            "win_chance_after": 0.53,
            "classification": "Best",
            "is_book_move": True,
        },
        {
            "ply": 2,
            "move_number": 1,
            "san": "e5",
            "uci": "e7e5",
            "fen_before": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            "eval_before_cp": 20,
            "win_chance_before": 0.47,
            "win_chance_after": 0.48,
            "classification": "Best",
            "is_book_move": True,
        },
        {
            "ply": 3,
            "move_number": 2,
            "san": "Qh5",
            "uci": "d1h5",
            "fen_before": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2",
            "eval_before_cp": 350,  # Winning advantage
            "win_chance_before": 0.85,
            "win_chance_after": 0.88,
            "classification": "Brilliant",
            "explanation": "Sacrificial tactical strike",
            "is_book_move": False,
        },
    ]

    tactics = analyze_game_tactics(moves_data, user_color="white", result="1-0")

    # Adv metrics
    adv = tactics["advantage_metrics"]
    assert adv["had_winning_advantage"] is True
    assert adv["converted_advantage"] is True
    assert adv["choked_advantage"] is False

    # Brilliancies
    brilliancies = tactics["brilliancies"]
    assert len(brilliancies) == 1
    assert brilliancies[0]["san"] == "Qh5"
    assert brilliancies[0]["classification"] == "Brilliant"

    # Phase accuracies
    phase_acc = tactics["phase_accuracies"]
    assert phase_acc["opening"] is not None

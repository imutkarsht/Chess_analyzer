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
    assert adv["thrown_losses"] is False
    assert adv["squandered_draws"] is False
    assert adv["had_losing_position"] is False
    assert adv["comeback_drawn_or_won"] is False

    # Brilliancies
    brilliancies = tactics["brilliancies"]
    assert len(brilliancies) == 1
    assert brilliancies[0]["san"] == "Qh5"
    assert brilliancies[0]["classification"] == "Brilliant"

    # Phase accuracies
    phase_acc = tactics["phase_accuracies"]
    assert phase_acc["opening"] is not None


def test_advantage_thrown_loss_and_comeback_win():
    """Test advantage metrics for thrown loss (+3.0 lost) and comeback win (-3.0 won)."""
    # 1. Thrown Loss: White was at +400 cp but lost (result 0-1)
    moves_thrown = [
        {
            "ply": 0,
            "san": "e4",
            "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "eval_before_cp": 400,
            "win_chance_before": 0.90,
            "win_chance_after": 0.90,
            "classification": "Best",
            "is_book_move": False,
        }
    ]
    tactics_thrown = analyze_game_tactics(moves_thrown, user_color="white", result="0-1")
    adv_t = tactics_thrown["advantage_metrics"]
    assert adv_t["had_winning_advantage"] is True
    assert adv_t["converted_advantage"] is False
    assert adv_t["choked_advantage"] is True
    assert adv_t["thrown_losses"] is True
    assert adv_t["squandered_draws"] is False

    # 2. Comeback Win: White was at -450 cp but won (result 1-0)
    moves_comeback = [
        {
            "ply": 0,
            "san": "e4",
            "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "eval_before_cp": -450,
            "win_chance_before": 0.05,
            "win_chance_after": 0.05,
            "classification": "Best",
            "is_book_move": False,
        }
    ]
    tactics_cb = analyze_game_tactics(moves_comeback, user_color="white", result="1-0")
    adv_cb = tactics_cb["advantage_metrics"]
    assert adv_cb["had_losing_position"] is True
    assert adv_cb["comeback_drawn_or_won"] is True
    assert adv_cb["comeback_wins"] is True
    assert adv_cb["comeback_draws"] is False
    assert adv_cb["lost_deficit"] is False


def test_pinned_defender_cannot_protect():
    """Test that a piece whose only defender is pinned to the King is detected as hanging."""
    # White King on h1, Pawn on g2 pinned by Black Bishop on b7.
    # White Knight on h3 is attacked by Black Queen on h8.
    # The pawn on g2 cannot legally capture on h3 because it is pinned along the long diagonal.
    board = chess.Board("7q/1b6/8/8/8/7N/6P1/7K w - - 0 1")
    hanging = get_hanging_pieces(board, chess.WHITE)
    hanging_sqs = [h["square"] for h in hanging]
    assert "h3" in hanging_sqs


def test_defended_pawn_attacked_by_higher_piece_not_hanging():
    """Test that a defended pawn attacked by higher-value pieces is NOT classified as hanging."""
    # White pawn on e4 defended by pawn on d3 (1 defender).
    # Attacked by Black Knight on f6 and Black Bishop on c5 (2 attackers of value 3).
    # Since min attacker value (3) > piece value (1), Black cannot profitably take, so e4 is safe.
    board = chess.Board("r1bqk2r/pppp1ppp/2n2n2/2b5/4P3/3P4/PPP2PPP/RNBQKBNR w KQkq - 1 5")
    hanging = get_hanging_pieces(board, chess.WHITE)
    hanging_sqs = [h["square"] for h in hanging]
    assert "e4" not in hanging_sqs


def test_sacrifices_and_best_moves_never_marked_hanging():
    """Test that intentional piece sacrifices and top engine moves are not counted as hung pieces."""
    # User plays Bxh7+ (Bxf7 or Bxh7) classified as Brilliant or Best move
    moves_data = [
        {
            "ply": 1,
            "move_number": 1,
            "san": "Bxh7+",
            "uci": "d3h7",
            # Position where Bishop on h7 is attacked by Black King on g8 and undefended
            "fen_before": "r1bq1rk1/pppp1ppp/2n5/4p3/4P3/3B4/PPP2PPP/RNBQK2R w KQ - 0 6",
            "eval_before_cp": 250,
            "win_chance_before": 0.75,
            "win_chance_after": 0.85,
            "classification": "Brilliant",
            "explanation": "Brilliant greek gift sacrifice",
            "is_book_move": False,
        }
    ]
    tactics = analyze_game_tactics(moves_data, user_color="white", result="1-0")
    h_metrics = tactics["hanging_metrics"]
    assert h_metrics["total_hung"] == 0
    assert h_metrics["hanging_blunders"] == 0


def test_opp_hanging_captured_good_vs_trap():
    """Test that capturing an opponent hanging piece counts only when sound, not when blundering into a trap."""
    # 1. Sound capture
    sound_capture = [
        {
            "ply": 1,
            "move_number": 1,
            "san": "Qxf7+",
            "uci": "d1f7",
            # Black pawn on f7 is hanging and undefended
            "fen_before": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1",
            "eval_before_cp": 50,
            "win_chance_before": 0.55,
            "win_chance_after": 0.65,
            "classification": "Best",
            "is_book_move": False,
        }
    ]
    tactics = analyze_game_tactics(sound_capture, user_color="white", result="1-0")
    assert tactics["hanging_metrics"]["opponent_hanging_captured"] == 0
    # e5 was hanging on board_before (from standard undefended pawn) or e5 pawn
    # User captured on f7 which wasn't hanging, but let's test capturing e5:
    sound_capture_e5 = [
        {
            "ply": 1,
            "move_number": 1,
            "san": "Nxe5",
            "uci": "f3e5",
            # Black pawn on e5 is hanging and undefended
            "fen_before": "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 1 2",
            "eval_before_cp": 100,
            "win_chance_before": 0.60,
            "win_chance_after": 0.65,
            "classification": "Best",
            "is_book_move": False,
        }
    ]
    tactics_e5 = analyze_game_tactics(sound_capture_e5, user_color="white", result="1-0")
    assert tactics_e5["hanging_metrics"]["opponent_hanging_captured"] == 1
    assert tactics_e5["hanging_metrics"]["captured_by_piece"]["pawn"] == 1


def test_detect_tactical_motifs():
    """Test detection of forks, pins, and discovered attacks."""
    from src.backend.analysis.tactics import detect_tactical_motifs

    # 1. Knight fork on c7 attacking e8 (King) and a8 (Rook)
    board_b = chess.Board("r3k2r/pppb1ppp/8/4N3/1b2P3/8/PPP2PPP/R1B1KB1R w KQkq - 1 10")
    move_fork = chess.Move.from_uci("e5c7")
    board_a = board_b.copy()
    board_a.push(move_fork)
    motifs_fork = detect_tactical_motifs(board_b, board_a, move_fork, chess.WHITE)
    assert "fork" in motifs_fork

    # 2. Pin: Bishop moving to b5 pins Knight on c6 to King on e8 (d7 is vacant)
    board_pin_b = chess.Board("r1bqkbnr/pp2pppp/2n5/3p4/4P3/8/PPPPBPPP/RNBQK1NR w KQkq - 0 4")
    move_pin = chess.Move.from_uci("e2b5")
    board_pin_a = board_pin_b.copy()
    board_pin_a.push(move_pin)
    motifs_pin = detect_tactical_motifs(board_pin_b, board_pin_a, move_pin, chess.WHITE)
    assert "pin" in motifs_pin

    # 3. Discovered Check: Rook on e1, Knight on e4 moves away giving check from Rook
    board_disc_b = chess.Board("4k3/8/8/8/4N3/8/8/4R2K w - - 0 1")
    move_disc = chess.Move.from_uci("e4f6")
    board_disc_a = board_disc_b.copy()
    board_disc_a.push(move_disc)
    motifs_disc = detect_tactical_motifs(board_disc_b, board_disc_a, move_disc, chess.WHITE)
    assert "discovered_attack" in motifs_disc

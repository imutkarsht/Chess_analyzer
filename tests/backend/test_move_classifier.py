"""Tests for move classification bands and mathematical win probability calculation."""

from src.backend.analysis.math_utils import calculate_move_accuracy, get_win_probability
from src.backend.analysis.move_classifier import classify_move
from src.backend.storage.models import MoveAnalysis


def test_win_probability_calculations():
    """Win probability maps centipawns and mate scores to 0.0-1.0."""
    # Equal position = 50%
    assert abs(get_win_probability(0, None) - 0.5) < 0.01

    # Large white advantage (~+500 cp) -> ~85%+
    assert get_win_probability(500, None) > 0.85

    # Large black advantage (~-500 cp) -> ~15%-
    assert get_win_probability(-500, None) < 0.15

    # Forced mate
    assert get_win_probability(None, 1) == 1.0
    assert get_win_probability(None, -1) == 0.0
    assert get_win_probability(None, None) == 0.5


def test_calculate_move_accuracy():
    """Move accuracy properly bounds between 0 and 100%."""
    # No loss in win prob -> 100% accuracy
    assert calculate_move_accuracy(0.5, 0.5) == 100.0
    assert calculate_move_accuracy(0.5, 0.6) == 100.0

    # Minor loss -> high accuracy
    acc = calculate_move_accuracy(0.6, 0.58)
    assert 85.0 < acc <= 100.0

    # Large blunder swing -> low accuracy
    bad_acc = calculate_move_accuracy(0.8, 0.2)
    assert bad_acc < 20.0


def test_classify_checkmate():
    """Delivering checkmate is classified as Best move."""
    move = MoveAnalysis(
        move_number=20,
        ply=40,
        san="Qxf7#",
        uci="d1f7",
        fen_before="start",
        win_chance_before=0.99,
        win_chance_after=1.0,
    )
    classify_move(move, wpl=0.0, side="white")
    assert move.classification == "Best"
    assert "checkmate" in move.explanation.lower()


def test_classify_missed_mate():
    """Missing a forced checkmate is classified as Miss."""
    move = MoveAnalysis(
        move_number=15,
        ply=29,
        san="Be3",
        uci="c1e3",
        fen_before="start",
        win_chance_before=1.0,
        win_chance_after=0.7,
        eval_before_mate=2,
        eval_after_mate=None,
        best_move="d1h5",
    )
    classify_move(move, wpl=0.3, side="white")
    assert move.classification == "Miss"


def test_classify_brilliant_move():
    """A sound piece sacrifice (e.g. Greek gift Bxh7+) is classified as Brilliant."""
    # Classic bishop sacrifice setup:
    # White bishop on d3 sacrifices on h7: 1. Bxh7+ Kxh7
    fen_greek_gift = "r1bq1rk1/pppn1ppp/4p3/3p4/2PP4/2NBPN2/PP3PPP/R1BQK2R w KQ - 0 8"
    move = MoveAnalysis(
        move_number=8,
        ply=15,
        san="Bxh7+",
        uci="d3h7",
        fen_before=fen_greek_gift,
        win_chance_before=0.58,
        win_chance_after=0.75,
        best_move="d3h7",
        eval_before_cp=50,
        eval_after_cp=180,
    )
    classify_move(move, wpl=0.0, side="white")
    assert move.classification == "Brilliant"
    assert "sacrifice" in move.explanation.lower()


def test_classify_brilliant_rook_sacrifice():
    """A rook sacrifice is classified as Brilliant."""
    # Position where White rook on e1 plays Re8+ or Rxe6
    # Let's create a position: White Rook on e1, Black pawn on e6 defended by f7 pawn and d7 pawn
    # White plays Rxe6: Rook (500cp) takes pawn (100cp), attacked by f7 pawn (100cp) -> net deficit
    fen = "r2q1rk1/ppp2ppp/4b3/8/8/4R3/PPP2PPP/4R1K1 w - - 0 1"
    # Rook on e3 plays Rxe6 (takes bishop, attacked by f7 pawn: moving 500, captured 325, attacked by 100)
    move = MoveAnalysis(
        move_number=19,
        ply=37,
        san="Rxe6",
        uci="e3e6",
        fen_before=fen,
        win_chance_before=0.55,
        win_chance_after=0.72,
        best_move="e3e6",
        eval_before_cp=40,
        eval_after_cp=150,
    )
    classify_move(move, wpl=0.0, side="white")
    assert move.classification == "Brilliant"


def test_classify_brilliant_allowed_when_winning_if_forced_mate():
    """A piece sacrifice in a winning position leading to forced mate is Brilliant."""
    fen = "r1bq1rk1/pppn1ppp/4p3/3p4/2PP4/2NBPN2/PP3PPP/R1BQK2R w KQ - 0 8"
    move = MoveAnalysis(
        move_number=8,
        ply=15,
        san="Bxh7+",
        uci="d3h7",
        fen_before=fen,
        win_chance_before=0.96,  # Already winning by a landslide
        win_chance_after=1.0,
        best_move="d3h7",
        eval_before_cp=700,
        eval_after_mate=3,  # Leads to forced mate in 3
    )
    classify_move(move, wpl=0.0, side="white")
    assert move.classification == "Brilliant"


def test_classify_brilliant_during_forced_mate_sequence():
    """Sacrifice played when player already had a forced mate (e.g. mate in 4 -> mate in 3) is Brilliant."""
    fen = "r1b2rk1/2p2pp1/2n4p/1pbpN3/p3P3/1B1P2P1/PPPQN1q1/2KR3R w - - 0 17"
    move = MoveAnalysis(
        move_number=17,
        ply=33,
        san="Rxh6+",
        uci="h1h6",
        fen_before=fen,
        win_chance_before=1.0,
        win_chance_after=1.0,
        best_move="h1h6",
        eval_before_mate=4,  # Had mate in 4 before
        eval_after_mate=3,  # Sacrifice advances to mate in 3
        eval_before_cp=99996,
        eval_after_cp=99997,
    )
    classify_move(move, wpl=0.0, side="white")
    assert move.classification == "Brilliant"


def test_classify_brilliant_not_given_when_already_winning_without_mate():
    """Sacrifice in an overwhelmingly won position (win_chance >= 0.95) without forced mate is Best, not Brilliant."""
    fen = "r1bq1rk1/pppn1ppp/4p3/3p4/2PP4/2NBPN2/PP3PPP/R1BQK2R w KQ - 0 8"
    move = MoveAnalysis(
        move_number=8,
        ply=15,
        san="Bxh7+",
        uci="d3h7",
        fen_before=fen,
        win_chance_before=0.96,  # Already winning by a landslide
        win_chance_after=0.98,
        best_move="d3h7",
        eval_before_cp=600,
        eval_after_cp=900,
        eval_after_mate=None,
    )
    multi_pvs = [
        {"uci": "d3h7", "cp": 900, "mate": None},
        {"uci": "e1g1", "cp": 890, "mate": None},  # Alternative is just as crushing
    ]
    classify_move(move, wpl=0.0, side="white", multi_pvs=multi_pvs)
    assert move.classification == "Best"


def test_classify_pinned_piece_not_sacrifice():
    """A piece landing on a square attacked only by a pinned piece cannot be taken, so it is Best, not Brilliant."""
    # Move 21 in game: White plays 21. Rxg6+. Black pawn on f7 is absolutely pinned to King on g8 by Queen on g5.
    fen_before_21 = "r1b2rk1/2p2p2/5Rn1/ppb1p1Q1/4P3/1B1P2P1/PPP1N1q1/2KR4 w - - 3 21"
    move = MoveAnalysis(
        move_number=21,
        ply=41,
        san="Rxg6+",
        uci="f6g6",
        fen_before=fen_before_21,
        win_chance_before=1.0,
        win_chance_after=1.0,
        best_move="f6g6",
        eval_before_mate=2,
        eval_after_mate=1,
    )
    classify_move(move, wpl=0.0, side="white")
    assert move.classification == "Best"


def test_classify_brilliant_not_given_for_equal_trade():
    """Equal piece trade (e.g. QxQ or RxR) is Best, not Brilliant."""
    # FEN with queens facing each other on open file
    fen_queens = "r2q1rk1/ppp2ppp/8/8/8/8/PPP2PPP/R2Q1RK1 w - - 0 1"
    move = MoveAnalysis(
        move_number=15,
        ply=29,
        san="Qxd8",
        uci="d1d8",
        fen_before=fen_queens,
        win_chance_before=0.52,
        win_chance_after=0.52,
        best_move="d1d8",
        eval_before_cp=10,
        eval_after_cp=10,
    )
    classify_move(move, wpl=0.0, side="white")
    assert move.classification == "Best"


def test_classify_brilliant_not_given_for_unsound_sacrifice():
    """An unsound sacrifice (high WPL / blunder) is classified as Blunder, not Brilliant."""
    fen = "r1bq1rk1/pppn1ppp/4p3/3p4/2PP4/2NBPN2/PP3PPP/R1BQK2R w KQ - 0 8"
    move = MoveAnalysis(
        move_number=8,
        ply=15,
        san="Bxh7+??",
        uci="d3h7",
        fen_before=fen,
        win_chance_before=0.55,
        win_chance_after=0.15,  # Completely ruined position
        best_move="e1g1",
        eval_before_cp=30,
        eval_after_cp=-350,
    )
    classify_move(move, wpl=0.40, side="white")
    assert move.classification == "Blunder"


def test_classify_blunder_tier():
    """A move with large win probability loss is classified as Blunder."""
    move = MoveAnalysis(
        move_number=10,
        ply=19,
        san="Qxa8??",
        uci="d1a8",
        fen_before="start",
        win_chance_before=0.60,
        win_chance_after=0.20,
        eval_before_cp=50,
        eval_after_cp=-250,
        best_move="e1g1",
    )
    classify_move(move, wpl=0.40, side="white")
    assert move.classification == "Blunder"


def test_classify_mistake_tier():
    """A move losing 10% to 20% win chances is classified as Mistake."""
    move = MoveAnalysis(
        move_number=14,
        ply=27,
        san="Nd4",
        uci="c2d4",
        fen_before="start",
        win_chance_before=0.55,
        win_chance_after=0.42,
        eval_before_cp=35,
        eval_after_cp=-60,
        best_move="e1g1",
    )
    classify_move(move, wpl=0.13, side="white")
    assert move.classification == "Mistake"


def test_classify_inaccuracy_tier():
    """A move losing 5% to 10% win chances is classified as Inaccuracy."""
    move = MoveAnalysis(
        move_number=12,
        ply=23,
        san="h3",
        uci="h2h3",
        fen_before="start",
        win_chance_before=0.52,
        win_chance_after=0.45,
        eval_before_cp=15,
        eval_after_cp=-35,
        best_move="c1e3",
    )
    classify_move(move, wpl=0.07, side="white")
    assert move.classification == "Inaccuracy"


def test_classify_miss_winning_opportunity():
    """Blowing a clearly winning position (>=70% win chance down to <50% but >=42%) is classified as Miss."""
    move = MoveAnalysis(
        move_number=25,
        ply=49,
        san="Kh1",
        uci="g1h1",
        fen_before="start",
        win_chance_before=0.78,
        win_chance_after=0.45,
        eval_before_cp=240,
        eval_after_cp=-40,
        best_move="f3f7",
    )
    classify_move(move, wpl=0.33, side="white")
    assert move.classification == "Miss"


def test_classify_recapture_is_best_not_great():
    """Recapturing a piece on the square where opponent just captured is Best, not Great."""
    # FEN where Black Knight just moved to d4 (captured on d4)
    fen = "r1bqk2r/pp2bppp/2n5/3p4/3n4/2N2N2/PPP1BPPP/R1BQK2R w KQkq - 0 10"
    prev_move = MoveAnalysis(
        move_number=9,
        ply=18,
        san="Nxd4",
        uci="c6d4",
        fen_before="",
    )
    move = MoveAnalysis(
        move_number=10,
        ply=19,
        san="Nxd4",
        uci="f3d4",
        fen_before=fen,
        win_chance_before=0.52,
        win_chance_after=0.52,
        best_move="f3d4",
    )
    multi_pvs = [
        {"uci": "f3d4", "cp": 15, "mate": None},
        {"uci": "h2h3", "cp": -320, "mate": None},  # Blunders a piece if not recapturing
    ]
    classify_move(move, wpl=0.0, side="white", multi_pvs=multi_pvs, prev_move=prev_move)
    assert move.classification == "Best"
    assert "Engine's top choice" in move.explanation


def test_classify_equal_trade_is_best_not_great():
    """Equal trades (QxQ, RxR, BxB) with only one viable move are Best, not Great."""
    fen = "r2q1rk1/ppp2ppp/8/8/8/8/PPP2PPP/R2Q1RK1 w - - 0 1"
    move = MoveAnalysis(
        move_number=15,
        ply=29,
        san="Qxd8",
        uci="d1d8",
        fen_before=fen,
        win_chance_before=0.50,
        win_chance_after=0.50,
        best_move="d1d8",
    )
    multi_pvs = [
        {"uci": "d1d8", "cp": 0, "mate": None},
        {"uci": "f1e1", "cp": -800, "mate": None},  # Dropping the Queen
    ]
    classify_move(move, wpl=0.0, side="white", multi_pvs=multi_pvs)
    assert move.classification == "Best"


def test_classify_hanging_higher_piece_is_great():
    """Capturing an undefended hanging higher-value piece where alternatives are worse is Great."""
    # White pawn on c4 captures undefended Black Queen on d5
    fen_pawn_takes_q = "r1b1kbnr/ppp1pppp/8/3q4/2P5/8/PP1P1PPP/RNBQKBNR w KQkq - 0 4"
    take_q = MoveAnalysis(
        move_number=4,
        ply=7,
        san="cxd5",
        uci="c4d5",
        fen_before=fen_pawn_takes_q,
        win_chance_before=0.55,
        win_chance_after=0.90,
        best_move="c4d5",
    )
    multi_pvs = [
        {"uci": "c4d5", "cp": 700, "mate": None},
        {"uci": "d2d4", "cp": 20, "mate": None},  # Missing the free queen
    ]
    classify_move(take_q, wpl=0.0, side="white", multi_pvs=multi_pvs)
    assert take_q.classification == "Great"


def test_classify_only_move_where_rest_worse_is_great():
    """Finding the only move in a position where the rest are worse is Great."""
    fen = "r1bq1rk1/pppn1ppp/4p3/3p4/2PP4/2NBPN2/PP3PPP/R1BQK2R w KQ - 0 8"
    move = MoveAnalysis(
        move_number=18,
        ply=35,
        san="h3",
        uci="h2h3",
        fen_before=fen,
        win_chance_before=0.60,
        win_chance_after=0.65,
        best_move="h2h3",
    )
    multi_pvs = [
        {"uci": "h2h3", "cp": 80, "mate": None},
        {"uci": "a2a3", "cp": -150, "mate": None},  # Rest of moves are worse
    ]
    classify_move(move, wpl=0.0, side="white", multi_pvs=multi_pvs)
    assert move.classification == "Great"
    assert "Only good move" in move.explanation


def test_classify_genuine_great_move():
    """A critical quiet move in a balanced/sharp game where only it avoids a blunder is Great."""
    # Quiet defensive queen move defending against a king attack
    fen = "r1b1kb1r/pppp1ppp/8/4p3/7q/3P4/PPP2PPP/RNBQK2R w KQkq - 0 8"
    move = MoveAnalysis(
        move_number=8,
        ply=15,
        san="Qe2",
        uci="d1e2",
        fen_before=fen,
        win_chance_before=0.52,
        win_chance_after=0.54,
        best_move="d1e2",
    )
    multi_pvs = [
        {"uci": "d1e2", "cp": 20, "mate": None},
        {"uci": "a2a3", "cp": -300, "mate": None},  # Alternative drops decisive attack/material
    ]
    classify_move(move, wpl=0.0, side="white", multi_pvs=multi_pvs)
    assert move.classification == "Great"
    assert "Only good move" in move.explanation

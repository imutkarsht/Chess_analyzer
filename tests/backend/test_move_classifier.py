"""Tests for move classification bands and mathematical win probability calculation."""
import pytest
from src.backend.storage.models import MoveAnalysis
from src.backend.analysis.math_utils import get_win_probability, calculate_move_accuracy, get_cp
from src.backend.analysis.move_classifier import classify_move


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
        move_number=20, ply=40, san="Qxf7#", uci="d1f7",
        fen_before="start", win_chance_before=0.99, win_chance_after=1.0
    )
    classify_move(move, wpl=0.0, side="white")
    assert move.classification == "Best"
    assert "checkmate" in move.explanation.lower()


def test_classify_missed_mate():
    """Missing a forced checkmate is classified as Miss."""
    move = MoveAnalysis(
        move_number=15, ply=29, san="Be3", uci="c1e3",
        fen_before="start", win_chance_before=1.0, win_chance_after=0.7,
        eval_before_mate=2, eval_after_mate=None,
        best_move="d1h5"
    )
    classify_move(move, wpl=0.3, side="white")
    assert move.classification == "Miss"


def test_classify_brilliant_move():
    """Best move with a massive second-choice gap and position improvement is Brilliant."""
    move = MoveAnalysis(
        move_number=18, ply=35, san="Nxf7", uci="e5f7",
        fen_before="start", win_chance_before=0.55, win_chance_after=0.85,
        best_move="e5f7", eval_before_cp=50, eval_after_cp=300
    )
    multi_pvs = [
        {"uci": "e5f7", "cp": 300, "mate": None},
        {"uci": "e5d3", "cp": -100, "mate": None},
    ]
    classify_move(move, wpl=0.0, side="white", multi_pvs=multi_pvs)
    assert move.classification in ("Brilliant", "Great")


def test_classify_blunder_tier():
    """A move with large win probability loss is classified as Blunder."""
    move = MoveAnalysis(
        move_number=10, ply=19, san="Qxa8??", uci="d1a8",
        fen_before="start", win_chance_before=0.60, win_chance_after=0.20,
        eval_before_cp=50, eval_after_cp=-250, best_move="e1g1"
    )
    classify_move(move, wpl=0.40, side="white")
    assert move.classification == "Blunder"

"""Tests for move-list navigation helpers."""

import pytest

from src.backend.analysis.navigation import find_critical_move
from src.backend.storage.models import MoveAnalysis


def _moves(*classifications):
    return [
        MoveAnalysis(i // 2 + 1, i % 2 + 1, "e4", "e2e4", "", classification=c)
        for i, c in enumerate(classifications)
    ]


MOVES = _moves("Book", "Best", "Mistake", "Good", "Blunder", "Miss", "Excellent")


def test_next_from_start_position():
    assert find_critical_move(MOVES, -1, 1) == 2


def test_next_skips_current_move():
    assert find_critical_move(MOVES, 2, 1) == 4
    assert find_critical_move(MOVES, 4, 1) == 5


def test_previous():
    assert find_critical_move(MOVES, 6, -1) == 5
    assert find_critical_move(MOVES, 4, -1) == 2


def test_none_when_nothing_in_direction():
    assert find_critical_move(MOVES, 5, 1) is None
    assert find_critical_move(MOVES, 2, -1) is None
    assert find_critical_move(MOVES, -1, -1) is None


def test_unanalysed_game_has_no_critical_moves():
    assert find_critical_move(_moves("", "", ""), -1, 1) is None


def test_custom_classifications_are_case_insensitive():
    assert find_critical_move(MOVES, -1, 1, classifications={"GOOD"}) == 3


def test_invalid_step_rejected():
    with pytest.raises(ValueError):
        find_critical_move(MOVES, 0, 2)

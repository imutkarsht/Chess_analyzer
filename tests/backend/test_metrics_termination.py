"""Tests for termination and draw-type classification."""

import pytest

from src.backend.analysis.metrics.termination import classify_termination


@pytest.mark.parametrize(
    ("term_mode", "expected"),
    [
        ("threefold_repetition", "3-Fold Repetition"),
        ("repetition", "3-Fold Repetition"),
        ("agreed_draw", "Agreement"),
        ("agreement", "Agreement"),
        ("stalemate", "Stalemate"),
        ("timeout_insufficient", "Insufficient vs Timeout"),
        ("insufficient_material", "Insufficient Material"),
        ("fifty_moves", "50-Move Rule"),
        ("50_moves", "50-Move Rule"),
    ],
)
def test_draw_mode_maps_to_bucket(term_mode, expected):
    assert classify_termination({"termination_mode": term_mode}, is_draw=True) == (
        "Draw",
        expected,
    )


@pytest.mark.parametrize(
    ("term_mode", "expected"),
    [
        ("checkmate", "Checkmate"),
        ("timeout", "Time"),
        ("abandonment", "Abandon"),
        ("resignation", "Resignation"),
    ],
)
def test_non_draw_modes(term_mode, expected):
    assert classify_termination({"termination_mode": term_mode}, is_draw=False) == (
        expected,
        None,
    )


def test_unknown_termination_defaults_to_resignation():
    assert classify_termination({}, is_draw=False) == ("Resignation", None)

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
    ("termination", "expected"),
    [
        ("Drawn by threefold repetition", "3-Fold Repetition"),
        ("Drawn by repetition", "3-Fold Repetition"),
        ("Drawn by stalemate", "Stalemate"),
        ("Draw by insufficient material and timeout", "Insufficient vs Timeout"),
        ("Draw by insufficient material", "Insufficient Material"),
        ("Draw by 50-move rule", "50-Move Rule"),
        ("Draw by fifty moves", "50-Move Rule"),
        ("Drawn by agreement", "Agreement"),
        ("", "Agreement"),
    ],
)
def test_draw_text_falls_back_to_patterns(termination, expected):
    assert classify_termination({"termination": termination}, is_draw=True) == (
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


@pytest.mark.parametrize(
    ("termination", "expected"),
    [
        ("Alice won by checkmate", "Checkmate"),
        ("Alice won on time", "Time"),
        ("Alice won - game abandoned", "Abandon"),
        ("Alice won by resignation", "Resignation"),
    ],
)
def test_non_draw_text_patterns(termination, expected):
    assert classify_termination({"termination": termination}, is_draw=False) == (
        expected,
        None,
    )


def test_stalemate_text_is_not_mistaken_for_checkmate():
    # "stalemate" contains "mate"; the anchored checkmate pattern must not win.
    assert classify_termination({"termination": "stalemate"}, is_draw=False) == (
        "Resignation",
        None,
    )


def test_checkmate_symbol_in_pgn_is_detected():
    assert classify_termination({"pgn": "1. f3 e5 2. g4 Qh4# 0-1"}, is_draw=False) == (
        "Checkmate",
        None,
    )


def test_unknown_termination_defaults_to_resignation():
    assert classify_termination({}, is_draw=False) == ("Resignation", None)

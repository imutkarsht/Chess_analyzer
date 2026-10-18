"""
Game termination classification module.
Determines exact termination type (Checkmate, Resignation, Time, Abandon, Draw)
and detailed draw subcategory using authoritative termination_mode and robust regex patterns.
"""

from __future__ import annotations

import re
from typing import Any

from .constants import DRAW_MODE_TO_BUCKET

# Regex patterns anchored with word boundaries to avoid false substrings
_STALEMATE_PAT = re.compile(r"\bstalemate\b", re.IGNORECASE)
_REPETITION_PAT = re.compile(r"\b(?:threefold|repetition)\b", re.IGNORECASE)
_INSUFFICIENT_PAT = re.compile(r"\binsufficient\b", re.IGNORECASE)
_TIME_PAT = re.compile(r"\b(?:time|timeout|clock|flag|flagged)\b", re.IGNORECASE)
_FIFTY_MOVES_PAT = re.compile(r"\b(?:50[- ]move|fifty[- ]moves?|\b50\b)", re.IGNORECASE)

_CHECKMATE_PAT = re.compile(r"\b(?:checkmate|mate)\b", re.IGNORECASE)
_ABANDON_PAT = re.compile(r"\b(?:abandon|abandoned|abandonment)\b", re.IGNORECASE)
_RESIGN_PAT = re.compile(r"\b(?:resign|resigned|resignation)\b", re.IGNORECASE)


def classify_termination(
    game: dict[str, Any],
    is_draw: bool,
) -> tuple[str, str | None]:
    """
    Classify game termination into (term_type, draw_type).

    Parameters:
        game: Dictionary containing game fields ('termination', 'termination_mode', 'pgn').
        is_draw: True if the normalized result is a draw.

    Returns:
        tuple[str, str | None]: (term_type, draw_type)
        where term_type is one of: Checkmate, Resignation, Time, Abandon, Draw
        and draw_type is populated only when term_type == 'Draw'.
    """
    term_mode = (game.get("termination_mode") or "").strip().lower()
    term = (game.get("termination") or "").strip()

    if is_draw:
        # 1. Exact termination mode
        if term_mode in DRAW_MODE_TO_BUCKET:
            return "Draw", DRAW_MODE_TO_BUCKET[term_mode]

        # 2. Text matching on header/termination description with boundary checks
        if _REPETITION_PAT.search(term):
            return "Draw", "3-Fold Repetition"
        if _STALEMATE_PAT.search(term):
            return "Draw", "Stalemate"
        if _INSUFFICIENT_PAT.search(term) and _TIME_PAT.search(term):
            return "Draw", "Insufficient vs Timeout"
        if _INSUFFICIENT_PAT.search(term):
            return "Draw", "Insufficient Material"
        if _FIFTY_MOVES_PAT.search(term):
            return "Draw", "50-Move Rule"

        return "Draw", "Agreement"

    # Non-draw games
    # 1. Exact termination mode
    if term_mode == "checkmate":
        return "Checkmate", None
    if term_mode == "timeout":
        return "Time", None
    if term_mode == "abandonment":
        return "Abandon", None
    if term_mode == "resignation":
        return "Resignation", None

    # 2. Anchored pattern checks (ensure "mate" does not match "stalemate")
    if _CHECKMATE_PAT.search(term) and not _STALEMATE_PAT.search(term):
        return "Checkmate", None
    if _TIME_PAT.search(term):
        return "Time", None
    if _ABANDON_PAT.search(term):
        return "Abandon", None
    if _RESIGN_PAT.search(term):
        return "Resignation", None

    # 3. PGN check for checkmate symbol '#'
    pgn = game.get("pgn", "")
    if "#" in pgn:
        return "Checkmate", None

    return "Resignation", None

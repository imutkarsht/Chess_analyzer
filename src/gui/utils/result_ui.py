# SPDX-License-Identifier: GPL-3.0-only
"""Shared result labels and tones for history, metrics, and reports."""

from __future__ import annotations

from src.backend.analysis.metrics.models import Outcome, outcome_for
from src.gui.theme.typography import TextTone


def result_tone(result: str | None, user_color: str | None) -> TextTone:
    """Resolve a game result to a semantic tone from the user's perspective."""
    if not user_color:
        return TextTone.RESULT_DRAW

    outcome = outcome_for(result or "", user_color)
    if outcome is Outcome.WIN:
        return TextTone.RESULT_WIN
    if outcome is Outcome.LOSS:
        return TextTone.RESULT_LOSS
    return TextTone.RESULT_DRAW


def result_text(result: str | None) -> str:
    """Human-readable result label used by the share report."""
    return {
        "1-0": "White wins",
        "0-1": "Black wins",
        "1/2-1/2": "Draw",
    }.get(result or "", "In progress")


def termination_suffix(mode: str | None) -> str:
    """Short termination phrase appended to the result label."""
    if mode == "resignation":
        return "by resignation"
    if mode in {"timeout", "timeout_insufficient"}:
        return "by timeout"
    return ""


def result_display(result: str | None, termination_mode: str | None) -> str:
    """Uppercase result label with an optional termination suffix."""
    outcome = result_text(result).upper()
    suffix = termination_suffix(termination_mode)
    return f"{outcome} · {suffix.upper()}" if suffix else outcome

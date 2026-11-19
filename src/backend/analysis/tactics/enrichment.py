# SPDX-License-Identifier: GPL-3.0-only
"""Attach tactical summaries to stored game summary dictionaries."""

from __future__ import annotations

from typing import Any

from src.backend.analysis.tactics.game import analyze_game_tactics


def enrich_summary_with_tactics(
    summary_dict: dict[str, Any],
    moves_data: list[dict[str, Any]],
    result: str,
    speed_category: str = "Blitz",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Compute both sides' tactics and attach them to ``summary_dict``."""
    tactics_white = analyze_game_tactics(
        moves_data, "white", result, speed_category=speed_category
    )
    tactics_black = analyze_game_tactics(
        moves_data, "black", result, speed_category=speed_category
    )

    if "white" not in summary_dict or not isinstance(summary_dict["white"], dict):
        summary_dict["white"] = {}
    if "black" not in summary_dict or not isinstance(summary_dict["black"], dict):
        summary_dict["black"] = {}

    summary_dict["white"]["tactics"] = tactics_white
    summary_dict["black"]["tactics"] = tactics_black
    return summary_dict, tactics_white, tactics_black

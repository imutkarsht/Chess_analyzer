"""
Metrics aggregation module for headless calculation of player performance statistics.
Pure Python, zero Qt dependencies.
Backward-compatibility facade delegating to the modular `src.backend.analysis.metrics` package.
"""

from __future__ import annotations

from typing import Any

from src.backend.analysis.metrics import (
    DRAW_MODE_TO_BUCKET,
    GameRecord,
    Outcome,
    StatsAccumulator,
    build_coach_dossier,
    calculate_stats,
    classify_termination,
    filter_games,
    get_drill_down_items,
    get_user_color,
    matches_filters,
    outcome_for,
)


class MetricsAggregator:
    """Aggregates game records into comprehensive statistical insights."""

    @staticmethod
    def get_user_color(
        game: dict[str, Any],
        usernames: list[str] | set[str] | frozenset[str],
    ) -> str | None:
        """Determine whether the tracked user was playing White or Black."""
        return get_user_color(game, usernames)

    @classmethod
    def matches_filters(
        cls,
        game: dict[str, Any],
        user_color: str | None,
        color_filter: str = "All Colors",
        format_filter: str = "All Formats",
        source_filter: str = "All Sources",
        date_filter: str = "All Time",
    ) -> bool:
        """Determines if a game matches user-selected criteria."""
        return matches_filters(
            game,
            user_color,
            color_filter=color_filter,
            format_filter=format_filter,
            source_filter=source_filter,
            date_filter=date_filter,
        )

    @classmethod
    def calculate_stats(
        cls,
        games: list[dict[str, Any]],
        usernames: list[str] | set[str],
        color_filter: str = "All Colors",
        format_filter: str = "All Formats",
        source_filter: str = "All Sources",
        date_filter: str = "All Time",
    ) -> dict[str, Any]:
        """Calculate comprehensive game statistics over filtered games."""
        return calculate_stats(
            games,
            usernames,
            color_filter=color_filter,
            format_filter=format_filter,
            source_filter=source_filter,
            date_filter=date_filter,
        )

    @classmethod
    def get_drill_down_items(
        cls,
        stats: dict[str, Any],
        category: str,
        subcategory: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve drill-down items for a specific category and optional subcategory."""
        return get_drill_down_items(stats, category, subcategory=subcategory)

    @classmethod
    def build_coach_dossier(cls, stats: dict[str, Any]) -> str:
        """Builds a compact, high-signal performance dossier from aggregated stats."""
        return build_coach_dossier(stats)


__all__ = [
    "DRAW_MODE_TO_BUCKET",
    "GameRecord",
    "MetricsAggregator",
    "Outcome",
    "StatsAccumulator",
    "build_coach_dossier",
    "calculate_stats",
    "classify_termination",
    "filter_games",
    "get_drill_down_items",
    "get_user_color",
    "matches_filters",
    "outcome_for",
]

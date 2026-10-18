"""
Core metrics aggregator orchestration module.
Aggregates games and coordinates filtering, parsing, and statistical accumulation.
"""

from __future__ import annotations

from typing import Any

from .accumulators import StatsAccumulator
from .filters import filter_games, get_user_color, matches_filters
from .models import GameRecord


def calculate_stats(
    games: list[dict[str, Any]],
    usernames: list[str] | set[str],
    color_filter: str = "All Colors",
    format_filter: str = "All Formats",
    source_filter: str = "All Sources",
    date_filter: str = "All Time",
) -> dict[str, Any]:
    """Calculate comprehensive game statistics over filtered games."""
    accumulator = StatsAccumulator()
    filtered_games = filter_games(
        games,
        usernames,
        color_filter=color_filter,
        format_filter=format_filter,
        source_filter=source_filter,
        date_filter=date_filter,
    )

    for game, user_color in filtered_games:
        rec = GameRecord.from_dict(game, user_color)
        accumulator.add(rec)

    return accumulator.finalize(
        color_filter=color_filter,
        format_filter=format_filter,
        source_filter=source_filter,
        date_filter=date_filter,
    )


def get_drill_down_items(
    stats: dict[str, Any],
    category: str,
    subcategory: str | None = None,
) -> list[dict[str, Any]]:
    """
    Retrieve drill-down items for a specific category and optional subcategory.
    E.g. category='hung_pieces', subcategory='queen'
         category='blunders'
         category='tactical_themes', subcategory='fork'
         category='advantage', subcategory='thrown_losses'
         category='brilliancies'
    """
    if category == "brilliancies":
        return stats.get("brilliancies", [])

    drill_down = stats.get("drill_down", {})
    cat_data = drill_down.get(category, {})
    if isinstance(cat_data, list):
        return cat_data
    if isinstance(cat_data, dict):
        if subcategory:
            if subcategory in cat_data:
                return cat_data[subcategory]
            sub_lower = subcategory.lower()
            for k, v in cat_data.items():
                if k.lower() == sub_lower:
                    return v
            for k, v in cat_data.items():
                if k.lower().startswith(sub_lower) or sub_lower.startswith(k.lower()):
                    return v
            return []
        if "all" in cat_data:
            return cat_data["all"]
        all_items: list[dict[str, Any]] = []
        for v in cat_data.values():
            if isinstance(v, list):
                all_items.extend(v)
        return all_items
    return []


class MetricsAggregator:
    """Aggregates game records into comprehensive statistical insights (OOP interface)."""

    get_user_color = staticmethod(get_user_color)
    matches_filters = staticmethod(matches_filters)
    calculate_stats = staticmethod(calculate_stats)
    get_drill_down_items = staticmethod(get_drill_down_items)

"""
Metrics package for game statistics aggregation, filtering, and performance dossiers.
"""

from __future__ import annotations

from .accumulators import (
    AdvantageStats,
    ClockStats,
    ColorStats,
    FormatStats,
    HangingStats,
    OpeningStats,
    PhaseStats,
    StatsAccumulator,
    pct,
)
from .aggregator import MetricsAggregator, calculate_stats, get_drill_down_items
from .coach_dossier import build_coach_dossier
from .constants import (
    ADVANTAGE_DRILLS,
    ADVANTAGE_KEYS,
    COLORS,
    DRAW_BUCKETS,
    DRAW_MODE_TO_BUCKET,
    MOTIF_NAMES,
    NON_DRAW_TERM_TYPES,
    PHASES,
    PIECE_NAMES,
    QUALITY_NAMES,
    QUALITY_PACE_KEYS,
    TERM_TYPES,
    VALID_DATE_FILTERS,
)
from .filters import filter_games, get_user_color, matches_filters
from .models import GameRecord, Outcome, outcome_for
from .termination import classify_termination

__all__ = [
    "ADVANTAGE_DRILLS",
    "ADVANTAGE_KEYS",
    "COLORS",
    "DRAW_BUCKETS",
    "DRAW_MODE_TO_BUCKET",
    "MOTIF_NAMES",
    "NON_DRAW_TERM_TYPES",
    "PHASES",
    "PIECE_NAMES",
    "QUALITY_NAMES",
    "QUALITY_PACE_KEYS",
    "TERM_TYPES",
    "VALID_DATE_FILTERS",
    "AdvantageStats",
    "ClockStats",
    "ColorStats",
    "FormatStats",
    "GameRecord",
    "HangingStats",
    "MetricsAggregator",
    "OpeningStats",
    "Outcome",
    "PhaseStats",
    "StatsAccumulator",
    "build_coach_dossier",
    "calculate_stats",
    "classify_termination",
    "filter_games",
    "get_drill_down_items",
    "get_user_color",
    "matches_filters",
    "outcome_for",
    "pct",
]


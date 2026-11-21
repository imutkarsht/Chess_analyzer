"""
Metrics package for game statistics aggregation, filtering, and performance dossiers.
"""

from __future__ import annotations

from src.backend.analysis.metrics.accumulators import (
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
from src.backend.analysis.metrics.aggregator import (
    calculate_stats,
    get_drill_down_items,
)
from src.backend.analysis.metrics.coach_dossier import build_coach_dossier
from src.backend.analysis.metrics.constants import (
    ADVANTAGE_DRILLS,
    ADVANTAGE_KEYS,
    COLORS,
    DRAW_BUCKETS,
    DRAW_MODE_TO_BUCKET,
    MAX_DRILL_DOWN_ITEMS,
    MOTIF_NAMES,
    NON_DRAW_TERM_TYPES,
    PHASES,
    PIECE_NAMES,
    QUALITY_NAMES,
    QUALITY_PACE_KEYS,
    TERM_TYPES,
    VALID_DATE_FILTERS,
)
from src.backend.analysis.metrics.filters import filter_games, get_user_color, matches_filters
from src.backend.analysis.metrics.models import GameRecord, Outcome, outcome_for
from src.backend.analysis.metrics.termination import classify_termination

__all__ = [
    "ADVANTAGE_DRILLS",
    "ADVANTAGE_KEYS",
    "COLORS",
    "DRAW_BUCKETS",
    "DRAW_MODE_TO_BUCKET",
    "MAX_DRILL_DOWN_ITEMS",
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

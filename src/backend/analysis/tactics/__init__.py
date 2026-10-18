"""
Tactical analysis package for Chess Analyzer Pro.
Provides deterministic hanging piece detection, game phase classification,
advantage conversion metrics, brilliancy extraction, and tactical motifs detection.
Zero Qt dependencies — headless and independently testable.
"""

from __future__ import annotations

from src.backend.analysis.tactics.board_utils import (
    find_slider_ray_targets,
    is_on_segment,
    legal_defenders,
    min_attacker_value,
    piece_value,
    to_user_cp,
    to_user_wp,
)
from src.backend.analysis.tactics.constants import (
    PHASES,
    PIECE_NAMES,
    PIECE_NAMES_ORDERED,
    PIECE_VALUES,
    GamePhase,
    MoveQualityBucket,
    TacticalTheme,
)
from src.backend.analysis.tactics.game import (
    ClockStats,
    MoveCtx,
    TacticsState,
    analyze_game_tactics,
)
from src.backend.analysis.tactics.hanging import get_hanging_pieces, is_piece_hanging
from src.backend.analysis.tactics.motifs import (
    DETECTORS,
    MotifCtx,
    detect_tactical_motifs,
)
from src.backend.analysis.tactics.phase import classify_game_phase, non_pawn_material
from src.backend.analysis.tactics.see import is_safely_placed, static_exchange_evaluation

__all__ = [
    "PIECE_NAMES",
    "PIECE_NAMES_ORDERED",
    "PIECE_VALUES",
    "PHASES",
    "GamePhase",
    "MoveQualityBucket",
    "TacticalTheme",
    "ClockStats",
    "MoveCtx",
    "TacticsState",
    "analyze_game_tactics",
    "classify_game_phase",
    "detect_tactical_motifs",
    "find_slider_ray_targets",
    "get_hanging_pieces",
    "is_on_segment",
    "is_piece_hanging",
    "is_safely_placed",
    "legal_defenders",
    "min_attacker_value",
    "non_pawn_material",
    "piece_value",
    "static_exchange_evaluation",
    "to_user_cp",
    "to_user_wp",
    "DETECTORS",
    "MotifCtx",
]

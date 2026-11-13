"""
Constants, enums, and configuration thresholds for tactics analysis.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

import chess

# ==============================================================================
# PIECE VALUES & NAMES
# ==============================================================================

PIECE_VALUES: Final[dict[chess.PieceType, int]] = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}

PIECE_NAMES: Final[dict[chess.PieceType, str]] = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}

PIECE_NAMES_ORDERED: Final[tuple[str, ...]] = ("pawn", "knight", "bishop", "rook", "queen")


# ==============================================================================
# ENUMS
# ==============================================================================


class GamePhase(StrEnum):
    OPENING = "opening"
    MIDDLEGAME = "middlegame"
    ENDGAME = "endgame"


PHASES: Final[tuple[str, ...]] = (
    GamePhase.OPENING.value,
    GamePhase.MIDDLEGAME.value,
    GamePhase.ENDGAME.value,
)


class TacticalTheme(StrEnum):
    """Tactical motifs. Definitions follow the Lichess puzzle themes."""

    HANGING_PIECE = "hanging_piece"
    FORK = "fork"
    PIN = "pin"
    SKEWER = "skewer"
    DISCOVERED_ATTACK = "discovered_attack"
    DISCOVERED_CHECK = "discovered_check"
    DOUBLE_CHECK = "double_check"
    REMOVAL_OF_DEFENDER = "removal_of_defender"
    TRAPPED_PIECE = "trapped_piece"
    SACRIFICE = "sacrifice"
    PROMOTION = "promotion"
    BACK_RANK_MATE = "back_rank_mate"
    SMOTHERED_MATE = "smothered_mate"
    MORPHY_MATE = "morphy_mate"
    OPERA_MATE = "opera_mate"
    BODEN_MATE = "boden_mate"


class TacticRole(StrEnum):
    """How the player relates to a detected motif."""

    EXECUTED = "executed"
    ALLOWED = "allowed"
    MISSED = "missed"


class Confidence(StrEnum):
    """How strongly a tactic fact is corroborated."""

    CONFIRMED = "confirmed"
    PROBABLE = "probable"


class MoveQualityBucket(StrEnum):
    BEST = "best"
    BLUNDER = "blunder"
    OTHER = "other"


# ==============================================================================
# CLASSIFICATION SETS
# ==============================================================================

BLUNDER_CLASSIFICATIONS: Final[frozenset[str]] = frozenset({"Blunder"})
BAD_MOVE_CLASSIFICATIONS: Final[frozenset[str]] = frozenset({"Blunder", "Mistake"})
BRILLIANT_CLASSIFICATIONS: Final[frozenset[str]] = frozenset({"Brilliant", "Great"})
SOUND_CLASSIFICATIONS: Final[frozenset[str]] = frozenset(
    {"Brilliant", "Great", "Best", "Excellent"}
)
# A sacrifice is only a tactic when there was no better alternative. An
# "Excellent" exchange sacrifice is usually a material concession, not the
# engine-approved tactical idea.
SACRIFICE_CLASSIFICATIONS: Final[frozenset[str]] = frozenset(
    {"Brilliant", "Great", "Best"}
)


# ==============================================================================
# THRESHOLDS & TUNING PARAMETERS
# ==============================================================================

# Trouble time threshold in seconds based on time control category
TROUBLE_SECONDS: Final[dict[str, float]] = {
    "bullet": 15.0,
    "blitz": 30.0,
    "rapid": 60.0,
    "classical": 120.0,
    "daily": 300.0,
}
DEFAULT_TROUBLE_SECONDS: Final[float] = 30.0
MAX_REASONABLE_TIME_SECONDS: Final[float] = 7200.0  # 2 hours per move cap

# Tactical evaluation thresholds
ADVANTAGE_THRESHOLD_CP: Final[int] = 300
MIN_SACRIFICE_DEFICIT_CP: Final[int] = 200
WINNING_WP_THRESHOLD: Final[float] = 0.50
SOUND_MOVE_WP_DROP_THRESHOLD: Final[float] = 0.03
GOOD_MOVE_WP_DROP_THRESHOLD: Final[float] = 0.05
TURNING_POINT_MIN_WP_SWING: Final[float] = 0.05
SOUND_TACTIC_MAX_WP_DROP: Final[float] = 0.08

# Game phase material thresholds
ENDGAME_NO_QUEEN_TOTAL_MAX: Final[int] = 26
ENDGAME_LOW_TOTAL_NON_PAWN: Final[int] = 18
ENDGAME_SOLO_PIECE_MAX: Final[int] = 6
OPENING_MAX_PLY: Final[int] = 16
OPENING_MIN_NON_PAWN: Final[int] = 20

# King arbitrary high value for skewer comparison
KING_SKEWER_VALUE: Final[int] = 100

# Bump when tactic facts or their schema change; stored summaries with an older
# version are lazily recomputed. v3 merges multiple alignments of one motif on a
# single move into one occurrence. v4 excludes best/mating moves from missed
# tactical stats. v5 preserves the chess evidence when a fact is confirmed.
# v6 drops non-best sacrifices and vacuous pins.
TACTICS_VERSION: Final[int] = 6

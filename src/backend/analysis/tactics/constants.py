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
    FORK = "fork"
    PIN = "pin"
    SKEWER = "skewer"
    DISCOVERED_ATTACK = "discovered_attack"
    SACRIFICE = "sacrifice"
    BACK_RANK = "back_rank"


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


# ==============================================================================
# THRESHOLDS & TUNING PARAMETERS
# ==============================================================================

# Trouble time threshold in seconds based on time control category
TROUBLE_SECONDS: Final[dict[str, float]] = {
    "bullet": 15.0,
    "blitz": 30.0,
    "rapid": 60.0,
    "classical": 120.0,
}
DEFAULT_TROUBLE_SECONDS: Final[float] = 30.0
MAX_REASONABLE_TIME_SECONDS: Final[float] = 7200.0  # 2 hours per move cap

# Tactical evaluation thresholds
ADVANTAGE_THRESHOLD_CP: Final[int] = 300
MIN_SACRIFICE_DEFICIT_CP: Final[int] = 200
LEAD_COLLAPSE_DROP_CP: Final[int] = 300
COMEBACK_SWING_CP: Final[int] = 300
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

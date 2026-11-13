"""
Tactical analysis for Chess Analyzer Pro.

Provides legal-move piece safety, static exchange evaluation, validated tactic
facts, game-level attribution and the legacy hanging-piece façade.

Zero Qt dependencies -- headless and independently testable.
"""

from __future__ import annotations

from src.backend.analysis.tactics.attribution import (
    LossRecord,
    is_sound_move,
    resolve_losses,
)
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
    TACTICS_VERSION,
    Confidence,
    GamePhase,
    MoveQualityBucket,
    TacticalTheme,
    TacticRole,
)
from src.backend.analysis.tactics.contexts import MoveCtx, build_contexts
from src.backend.analysis.tactics.facts import TacticFact, fact_to_dict
from src.backend.analysis.tactics.game import (
    ClockStats,
    TacticsState,
    analyze_game_tactics,
)
from src.backend.analysis.tactics.hanging import get_hanging_pieces, is_piece_hanging
from src.backend.analysis.tactics.motifs import detect_candidates, detect_tactical_motifs
from src.backend.analysis.tactics.phase import classify_game_phase, non_pawn_material
from src.backend.analysis.tactics.piece_safety import (
    can_save_piece,
    get_lost_pieces,
    is_piece_doomed,
    is_piece_lost,
    piece_loss_evidence,
)
from src.backend.analysis.tactics.see import is_safely_placed, static_exchange_evaluation
from src.backend.analysis.tactics.validation import confirm_facts

__all__ = [
    "PHASES",
    "PIECE_NAMES",
    "PIECE_NAMES_ORDERED",
    "PIECE_VALUES",
    "TACTICS_VERSION",
    "ClockStats",
    "Confidence",
    "GamePhase",
    "LossRecord",
    "MoveCtx",
    "MoveQualityBucket",
    "TacticFact",
    "TacticRole",
    "TacticalTheme",
    "TacticsState",
    "analyze_game_tactics",
    "build_contexts",
    "can_save_piece",
    "classify_game_phase",
    "confirm_facts",
    "detect_candidates",
    "detect_tactical_motifs",
    "fact_to_dict",
    "find_slider_ray_targets",
    "get_hanging_pieces",
    "get_lost_pieces",
    "is_on_segment",
    "is_piece_doomed",
    "is_piece_hanging",
    "is_piece_lost",
    "is_safely_placed",
    "is_sound_move",
    "legal_defenders",
    "min_attacker_value",
    "non_pawn_material",
    "piece_loss_evidence",
    "piece_value",
    "resolve_losses",
    "static_exchange_evaluation",
    "to_user_cp",
    "to_user_wp",
]

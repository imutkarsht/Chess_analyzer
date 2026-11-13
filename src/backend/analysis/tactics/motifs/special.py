"""
Sacrifice and promotion detection.

A sacrifice is a sound move that offers material for a tactical return. A move
that simply hangs material is not classified as a sacrifice.

Zero Qt dependencies.
"""

from __future__ import annotations

import chess

from src.backend.analysis.tactics.board_utils import min_attacker_value, piece_value
from src.backend.analysis.tactics.constants import (
    MIN_SACRIFICE_DEFICIT_CP,
    PIECE_NAMES,
    SACRIFICE_CLASSIFICATIONS,
    TacticalTheme,
)
from src.backend.analysis.tactics.facts import TacticFact
from src.backend.analysis.tactics.motifs.context import MotifCtx, make_fact
from src.backend.analysis.tactics.see import static_exchange_evaluation


def sacrifice_fact(ctx: MotifCtx) -> TacticFact | None:
    """A sound non-pawn move that deliberately offers material."""
    if ctx.piece.piece_type in (chess.PAWN, chess.KING):
        return None
    # A sacrifice is only a tactic when it is the engine's choice. A merely
    # sound alternative that gives material is a concession, not the idea.
    if ctx.classification not in SACRIFICE_CLASSIFICATIONS:
        return None

    moved_value = piece_value(ctx.after, ctx.move.to_square)
    captured_value = piece_value(ctx.before, ctx.move.to_square)
    if captured_value >= moved_value:
        return None

    if ctx.before.is_pinned(ctx.color, ctx.move.from_square):
        return None
    if ctx.move.to_square in ctx.before.attackers(
        ctx.enemy_color, ctx.move.from_square
    ):
        return None
    if min_attacker_value(ctx.before, ctx.enemy_color, ctx.move.from_square) < moved_value:
        return None

    enemy_gain = static_exchange_evaluation(ctx.after, ctx.move.to_square, ctx.enemy_color)
    net_deficit = enemy_gain - captured_value * 100
    if net_deficit < MIN_SACRIFICE_DEFICIT_CP:
        return None

    captured_piece = ctx.before.piece_at(ctx.move.to_square)
    if captured_piece is not None:
        moved_name = PIECE_NAMES.get(ctx.piece.piece_type, "piece")
        captured_name = PIECE_NAMES.get(captured_piece.piece_type, "piece")
        evidence = (
            f"{moved_name} for {captured_name} · "
            f"{net_deficit / 100:g} points invested"
        )
    else:
        evidence = f"offers {moved_value} points"

    return make_fact(
        ctx,
        TacticalTheme.SACRIFICE,
        target_square=ctx.move.to_square,
        target_piece=PIECE_NAMES.get(ctx.piece.piece_type),
        evidence=evidence,
        material_gain_cp=-net_deficit,
    )


def promotion_fact(ctx: MotifCtx) -> TacticFact | None:
    """A pawn promotion."""
    if ctx.move.promotion is None:
        return None
    return make_fact(
        ctx,
        TacticalTheme.PROMOTION,
        target_square=ctx.move.to_square,
        target_piece=PIECE_NAMES.get(ctx.piece.piece_type),
        evidence=f"promotes to {PIECE_NAMES.get(ctx.move.promotion, 'piece')}",
    )


__all__ = ["promotion_fact", "sacrifice_fact"]

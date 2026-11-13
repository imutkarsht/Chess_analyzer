"""
Hanging, trapped and removal-of-defender detection.

These motifs all describe a piece that is (or becomes) loose. Detection uses
legal captures and escape analysis rather than static attacker maps, so pinned
attackers and routine trades do not create false alarms.

Zero Qt dependencies.
"""

from __future__ import annotations

import chess

from src.backend.analysis.tactics.board_utils import captured_piece, captured_square
from src.backend.analysis.tactics.constants import PIECE_NAMES, PIECE_VALUES, TacticalTheme
from src.backend.analysis.tactics.facts import TacticFact
from src.backend.analysis.tactics.motifs.context import MotifCtx, make_fact
from src.backend.analysis.tactics.piece_safety import get_lost_pieces, is_piece_doomed
from src.backend.analysis.tactics.see import static_exchange_evaluation


def hanging_facts(ctx: MotifCtx) -> list[TacticFact]:
    """Hanging pieces captured by the move, plus enemy pieces it newly dooms."""
    before_lost = {
        item["square"] for item in get_lost_pieces(ctx.before, ctx.enemy_color)
    }
    facts: list[TacticFact] = []

    # Capturing a piece that was already hanging is itself a hanging-piece tactic.
    if ctx.before.is_capture(ctx.move):
        square = captured_square(ctx.before, ctx.move)
        captured = captured_piece(ctx.before, ctx.move)
        if (
            captured is not None
            and captured.color == ctx.enemy_color
            and static_exchange_evaluation(ctx.before, square, ctx.color) > 0
        ):
            facts.append(
                make_fact(
                    ctx,
                    TacticalTheme.HANGING_PIECE,
                    target_square=square,
                    target_piece=PIECE_NAMES.get(captured.piece_type, "piece"),
                    targets=(chess.square_name(square),),
                    evidence="captures a piece that was already hanging",
                    material_gain_cp=PIECE_VALUES.get(captured.piece_type, 0) * 100,
                )
            )

    for item in get_lost_pieces(
        ctx.after,
        ctx.enemy_color,
        last_move=ctx.move,
        board_before=ctx.before,
    ):
        if item["square"] in before_lost:
            continue

        square = item["square_index"]
        if not is_piece_doomed(ctx.after, square, ctx.enemy_color):
            continue

        facts.append(
            make_fact(
                ctx,
                TacticalTheme.HANGING_PIECE,
                target_square=square,
                target_piece=item["piece_name"],
                targets=(item["square"],),
                evidence=f"{item['piece_name']} on {item['square']} cannot be saved",
                material_gain_cp=item.get("enemy_see_gain", 0),
            )
        )

    return facts


def removal_of_defender_fact(ctx: MotifCtx) -> TacticFact | None:
    """Capturing a defender that leaves a more valuable piece doomed."""
    if not ctx.before.is_capture(ctx.move):
        return None

    captured_sq = captured_square(ctx.before, ctx.move)
    captured = captured_piece(ctx.before, ctx.move)
    if captured is None:
        return None

    captured_value = PIECE_VALUES.get(captured.piece_type, 0)
    for square, piece in ctx.before.piece_map().items():
        if piece.color != ctx.enemy_color or square == captured_sq:
            continue
        if piece.piece_type == chess.PAWN:
            continue  # winning a pawn by removing its defender is not a tactic
        if PIECE_VALUES.get(piece.piece_type, 0) <= captured_value:
            continue  # the target must be worth more than the defender
        if captured_sq not in ctx.before.attackers(ctx.enemy_color, square):
            continue
        if not is_piece_doomed(ctx.after, square, ctx.enemy_color):
            continue

        return make_fact(
            ctx,
            TacticalTheme.REMOVAL_OF_DEFENDER,
            target_square=square,
            target_piece=PIECE_NAMES.get(piece.piece_type),
            targets=(chess.square_name(square),),
            evidence=(
                f"captured defender on {chess.square_name(captured_sq)}; "
                f"{PIECE_NAMES.get(piece.piece_type, 'piece')} on "
                f"{chess.square_name(square)} is now loose"
            ),
        )

    return None


def trapped_piece_fact(ctx: MotifCtx) -> TacticFact | None:
    """An attacked enemy piece with no legal escape and no way to be saved."""
    for target_sq in ctx.after.attacks(ctx.move.to_square):
        target = ctx.after.piece_at(target_sq)
        if target is None or target.color != ctx.enemy_color:
            continue
        if target.piece_type in (chess.KING, chess.PAWN):
            continue
        # A trapped piece has no legal escape at all. A piece that can move but
        # merely loses material is a different motif (hanging/doomed).
        if any(move.from_square == target_sq for move in ctx.after.legal_moves):
            continue
        if not is_piece_doomed(ctx.after, target_sq, ctx.enemy_color):
            continue

        return make_fact(
            ctx,
            TacticalTheme.TRAPPED_PIECE,
            target_square=target_sq,
            target_piece=PIECE_NAMES.get(target.piece_type),
            targets=(chess.square_name(target_sq),),
            evidence=(
                f"{PIECE_NAMES.get(target.piece_type, 'piece')} on "
                f"{chess.square_name(target_sq)} has no safe escape"
            ),
            include_origin=False,
        )

    return None


__all__ = ["hanging_facts", "removal_of_defender_fact", "trapped_piece_fact"]

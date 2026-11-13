"""
Fork and discovered-attack detection.

A fork is one moved piece attacking two or more meaningful targets. A
discovered attack is a friendly slider that gained a genuinely forcing target
after the move; discovered and double check are the check-specific forms.

Zero Qt dependencies.
"""

from __future__ import annotations

import chess

from src.backend.analysis.tactics.board_utils import piece_value
from src.backend.analysis.tactics.constants import PIECE_NAMES, PIECE_VALUES, TacticalTheme
from src.backend.analysis.tactics.facts import TacticFact
from src.backend.analysis.tactics.motifs.context import MotifCtx, make_fact
from src.backend.analysis.tactics.piece_safety import is_piece_doomed
from src.backend.analysis.tactics.see import (
    is_safely_placed,
    static_exchange_evaluation,
)


def fork_target_is_meaningful(
    board: chess.Board,
    target_sq: chess.Square,
    enemy_color: chess.Color,
    forking_value: int,
) -> bool:
    """King or a non-pawn piece that can actually be won."""
    target = board.piece_at(target_sq)
    if target is None or target.color != enemy_color:
        return False
    if target.piece_type == chess.KING:
        return True
    if target.piece_type == chess.PAWN:
        return False

    target_value = PIECE_VALUES.get(target.piece_type, 0)
    return target_value > forking_value or static_exchange_evaluation(
        board, target_sq, not enemy_color
    ) > 0


def fork_fact(ctx: MotifCtx) -> TacticFact | None:
    """A safe moved piece attacking two meaningful, newly attacked targets."""
    if ctx.piece.piece_type == chess.KING:
        return None
    if not is_safely_placed(ctx.after, ctx.move.to_square, ctx.color):
        return None

    forking_value = piece_value(ctx.after, ctx.move.to_square)
    before_attacks = (
        ctx.before.attacks(ctx.move.from_square)
        if ctx.before.piece_at(ctx.move.from_square)
        else chess.SquareSet()
    )

    targets: list[tuple[chess.Square, chess.Piece]] = []
    new_target = False
    for target_sq in ctx.after.attacks(ctx.move.to_square):
        if not fork_target_is_meaningful(
            ctx.after, target_sq, ctx.enemy_color, forking_value
        ):
            continue
        target = ctx.after.piece_at(target_sq)
        if target is None:
            continue
        targets.append((target_sq, target))
        if target_sq not in before_attacks:
            new_target = True

    if len(targets) < 2 or not new_target:
        return None

    names = ", ".join(
        f"{PIECE_NAMES.get(piece.piece_type, 'piece')} on {chess.square_name(sq)}"
        for sq, piece in targets
    )
    return make_fact(
        ctx,
        TacticalTheme.FORK,
        target_square=ctx.move.to_square,
        target_piece=PIECE_NAMES.get(ctx.piece.piece_type),
        targets=tuple(chess.square_name(sq) for sq, _ in targets),
        evidence=f"attacks {names}",
    )


def discovered_facts(ctx: MotifCtx) -> list[TacticFact]:
    """Discovered attack, discovered check and double check facts."""
    facts: list[TacticFact] = []
    double_check = ctx.after.is_check() and len(ctx.after.checkers()) >= 2
    discovered_check = ctx.after.is_check() and any(
        checker != ctx.move.to_square for checker in ctx.after.checkers()
    )

    if double_check:
        facts.append(_check_fact(ctx, TacticalTheme.DOUBLE_CHECK, "both pieces give check"))
    elif discovered_check:
        facts.append(
            _check_fact(ctx, TacticalTheme.DISCOVERED_CHECK, "unmasks a check")
        )

    for slider_sq in ctx.sliders:
        if slider_sq == ctx.move.to_square:
            continue

        new_targets = ctx.after.attacks(slider_sq) - ctx.before.attacks(slider_sq)

        for target_sq in new_targets:
            target = ctx.after.piece_at(target_sq)
            if target is None or target.color != ctx.enemy_color:
                continue

            # A discovered attack is only forcing when the uncovered target is
            # the king or a piece that cannot escape. A merely valuable target
            # is often a secondary alignment that the forced line ignores.
            if target.piece_type != chess.KING and not is_piece_doomed(
                ctx.after, target_sq, ctx.enemy_color
            ):
                continue

            facts.append(
                make_fact(
                    ctx,
                    TacticalTheme.DISCOVERED_ATTACK,
                    target_square=target_sq,
                    target_piece=PIECE_NAMES.get(target.piece_type),
                    targets=(chess.square_name(target_sq),),
                    evidence=(
                        f"{chess.square_name(slider_sq)} now attacks "
                        f"{chess.square_name(target_sq)}"
                    ),
                )
            )
            break

    return facts


def _check_fact(ctx: MotifCtx, motif: TacticalTheme, evidence: str) -> TacticFact:
    return make_fact(
        ctx,
        motif,
        target_square=ctx.move.to_square,
        target_piece=PIECE_NAMES.get(ctx.piece.piece_type),
        evidence=evidence,
    )


__all__ = ["discovered_facts", "fork_fact", "fork_target_is_meaningful"]

"""
Tactical motif detection engine and registry.
Detects: fork, pin, skewer, discovered attack, sacrifice, and back-rank threats.
Zero Qt dependencies — headless and independently testable.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Final

import chess

from src.backend.analysis.tactics.board_utils import (
    find_slider_ray_targets,
    is_on_segment,
    legal_defenders,
    min_attacker_value,
    piece_value,
)
from src.backend.analysis.tactics.constants import (
    KING_SKEWER_VALUE,
    MIN_SACRIFICE_DEFICIT_CP,
    PIECE_VALUES,
    TacticalTheme,
)
from src.backend.analysis.tactics.see import is_safely_placed, static_exchange_evaluation


@dataclass(frozen=True)
class MotifCtx:
    """Context container for tactical motif evaluation on a move."""

    before: chess.Board
    after: chess.Board
    move: chess.Move
    color: chess.Color
    piece: chess.Piece
    enemy_color: chess.Color
    enemy_king_sq: chess.Square | None
    sliders: chess.SquareSet


def affected_alignments(
    ctx: MotifCtx,
) -> Iterator[tuple[chess.Square, chess.Square, chess.Piece, chess.Square, chess.Piece]]:
    """
    Yields aligned (slider_sq, front_sq, front_piece, rear_sq, rear_piece) tuples
    that were either newly formed by moving the slider or unmasked along the slider's ray.
    """
    for slider_sq in ctx.sliders:
        is_moved = slider_sq == ctx.move.to_square
        for front_sq, front_p, rear_sq, rear_p in find_slider_ray_targets(
            ctx.after, slider_sq, ctx.color
        ):
            if is_moved or is_on_segment(slider_sq, front_sq, ctx.move.from_square):
                yield slider_sq, front_sq, front_p, rear_sq, rear_p


# ==============================================================================
# DETECTOR FUNCTIONS
# ==============================================================================


def _is_sacrifice(ctx: MotifCtx) -> bool:
    """
    Detects voluntary piece sacrifices resulting in a net material deficit (>= 200 cp).
    Excludes pawns, equal trades, defended pieces, and liquidation under duress/pin.
    """
    if ctx.piece.piece_type in (chess.PAWN, chess.KING):
        return False

    moved_val = piece_value(ctx.after, ctx.move.to_square)
    captured_val = piece_value(ctx.before, ctx.move.to_square)

    # Equal trades (QxQ, RxR, etc.) or winning captures are not sacrifices
    if captured_val >= moved_val:
        return False

    # Duress / concession exclusions before the move
    is_pinned_before = ctx.before.is_pinned(ctx.color, ctx.move.from_square)
    attacked_by_target = ctx.move.to_square in ctx.before.attackers(
        ctx.enemy_color, ctx.move.from_square
    )
    under_attack_by_lesser = (
        min_attacker_value(ctx.before, ctx.enemy_color, ctx.move.from_square) < moved_val
    )

    if is_pinned_before or attacked_by_target or under_attack_by_lesser:
        return False

    enemy_gain = static_exchange_evaluation(ctx.after, ctx.move.to_square, ctx.enemy_color)
    net_deficit = enemy_gain - (captured_val * 100)
    return net_deficit >= MIN_SACRIFICE_DEFICIT_CP


def _is_fork(ctx: MotifCtx) -> bool:
    """
    Detects double attacks where the moved piece simultaneously attacks 2+ targets
    (King in check, undefended piece, higher-value piece, or under-defended piece).
    Excludes pawn targets and forking pieces that can be taken for free or with profit.
    """
    if ctx.piece.piece_type == chess.KING:
        return False

    # Safety check: moved piece cannot be capturable for free or at a profit
    if not is_safely_placed(ctx.after, ctx.move.to_square, ctx.color):
        return False

    attacks = ctx.after.attacks(ctx.move.to_square)
    valuable_targets = 0

    if ctx.enemy_king_sq is not None and ctx.enemy_king_sq in attacks:
        valuable_targets += 1

    moved_val = piece_value(ctx.after, ctx.move.to_square)

    for target_sq in attacks:
        if target_sq == ctx.enemy_king_sq:
            continue
        target_p = ctx.after.piece_at(target_sq)
        if target_p and target_p.color == ctx.enemy_color:
            # Fork targets must strictly be pieces (Knight, Bishop, Rook, Queen), NOT pawns!
            if target_p.piece_type == chess.PAWN:
                continue

            target_val = PIECE_VALUES.get(target_p.piece_type, 0)
            defenders = legal_defenders(ctx.after, ctx.enemy_color, target_sq)
            if (
                len(defenders) == 0
                or target_val > moved_val
                or static_exchange_evaluation(ctx.after, target_sq, ctx.color) > 0
            ):
                valuable_targets += 1

    return valuable_targets >= 2


def _is_pin_alignment(
    ctx: MotifCtx,
    slider_sq: chess.Square,
    front_sq: chess.Square,
    front_p: chess.Piece,
    rear_sq: chess.Square,
    rear_p: chess.Piece,
) -> bool:
    """Evaluates whether an individual alignment constitutes an absolute or relative pin."""
    # 1. Absolute Pin: Rear piece is enemy King.
    if rear_p.piece_type == chess.KING:
        return True

    # 2. Relative Pin:
    # - Front piece CANNOT be a pawn (pawns are never relatively pinned to pieces).
    # - Rear piece CANNOT be a pawn or minor piece.
    if front_p.piece_type != chess.PAWN:
        if rear_p.piece_type == chess.QUEEN:
            return True
        if rear_p.piece_type == chess.ROOK and front_p.piece_type in (
            chess.KNIGHT,
            chess.BISHOP,
        ):
            slider_p = ctx.after.piece_at(slider_sq)
            slider_type = slider_p.piece_type if slider_p else None
            rear_defenders = legal_defenders(ctx.after, ctx.enemy_color, rear_sq)
            if slider_type == chess.BISHOP or len(rear_defenders) == 0:
                return True

    return False


def _has_pin(ctx: MotifCtx) -> bool:
    """Detects creation of a new absolute or relative pin."""
    return any(_is_pin_alignment(ctx, *alignment) for alignment in affected_alignments(ctx))


def _is_discovered(ctx: MotifCtx) -> bool:
    """Detects discovered attacks / discovered checks unmasked by the moved piece."""
    if ctx.after.is_check():
        checkers = ctx.after.checkers()
        if ctx.move.to_square not in checkers and len(checkers) > 0:
            return True

    for slider_sq in ctx.sliders:
        if slider_sq != ctx.move.to_square and ctx.move.from_square in ctx.after.attacks(slider_sq):
            new_targets = ctx.after.attacks(slider_sq) - ctx.before.attacks(slider_sq)
            slider_val = piece_value(ctx.after, slider_sq)

            for nt_sq in new_targets:
                nt_piece = ctx.after.piece_at(nt_sq)
                if not nt_piece or nt_piece.color != ctx.enemy_color:
                    continue

                target_val = PIECE_VALUES.get(nt_piece.piece_type, 0)
                defenders = legal_defenders(ctx.after, ctx.enemy_color, nt_sq)

                # Real tactical threat check
                if (
                    len(defenders) == 0
                    or target_val > slider_val
                    or (
                        nt_piece.piece_type != chess.PAWN
                        and static_exchange_evaluation(ctx.after, nt_sq, ctx.color) > 0
                    )
                ):
                    return True

    return False


def _is_skewer_alignment(
    ctx: MotifCtx,
    slider_sq: chess.Square,
    front_sq: chess.Square,
    front_p: chess.Piece,
    _rear_sq: chess.Square,
    rear_p: chess.Piece,
) -> bool:
    """Evaluates whether an individual alignment constitutes a tactical skewer."""
    # Rear piece cannot be a pawn
    if rear_p.piece_type == chess.PAWN:
        return False

    front_val = (
        KING_SKEWER_VALUE
        if front_p.piece_type == chess.KING
        else PIECE_VALUES.get(front_p.piece_type, 0)
    )
    rear_val = PIECE_VALUES.get(rear_p.piece_type, 0)

    # Front piece must be strictly more valuable than rear piece
    if front_val <= rear_val:
        return False

    slider_val = piece_value(ctx.after, slider_sq)
    front_defenders = legal_defenders(ctx.after, ctx.enemy_color, front_sq)
    is_undefended = len(front_defenders) == 0

    # Front piece must be genuinely compelled to move
    if front_p.piece_type == chess.KING:
        return True
    if front_p.piece_type == chess.QUEEN:
        return slider_val < 9 or is_undefended
    if front_p.piece_type == chess.ROOK:
        return slider_val < 5 or is_undefended
    return is_undefended


def _is_skewer(ctx: MotifCtx) -> bool:
    """Detects skewers (reverse pins)."""
    return any(_is_skewer_alignment(ctx, *alignment) for alignment in affected_alignments(ctx))


def _is_back_rank(ctx: MotifCtx) -> bool:
    """Detects back-rank weakness exploitation or mate infiltration."""
    back_rank = 7 if ctx.enemy_color == chess.BLACK else 0
    if ctx.enemy_king_sq is None or chess.square_rank(ctx.enemy_king_sq) != back_rank:
        return False

    adj_rank = 6 if ctx.enemy_color == chess.BLACK else 1
    king_file = chess.square_file(ctx.enemy_king_sq)
    escape_sqs = [
        chess.square(f, adj_rank) for f in range(max(0, king_file - 1), min(8, king_file + 2))
    ]
    has_luft = False
    for esq in escape_sqs:
        occ = ctx.after.piece_at(esq)
        if occ is None and esq not in ctx.after.attacks(ctx.color):
            has_luft = True
            break

    if has_luft:
        return False

    # Checkmate on the back rank
    if ctx.after.is_checkmate() and any(
        chess.square_rank(c) == back_rank for c in ctx.after.checkers()
    ):
        return True

    # Infiltration with check by Queen or Rook
    if (
        ctx.piece.piece_type in (chess.ROOK, chess.QUEEN)
        and chess.square_rank(ctx.move.to_square) == back_rank
        and ((ctx.enemy_king_sq in ctx.after.attacks(ctx.move.to_square)) or ctx.after.is_check())
    ):
        can_be_captured = any(m.to_square == ctx.move.to_square for m in ctx.after.legal_moves)
        if can_be_captured:
            defenders = legal_defenders(ctx.after, ctx.color, ctx.move.to_square)
            is_undefended = len(defenders) == 0
            is_recapturable_trade = ctx.before.is_capture(ctx.move)
            if not (is_undefended or is_recapturable_trade):
                enemy_see = static_exchange_evaluation(
                    ctx.after, ctx.move.to_square, ctx.enemy_color
                )
                if enemy_see <= 0:
                    return True
        else:
            return True

    return False


# ==============================================================================
# DETECTORS REGISTRY
# ==============================================================================

DETECTORS: Final[dict[str, Callable[[MotifCtx], bool]]] = {
    TacticalTheme.SACRIFICE.value: _is_sacrifice,
    TacticalTheme.FORK.value: _is_fork,
    TacticalTheme.PIN.value: _has_pin,
    TacticalTheme.DISCOVERED_ATTACK.value: _is_discovered,
    TacticalTheme.SKEWER.value: _is_skewer,
    TacticalTheme.BACK_RANK.value: _is_back_rank,
}


def detect_tactical_motifs(
    board_before: chess.Board,
    board_after: chess.Board,
    move_obj: chess.Move,
    color: chess.Color,
    classification: str | None = None,
) -> list[str]:
    """
    Detects tactical motifs executed by a move:
    - 'fork': Piece attacks 2+ tactical targets without hanging itself.
    - 'pin': Establishes an absolute or relative pin.
    - 'skewer': Attacks higher-value front piece exposing a rear piece.
    - 'discovered_attack': Moving unmasks a slider with real threat.
    - 'sacrifice': Voluntary material deficit for tactical/positional advantage.
    - 'back_rank': Infiltrates or mates on trapped opponent back rank.
    """
    to_sq = move_obj.to_square
    piece = board_after.piece_at(to_sq)
    if not piece:
        return []

    enemy_color = not color
    sliders = (
        board_after.pieces(chess.BISHOP, color)
        | board_after.pieces(chess.ROOK, color)
        | board_after.pieces(chess.QUEEN, color)
    )

    ctx = MotifCtx(
        before=board_before,
        after=board_after,
        move=move_obj,
        color=color,
        piece=piece,
        enemy_color=enemy_color,
        enemy_king_sq=board_after.king(enemy_color),
        sliders=sliders,
    )

    return [name for name, fn in DETECTORS.items() if fn(ctx)]

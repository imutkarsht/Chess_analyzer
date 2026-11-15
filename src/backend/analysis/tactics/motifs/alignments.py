"""
Pin and skewer detection.

A pin is an alignment where the front piece cannot leave the line without
exposing a more valuable rear piece. A skewer is the inverse: a more valuable
front piece is forced away and the lower-value rear piece is attacked. A rear
king is always a pin, never a skewer.

Zero Qt dependencies.
"""

from __future__ import annotations

import chess

from src.backend.analysis.tactics.constants import (
    KING_SKEWER_VALUE,
    PIECE_NAMES,
    PIECE_VALUES,
    TacticalTheme,
)
from src.backend.analysis.tactics.facts import TacticFact
from src.backend.analysis.tactics.motifs.context import (
    MotifCtx,
    affected_alignments,
    make_fact,
    stays_on_line,
)
from src.backend.analysis.tactics.piece_safety import is_piece_lost


def pin_is_effective(
    board: chess.Board,
    enemy_color: chess.Color,
    slider_sq: chess.Square,
    front_sq: chess.Square,
    rear_sq: chess.Square,
) -> bool:
    """True when the front piece cannot leave the line without losing the rear."""
    if board.is_pinned(enemy_color, front_sq):
        return True

    front = board.piece_at(front_sq)
    rear = board.piece_at(rear_sq)
    if front is None or rear is None or front.piece_type == chess.KING:
        return False

    front_value = PIECE_VALUES.get(front.piece_type, 0)
    rear_value = PIECE_VALUES.get(rear.piece_type, 0)
    if rear_value <= front_value:
        return False

    has_off_line_move = False
    for move in board.legal_moves:
        if move.from_square != front_sq:
            continue
        if move.to_square == slider_sq:
            return False  # captures the pinner
        if stays_on_line(move.to_square, slider_sq, rear_sq):
            continue

        has_off_line_move = True
        next_board = board.copy(stack=False)
        next_board.push(move)
        if not is_piece_lost(next_board, rear_sq, rear.color):
            return False

    # If the front piece has no legal move that leaves the line, the alignment
    # restricts nothing (e.g. a pawn whose only move is forward along the pin).
    return has_off_line_move


def skewer_is_effective(
    board: chess.Board,
    enemy_color: chess.Color,
    slider_sq: chess.Square,
    front_sq: chess.Square,
    rear_sq: chess.Square,
) -> bool:
    """
    True when the front piece is genuinely forced off the line and the rear
    piece is attacked.

    A rear king is always a pin, never a skewer. A king front piece must be in
    check. A non-king front piece must itself be hanging; otherwise it can simply
    stay on the line.
    """
    front = board.piece_at(front_sq)
    rear = board.piece_at(rear_sq)
    if front is None or rear is None or rear.piece_type == chess.KING:
        return False

    front_value = (
        KING_SKEWER_VALUE
        if front.piece_type == chess.KING
        else PIECE_VALUES.get(front.piece_type, 0)
    )
    rear_value = PIECE_VALUES.get(rear.piece_type, 0)
    if front_value <= rear_value:
        return False

    if front_sq not in board.attacks(slider_sq):
        return False

    if front.piece_type == chess.KING:
        if not board.is_check():
            return False
    elif not is_piece_lost(board, front_sq, enemy_color):
        return False

    # If the opponent can answer without moving the front piece off the line,
    # the rear piece is not forced to become vulnerable. For a check, that is
    # any interposition or capture of the checking piece by another unit. For a
    # non-king front, it is any defence or block that saves the attacked piece.
    if front.piece_type == chess.KING:
        if any(move.from_square != front_sq for move in board.legal_moves):
            return False
    else:
        for move in board.legal_moves:
            if move.from_square == front_sq:
                continue
            next_board = board.copy(stack=False)
            next_board.push(move)
            if not is_piece_lost(next_board, front_sq, enemy_color):
                return False

    exposed = False
    for move in board.legal_moves:
        if move.from_square != front_sq:
            continue
        if move.to_square == slider_sq:
            return False  # can capture the skewering piece
        if stays_on_line(move.to_square, slider_sq, rear_sq):
            return False  # can keep blocking

        next_board = board.copy(stack=False)
        next_board.push(move)
        if not is_piece_lost(next_board, rear_sq, rear.color):
            return False
        exposed = True

    return exposed


def _pin_has_consequence(
    board: chess.Board,
    enemy_color: chess.Color,
    slider_sq: chess.Square,
    front_sq: chess.Square,
    rear_sq: chess.Square,
) -> bool:
    """True when the pin prevents an escape or a meaningful attack.

    Lichess only tags tactical pins: the pinned piece cannot capture something
    it attacks, or it is attacked and cannot escape. A purely positional
    alignment is not a tactic.
    """
    front = board.piece_at(front_sq)
    slider = board.piece_at(slider_sq)
    if front is None or slider is None:
        return False

    front_value = PIECE_VALUES.get(front.piece_type, 0)
    slider_value = PIECE_VALUES.get(slider.piece_type, 0)

    # Pin prevents escape: the pinner attacks the front piece, which is more
    # valuable and cannot move off the line.
    if front_value > slider_value and is_piece_lost(board, front_sq, enemy_color):
        return True

    # Pin prevents attack: the pinned piece attacks a player piece off the pin
    # line, but cannot legally capture it.
    for target_sq in board.attacks(front_sq):
        if stays_on_line(target_sq, slider_sq, rear_sq):
            continue
        target = board.piece_at(target_sq)
        if target is None or target.color == enemy_color:
            continue
        target_value = PIECE_VALUES.get(target.piece_type, 0)
        if target_value > front_value or is_piece_lost(board, target_sq, target.color):
            return True

    return False


def alignment_facts(ctx: MotifCtx, motif: TacticalTheme) -> list[TacticFact]:
    """Pin or skewer facts for newly formed alignments."""
    facts: list[TacticFact] = []
    for slider_sq, front_sq, rear_sq in affected_alignments(ctx):
        if motif is TacticalTheme.PIN:
            effective = pin_is_effective(
                ctx.after, ctx.enemy_color, slider_sq, front_sq, rear_sq
            ) and (
                ctx.after.is_pinned(ctx.enemy_color, front_sq)
                or _pin_has_consequence(
                    ctx.after, ctx.enemy_color, slider_sq, front_sq, rear_sq
                )
            )
        else:
            effective = skewer_is_effective(
                ctx.after, ctx.enemy_color, slider_sq, front_sq, rear_sq
            )
        if not effective:
            continue

        rear = ctx.after.piece_at(rear_sq)
        # A pin can be exploited by capturing either side of the line; the
        # front piece is often the one that falls. A skewer always wins the
        # lower-value rear piece.
        targets = (
            (chess.square_name(front_sq), chess.square_name(rear_sq))
            if motif is TacticalTheme.PIN
            else (chess.square_name(rear_sq),)
        )
        facts.append(
            make_fact(
                ctx,
                motif,
                target_square=rear_sq,
                target_piece=PIECE_NAMES.get(rear.piece_type) if rear else None,
                targets=targets,
                evidence=(
                    f"line {chess.square_name(slider_sq)}-"
                    f"{chess.square_name(front_sq)}-{chess.square_name(rear_sq)}"
                ),
                line=(
                    chess.square_name(slider_sq),
                    chess.square_name(front_sq),
                    chess.square_name(rear_sq),
                ),
            )
        )
    return facts


__all__ = ["alignment_facts", "pin_is_effective", "skewer_is_effective"]

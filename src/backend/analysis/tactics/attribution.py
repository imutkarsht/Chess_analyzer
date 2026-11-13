"""
One-reply-ahead loss attribution.

The old pipeline counted a piece as "hung" the moment it was attacked, even when
the opponent never punished it, and it could not see losses that only appear
after a quiet reply (the Qe3 / ...Bg5 case). Attribution resolves the move the
opponent actually played and separates:

- immediate: the piece is loose right after the user's move;
- punished: the piece is captured, or becomes doomed after the reply.

Losses are deduplicated by (ply, square) and are never charged to sound moves,
book moves or intentional sacrifices.

Zero Qt dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

from src.backend.analysis.tactics.board_utils import captured_piece, captured_square
from src.backend.analysis.tactics.constants import (
    BAD_MOVE_CLASSIFICATIONS,
    GOOD_MOVE_WP_DROP_THRESHOLD,
    PIECE_NAMES,
    PIECE_VALUES,
    SOUND_CLASSIFICATIONS,
    SOUND_MOVE_WP_DROP_THRESHOLD,
    WINNING_WP_THRESHOLD,
)
from src.backend.analysis.tactics.contexts import MoveCtx
from src.backend.analysis.tactics.piece_safety import (
    get_lost_pieces,
    is_piece_doomed,
    is_piece_lost,
)


@dataclass(frozen=True)
class LossRecord:
    """A single piece loss attributed to one ply."""

    square: str
    piece_name: str
    kind: str  # "immediate" | "punished"
    see_gain_cp: int
    punished_by: str | None = None
    punished_by_uci: str | None = None
    line: tuple[str, ...] = ()


@dataclass(frozen=True)
class _PunishedPiece:
    piece_name: str
    see_gain_cp: int


def is_sound_move(ctx: MoveCtx) -> bool:
    """True when the move should never be blamed for offered material."""
    return (
        ctx.is_book
        or ctx.classification in SOUND_CLASSIFICATIONS
        or (
            ctx.classification == "Good"
            and ctx.wp_drop < GOOD_MOVE_WP_DROP_THRESHOLD
        )
        or (
            ctx.wp_drop < SOUND_MOVE_WP_DROP_THRESHOLD
            and ctx.player_wp_after >= WINNING_WP_THRESHOLD
        )
    )


def is_blunder(ctx: MoveCtx) -> bool:
    """True when a loss should increment the hanging-blunder counter."""
    return ctx.classification in BAD_MOVE_CLASSIFICATIONS


def resolve_losses(
    user_ctx: MoveCtx,
    next_ctx: MoveCtx | None,
    target_color: chess.Color,
) -> list[LossRecord]:
    """Resolve immediate and punished losses for one user move."""
    if user_ctx.move_obj is None or user_ctx.board_after is None:
        return []
    if is_sound_move(user_ctx):
        return []

    hanging_before = {
        item["square"] for item in get_lost_pieces(user_ctx.board_before, target_color)
    }
    newly_hung = {
        item["square"]: item
        for item in get_lost_pieces(
            user_ctx.board_after,
            target_color,
            last_move=user_ctx.move_obj,
            board_before=user_ctx.board_before,
        )
        if item["square"] not in hanging_before
    }

    punished, punishing_san, punishing_uci, line = _resolve_punishment(
        user_ctx, next_ctx, target_color, hanging_before
    )

    records: list[LossRecord] = []
    for square_name, item in newly_hung.items():
        is_punished = square_name in punished
        records.append(
            LossRecord(
                square=square_name,
                piece_name=str(item.get("piece_name", "piece")),
                kind="punished" if is_punished else "immediate",
                see_gain_cp=int(item.get("enemy_see_gain", 0)),
                punished_by=punishing_san if is_punished else None,
                punished_by_uci=punishing_uci if is_punished else None,
                line=line if is_punished else (),
            )
        )

    for square_name, item in punished.items():
        if square_name in newly_hung:
            continue
        records.append(
            LossRecord(
                square=square_name,
                piece_name=item.piece_name,
                kind="punished",
                see_gain_cp=item.see_gain_cp,
                punished_by=punishing_san,
                punished_by_uci=punishing_uci,
                line=line,
            )
        )

    return records


def _resolve_punishment(
    user_ctx: MoveCtx,
    next_ctx: MoveCtx | None,
    target_color: chess.Color,
    hanging_before: set[str],
) -> tuple[dict[str, _PunishedPiece], str | None, str | None, tuple[str, ...]]:
    """Pieces the opponent actually captured or left doomed after the reply."""
    punished: dict[str, _PunishedPiece] = {}
    if next_ctx is None or next_ctx.move_obj is None or next_ctx.board_after is None:
        return punished, None, None, ()

    punishing_san = next_ctx.san or None
    punishing_uci = next_ctx.move_obj.uci()
    line = (punishing_san,) if punishing_san else ()

    _record_capture_punishment(user_ctx, next_ctx, target_color, punished)
    _record_quiet_punishments(next_ctx, target_color, hanging_before, punished)

    return punished, punishing_san, punishing_uci, line


def _record_capture_punishment(
    user_ctx: MoveCtx,
    next_ctx: MoveCtx,
    target_color: chess.Color,
    punished: dict[str, _PunishedPiece],
) -> None:
    reply = next_ctx.move_obj
    if reply is None or not next_ctx.board_before.is_capture(reply):
        return
    if _is_routine_recapture(user_ctx, next_ctx):
        return

    square = captured_square(next_ctx.board_before, reply)
    piece = captured_piece(next_ctx.board_before, reply)
    if piece is None or piece.color != target_color:
        return
    if not is_piece_lost(next_ctx.board_before, square, target_color):
        return

    punished[chess.square_name(square)] = _PunishedPiece(
        piece_name=PIECE_NAMES.get(piece.piece_type, "piece"),
        see_gain_cp=PIECE_VALUES.get(piece.piece_type, 0) * 100,
    )


def _record_quiet_punishments(
    next_ctx: MoveCtx,
    target_color: chess.Color,
    hanging_before: set[str],
    punished: dict[str, _PunishedPiece],
) -> None:
    if next_ctx.board_after is None:
        return

    for square, piece in next_ctx.board_after.piece_map().items():
        if piece.color != target_color or piece.piece_type == chess.KING:
            continue
        square_name = chess.square_name(square)
        if square_name in hanging_before or square_name in punished:
            continue
        if not is_piece_doomed(next_ctx.board_after, square, target_color):
            continue
        punished[square_name] = _PunishedPiece(
            piece_name=PIECE_NAMES.get(piece.piece_type, "piece"),
            see_gain_cp=PIECE_VALUES.get(piece.piece_type, 0) * 100,
        )


def _is_routine_recapture(user_ctx: MoveCtx, reply_ctx: MoveCtx) -> bool:
    """True when the reply is an equal-or-better recapture of the user's move."""
    if (
        user_ctx.move_obj is None
        or reply_ctx.move_obj is None
        or not user_ctx.board_before.is_capture(user_ctx.move_obj)
        or not reply_ctx.board_before.is_capture(reply_ctx.move_obj)
        or user_ctx.move_obj.to_square != reply_ctx.move_obj.to_square
    ):
        return False

    captured_by_user = captured_piece(user_ctx.board_before, user_ctx.move_obj)
    captured_by_reply = captured_piece(reply_ctx.board_before, reply_ctx.move_obj)
    if captured_by_user is None or captured_by_reply is None:
        return False

    return PIECE_VALUES.get(captured_by_user.piece_type, 0) >= PIECE_VALUES.get(
        captured_by_reply.piece_type, 0
    )


__all__ = ["LossRecord", "is_blunder", "is_sound_move", "resolve_losses"]

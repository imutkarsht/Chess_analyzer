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

from src.backend.analysis.tactics.constants import (
    BAD_MOVE_CLASSIFICATIONS,
    PIECE_NAMES,
    PIECE_VALUES,
    SOUND_CLASSIFICATIONS,
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


def is_sound_move(ctx: MoveCtx) -> bool:
    """True when the move should never be blamed for offered material."""
    return (
        ctx.is_book
        or ctx.classification in SOUND_CLASSIFICATIONS
        or (ctx.classification == "Good" and ctx.wp_drop < 0.05)
        or (ctx.wp_drop < 0.03 and ctx.player_wp_after >= 0.50)
    )


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
    hanging_after = get_lost_pieces(
        user_ctx.board_after,
        target_color,
        last_move=user_ctx.move_obj,
        board_before=user_ctx.board_before,
    )
    newly_hung = {
        item["square"]: item
        for item in hanging_after
        if item["square"] not in hanging_before
    }

    punished: dict[str, dict[str, object]] = {}
    punishing_san: str | None = None
    punishing_uci: str | None = None
    line: tuple[str, ...] = ()

    if next_ctx is not None and next_ctx.move_obj is not None and next_ctx.board_after is not None:
        punishing_san = next_ctx.san or None
        punishing_uci = next_ctx.move_obj.uci()
        line = (punishing_san,) if punishing_san else ()

        if next_ctx.board_before.is_capture(next_ctx.move_obj) and not _is_routine_recapture(
            user_ctx, next_ctx
        ):
            captured_square, captured_piece = _captured_piece(
                next_ctx.board_before, next_ctx.move_obj
            )
            if (
                captured_piece is not None
                and captured_piece.color == target_color
                and is_piece_lost(next_ctx.board_before, captured_square, target_color)
            ):
                punished[chess.square_name(captured_square)] = {
                    "piece_name": PIECE_NAMES.get(captured_piece.piece_type, "piece"),
                    "see_gain_cp": PIECE_VALUES.get(captured_piece.piece_type, 0) * 100,
                }

        for square, piece in next_ctx.board_after.piece_map().items():
            if piece.color != target_color or piece.piece_type == chess.KING:
                continue
            square_name = chess.square_name(square)
            if square_name in hanging_before or square_name in punished:
                continue
            if not is_piece_doomed(next_ctx.board_after, square, target_color):
                continue
            punished[square_name] = {
                "piece_name": PIECE_NAMES.get(piece.piece_type, "piece"),
                "see_gain_cp": PIECE_VALUES.get(piece.piece_type, 0) * 100,
            }

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
                piece_name=str(item["piece_name"]),
                kind="punished",
                see_gain_cp=int(item["see_gain_cp"]),
                punished_by=punishing_san,
                punished_by_uci=punishing_uci,
                line=line,
            )
        )

    return records


def is_blunder(ctx: MoveCtx) -> bool:
    """True when a loss should increment the hanging-blunder counter."""
    return ctx.classification in BAD_MOVE_CLASSIFICATIONS


def _captured_piece(
    board: chess.Board,
    move: chess.Move,
) -> tuple[chess.Square, chess.Piece | None]:
    if board.is_en_passant(move):
        square = chess.square(
            chess.square_file(move.to_square),
            chess.square_rank(move.from_square),
        )
    else:
        square = move.to_square
    return square, board.piece_at(square)


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

    _, captured_by_user = _captured_piece(user_ctx.board_before, user_ctx.move_obj)
    _, captured_by_reply = _captured_piece(reply_ctx.board_before, reply_ctx.move_obj)
    if captured_by_user is None or captured_by_reply is None:
        return False

    return PIECE_VALUES.get(captured_by_user.piece_type, 0) >= PIECE_VALUES.get(
        captured_by_reply.piece_type, 0
    )


__all__ = ["LossRecord", "is_blunder", "is_sound_move", "resolve_losses"]

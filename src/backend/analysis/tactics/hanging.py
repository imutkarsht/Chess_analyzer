"""
Backwards-compatible hanging-piece API.

The real implementation lives in ``piece_safety.py`` and uses legal captures
plus escape analysis. This module keeps the historical names stable for
callers and tests.

Zero Qt dependencies.
"""

from __future__ import annotations

from typing import Any

import chess

from src.backend.analysis.tactics.piece_safety import (
    get_lost_pieces,
    is_piece_doomed,
    is_piece_lost,
    piece_loss_evidence,
)


def is_piece_hanging(
    board: chess.Board,
    square: chess.Square,
    color: chess.Color,
    last_move: chess.Move | None = None,
    board_before: chess.Board | None = None,
) -> bool:
    """True when the piece can be won and is not merely a routine recapture."""
    piece = board.piece_at(square)
    if piece is None or piece.color != color or piece.piece_type == chess.KING:
        return False
    if not is_piece_lost(board, square, color):
        return False

    return any(
        item["square"] == chess.square_name(square)
        for item in get_lost_pieces(
            board, color, last_move=last_move, board_before=board_before
        )
    )


def get_hanging_pieces(
    board: chess.Board,
    color: chess.Color,
    last_move: chess.Move | None = None,
    board_before: chess.Board | None = None,
) -> list[dict[str, Any]]:
    """All pieces of ``color`` that the opponent can win by legal captures."""
    return get_lost_pieces(
        board, color, last_move=last_move, board_before=board_before
    )


__all__ = [
    "get_hanging_pieces",
    "is_piece_doomed",
    "is_piece_hanging",
    "piece_loss_evidence",
]

"""
Deterministic hanging piece detection.
Zero Qt dependencies — headless and independently testable.
"""

from __future__ import annotations

from typing import Any

import chess

from src.backend.analysis.tactics.board_utils import (
    legal_defenders,
    min_attacker_value,
    piece_value,
)
from src.backend.analysis.tactics.constants import PIECE_NAMES, PIECE_VALUES
from src.backend.analysis.tactics.see import static_exchange_evaluation


def is_piece_hanging(
    board: chess.Board,
    square: chess.Square,
    color: chess.Color,
    last_move: chess.Move | None = None,
    board_before: chess.Board | None = None,
) -> bool:
    """
    Determines if the piece on `square` belonging to `color` is hanging on `board`.

    A friendly piece on square is hanging if and only if:
    1. It is not a King.
    2. It is attacked by at least one enemy piece.
    3. Loss of material condition:
       - Completely undefended, OR
       - Attacked by a strictly lesser-value enemy piece, OR
       - Under-defended (enemy SEE > 0).
    4. Excludes equal or winning trades/recaptures on `last_move` (including en passant).
    """
    piece = board.piece_at(square)
    if not piece or piece.color != color or piece.piece_type == chess.KING:
        return False

    enemy_color = not color
    enemy_attackers = board.attackers(enemy_color, square)
    if not enemy_attackers:
        return False

    p_val = piece_value(board, square)
    friendly_defenders = legal_defenders(board, color, square)
    min_att_val = min_attacker_value(board, enemy_color, square)

    is_undefended = len(friendly_defenders) == 0
    attacked_by_lesser = min_att_val < p_val
    enemy_see_gain = static_exchange_evaluation(board, square, enemy_color)
    is_underdefended = enemy_see_gain > 0

    if not (is_undefended or attacked_by_lesser or is_underdefended):
        return False

    # Recapture / equal trade exclusion
    if last_move and board_before is not None and last_move.to_square == square:
        captured = board_before.piece_at(square)
        if captured is None and board_before.is_en_passant(last_move):
            ep_sq = chess.square(
                chess.square_file(last_move.to_square),
                chess.square_rank(last_move.from_square),
            )
            captured = board_before.piece_at(ep_sq)
        if captured:
            captured_val = PIECE_VALUES.get(captured.piece_type, 0)
            if captured_val >= p_val:
                return False

    return True


def get_hanging_pieces(
    board: chess.Board,
    color: chess.Color,
    last_move: chess.Move | None = None,
    board_before: chess.Board | None = None,
) -> list[dict[str, Any]]:
    """
    Finds all pieces belonging to `color` that are hanging on `board`.

    Returns a list of detailed dicts for each hanging piece:
    - square: SAN square name (e.g. 'e4')
    - square_index: int (0..63)
    - piece_name: str ('pawn', 'knight', ...)
    - piece_type: chess.PieceType
    - is_undefended: bool
    - attacked_by_lesser: bool
    - attacker_count: int
    - defender_count: int
    - enemy_see_gain: int (centipawns gained by opponent capturing)
    """
    hanging: list[dict[str, Any]] = []
    enemy_color = not color

    for square, piece in board.piece_map().items():
        if piece.color == color and is_piece_hanging(board, square, color, last_move, board_before):
            p_val = piece_value(board, square)
            friendly_defs = legal_defenders(board, color, square)
            min_att_val = min_attacker_value(board, enemy_color, square)
            enemy_see = static_exchange_evaluation(board, square, enemy_color)

            hanging.append(
                {
                    "square": chess.square_name(square),
                    "square_index": square,
                    "piece_name": PIECE_NAMES.get(piece.piece_type, "piece"),
                    "piece_type": piece.piece_type,
                    "is_undefended": len(friendly_defs) == 0,
                    "attacked_by_lesser": min_att_val < p_val,
                    "attacker_count": len(board.attackers(enemy_color, square)),
                    "defender_count": len(friendly_defs),
                    "enemy_see_gain": enemy_see,
                }
            )

    return hanging

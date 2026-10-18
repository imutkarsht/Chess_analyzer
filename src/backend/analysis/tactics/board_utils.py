"""
Board geometry, ray tracing, and piece safety utility functions.
Zero Qt dependencies — headless and independently testable.
"""

from __future__ import annotations

import chess

from src.backend.analysis.tactics.constants import PIECE_VALUES


def piece_value(board: chess.Board, sq: chess.Square) -> int:
    """Returns the piece value at `sq` (0 if empty or King)."""
    piece = board.piece_at(sq)
    return PIECE_VALUES.get(piece.piece_type, 0) if piece else 0


def legal_defenders(
    board: chess.Board,
    color: chess.Color,
    square: chess.Square,
) -> list[chess.Square]:
    """
    Returns friendly pieces defending `square` that are not absolutely pinned
    away from `square` along a different ray.
    """
    return [
        sq
        for sq in board.attackers(color, square)
        if not (board.is_pinned(color, sq) and square not in board.pin(color, sq))
    ]


def min_attacker_value(
    board: chess.Board,
    color: chess.Color,
    square: chess.Square,
    default: int = 99,
) -> int:
    """Returns the minimum piece value among pieces of `color` attacking `square`."""
    attackers = board.attackers(color, square)
    if not attackers:
        return default
    return min(piece_value(board, sq) for sq in attackers)


def find_slider_ray_targets(
    board: chess.Board,
    slider_sq: chess.Square,
    color: chess.Color,
) -> list[tuple[chess.Square, chess.Piece, chess.Square, chess.Piece]]:
    """
    Finds all aligned pairs of enemy pieces (front_sq, front_piece, rear_sq, rear_piece)
    along straight rays extending outwards from `slider_sq`.
    Guarantees physical order along each ray outwards from `slider_sq`.
    """
    enemy_color = not color
    results: list[tuple[chess.Square, chess.Piece, chess.Square, chess.Piece]] = []
    slider_piece = board.piece_at(slider_sq)
    if not slider_piece:
        return results

    directions: list[tuple[int, int]] = []
    if slider_piece.piece_type in (chess.BISHOP, chess.QUEEN):
        directions.extend([(1, 1), (1, -1), (-1, 1), (-1, -1)])
    if slider_piece.piece_type in (chess.ROOK, chess.QUEEN):
        directions.extend([(1, 0), (-1, 0), (0, 1), (0, -1)])

    slider_file = chess.square_file(slider_sq)
    slider_rank = chess.square_rank(slider_sq)

    for delta_file, delta_rank in directions:
        curr_file = slider_file + delta_file
        curr_rank = slider_rank + delta_rank
        front_sq: chess.Square | None = None
        front_piece: chess.Piece | None = None

        while 0 <= curr_file < 8 and 0 <= curr_rank < 8:
            sq = chess.square(curr_file, curr_rank)
            piece = board.piece_at(sq)
            if piece is not None:
                if front_sq is None:
                    if piece.color == enemy_color:
                        front_sq = sq
                        front_piece = piece
                    else:
                        break  # Friendly piece blocks ray immediately
                else:
                    if piece.color == enemy_color and front_piece is not None:
                        results.append((front_sq, front_piece, sq, piece))
                    break  # Second piece blocks further vision on this ray
            curr_file += delta_file
            curr_rank += delta_rank

    return results


def is_on_segment(a: chess.Square, b: chess.Square, c: chess.Square) -> bool:
    """Returns True if square `c` lies strictly between `a` and `b` on a straight ray."""
    a_file, a_rank = chess.square_file(a), chess.square_rank(a)
    b_file, b_rank = chess.square_file(b), chess.square_rank(b)
    c_file, c_rank = chess.square_file(c), chess.square_rank(c)
    delta_file, delta_rank = b_file - a_file, b_rank - a_rank

    if delta_file != 0 and delta_rank != 0 and abs(delta_file) != abs(delta_rank):
        return False

    c_delta_file, c_delta_rank = c_file - a_file, c_rank - a_rank
    if delta_file == 0:
        if c_delta_file != 0:
            return False
        return (0 < c_delta_rank < delta_rank) or (delta_rank < c_delta_rank < 0)
    if delta_rank == 0:
        if c_delta_rank != 0:
            return False
        return (0 < c_delta_file < delta_file) or (delta_file < c_delta_file < 0)

    step_f = 1 if delta_file > 0 else -1
    step_r = 1 if delta_rank > 0 else -1
    c_step_f = 1 if c_delta_file > 0 else (-1 if c_delta_file < 0 else 0)
    c_step_r = 1 if c_delta_rank > 0 else (-1 if c_delta_rank < 0 else 0)

    if (step_f, step_r) != (c_step_f, c_step_r):
        return False

    return abs(c_delta_file) == abs(c_delta_rank) and 0 < abs(c_delta_file) < abs(delta_file)


def to_user_cp(cp: int | None, is_user_white: bool) -> int | None:
    """Converts a White-perspective score to user perspective."""
    if cp is None:
        return None
    return cp if is_user_white else -cp


def to_user_wp(wp: float, is_user_white: bool) -> float:
    """Converts a White win-probability (0..1) to user perspective."""
    return wp if is_user_white else (1.0 - wp)

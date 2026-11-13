"""
Static Exchange Evaluation (SEE) using only legal captures.

Implements the recursive swap-off algorithm from the Chess Programming Wiki:
the side to move may capture, then the opponent may recapture, and so on. A
side always has the option to stop, so every returned value is non-negative.

Because every candidate capture comes from ``board.legal_moves``, pins, checks,
king safety, castling and en passant are handled by python-chess itself.

Zero Qt dependencies -- headless and independently testable.
"""

from __future__ import annotations

import chess

from src.backend.analysis.tactics.board_utils import piece_value
from src.backend.analysis.tactics.constants import PIECE_VALUES


def _legal_captures_on_square(
    board: chess.Board,
    square: chess.Square,
    attacking_color: chess.Color,
) -> list[chess.Move]:
    """Legal captures on ``square`` by ``attacking_color``, cheapest attacker first.

    ``board`` may have either side to move; a cheap copy is used when the turn
    does not already match ``attacking_color``.
    """
    work = board
    if work.turn != attacking_color:
        work = board.copy(stack=False)
        work.turn = attacking_color

    return sorted(
        (move for move in work.legal_moves if move.to_square == square),
        key=lambda move: piece_value(work, move.from_square),
    )


def _see(
    board: chess.Board,
    square: chess.Square,
    attacking_color: chess.Color,
) -> int:
    """Recursive swap-off on a board where ``attacking_color`` is to move."""
    if board.piece_at(square) is None:
        return 0

    captures = _legal_captures_on_square(board, square, attacking_color)
    if not captures:
        return 0

    best_gain = 0
    for move in captures:
        captured = board.piece_at(square)
        if captured is None:
            continue

        captured_value = piece_value(board, square) * 100
        promotion_gain = 0
        if move.promotion is not None:
            promotion_gain = (PIECE_VALUES.get(move.promotion, 1) - 1) * 100

        board.push(move)
        try:
            recapture_gain = _see(board, square, not attacking_color)
        finally:
            board.pop()

        gain = captured_value + promotion_gain - recapture_gain
        if gain > best_gain:
            best_gain = gain

    return best_gain


def static_exchange_evaluation(
    board: chess.Board,
    square: chess.Square,
    attacking_color: chess.Color,
) -> int:
    """
    Net material gain in centipawns for ``attacking_color`` if the exchange on
    ``square`` is played out optimally.

    The attacker can always choose not to capture, so the result is >= 0.
    """
    work = board
    if work.turn != attacking_color:
        work = board.copy(stack=False)
        work.turn = attacking_color
    return _see(work, square, attacking_color)


def is_safely_placed(
    board_after: chess.Board,
    square: chess.Square,
    color: chess.Color,
) -> bool:
    """True when the piece on ``square`` cannot be won profitably next move."""
    piece = board_after.piece_at(square)
    if piece is None or piece.color != color or piece.piece_type == chess.KING:
        return True

    if not _legal_captures_on_square(board_after, square, not color):
        return True

    return static_exchange_evaluation(board_after, square, not color) <= 0

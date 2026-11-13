"""
Piece-safety analysis built on legal moves and static exchange evaluation.

Static attacker maps answer "who attacks this square"; this module answers the
only question that matters for tactics: "can the opponent win this piece with a
legal move, and can its owner save it?" That distinction removes the classic
false positives from pinned attackers, checks and illegal king captures.

Zero Qt dependencies -- headless and independently testable.
"""

from __future__ import annotations

from typing import Any

import chess

from src.backend.analysis.tactics.board_utils import (
    captured_piece,
    legal_defenders,
    piece_value,
)
from src.backend.analysis.tactics.constants import PIECE_NAMES, PIECE_VALUES
from src.backend.analysis.tactics.see import (
    legal_captures_on_square,
    static_exchange_evaluation,
)


def piece_loss_evidence(
    board: chess.Board,
    square: chess.Square,
    color: chess.Color,
) -> dict[str, Any]:
    """
    Evidence that the piece on ``square`` belonging to ``color`` can be won.

    ``lost`` is true only when a legal capture yields a positive SEE for the
    opponent. The representative punishing move is the cheapest legal attacker.
    """
    empty = {
        "lost": False,
        "best_gain_cp": 0,
        "punishing_move": None,
        "punishing_uci": None,
        "is_undefended": False,
        "attacker_count": 0,
        "defender_count": 0,
    }

    piece = board.piece_at(square)
    if piece is None or piece.color != color or piece.piece_type == chess.KING:
        return empty

    enemy_color = not color

    # En passant removes a pawn that is not on the move's destination square,
    # so it has to be handled before the ordinary capture scan.
    en_passant = _en_passant_capture_on(board, square, enemy_color)
    if en_passant is not None:
        return {
            "lost": True,
            "best_gain_cp": 100,
            "punishing_move": en_passant,
            "punishing_uci": en_passant.uci(),
            "is_undefended": len(legal_defenders(board, color, square)) == 0,
            "attacker_count": 1,
            "defender_count": len(legal_defenders(board, color, square)),
        }

    captures = legal_captures_on_square(board, square, enemy_color)
    if not captures:
        return empty

    see_gain = static_exchange_evaluation(board, square, enemy_color)
    punishing_move = captures[0]
    defender_count = len(legal_defenders(board, color, square))

    return {
        "lost": see_gain > 0,
        "best_gain_cp": max(0, see_gain),
        "punishing_move": punishing_move,
        "punishing_uci": punishing_move.uci(),
        "is_undefended": defender_count == 0,
        "attacker_count": len(captures),
        "defender_count": defender_count,
    }


def is_piece_lost(
    board: chess.Board,
    square: chess.Square,
    color: chess.Color,
) -> bool:
    """True when the opponent can win the piece on ``square`` by legal captures."""
    return piece_loss_evidence(board, square, color)["lost"]


def can_save_piece(board: chess.Board, square: chess.Square, color: chess.Color) -> bool:
    """
    True when the owner has a legal move that prevents the piece from being won.

    The check covers moving the piece, defending it, blocking the attack and
    counter-attacking. ``board.turn`` is set to ``color`` on a copy if needed.
    """
    piece = board.piece_at(square)
    if piece is None or piece.color != color:
        return False

    work = board
    if work.turn != color:
        work = board.copy(stack=False)
        work.turn = color

    for move in work.legal_moves:
        next_board = work.copy(stack=False)
        next_board.push(move)

        if move.from_square == square:
            if next_board.piece_at(move.to_square) and not is_piece_lost(
                next_board, move.to_square, color
            ):
                return True
        elif not is_piece_lost(next_board, square, color):
            return True

    return False


def is_piece_doomed(board: chess.Board, square: chess.Square, color: chess.Color) -> bool:
    """True when the piece is lost and its owner cannot save it with one move."""
    if not is_piece_lost(board, square, color):
        return False
    return not can_save_piece(board, square, color)


def _is_routine_recapture(
    board: chess.Board,
    square: chess.Square,
    last_move: chess.Move | None,
    board_before: chess.Board | None,
) -> bool:
    """True for an equal-or-better recapture on the square just captured."""
    if last_move is None or board_before is None or last_move.to_square != square:
        return False

    captured = captured_piece(board_before, last_move)
    current = board.piece_at(square)
    if captured is None or current is None:
        return False

    captured_value = PIECE_VALUES.get(captured.piece_type, 0)
    current_value = PIECE_VALUES.get(current.piece_type, 0)
    return captured_value >= current_value


def get_lost_pieces(
    board: chess.Board,
    color: chess.Color,
    last_move: chess.Move | None = None,
    board_before: chess.Board | None = None,
) -> list[dict[str, Any]]:
    """
    All pieces of ``color`` that can be won by the opponent on ``board``.

    Routine equal-or-better recaptures on ``last_move.to_square`` are excluded so
    normal trades are never reported as hanging pieces.

    When the owner is in check, static hanging detection is not meaningful: the
    check must be answered first. This is what removes the classic
    "piece in check position is hanging" false positive.
    """
    if board.turn == color and board.is_check():
        return []

    lost: list[dict[str, Any]] = []

    for square, piece in board.piece_map().items():
        if piece.color != color or piece.piece_type == chess.KING:
            continue

        evidence = piece_loss_evidence(board, square, color)
        if not evidence["lost"]:
            continue
        if _is_routine_recapture(board, square, last_move, board_before):
            continue

        punishing_move = evidence["punishing_move"]
        punishing_san = None
        if punishing_move is not None:
            try:
                punishing_san = board.san(punishing_move)
            except Exception:  # noqa: BLE001 - malformed positions must not crash
                punishing_san = None

        lost.append(
            {
                "square": chess.square_name(square),
                "square_index": square,
                "piece_name": PIECE_NAMES.get(piece.piece_type, "piece"),
                "piece_type": piece.piece_type,
                "is_undefended": evidence["is_undefended"],
                "attacked_by_lesser": _attacked_by_lesser(board, square, color),
                "attacker_count": evidence["attacker_count"],
                "defender_count": evidence["defender_count"],
                "enemy_see_gain": evidence["best_gain_cp"],
                "punishing_uci": evidence["punishing_uci"],
                "punishing_san": punishing_san,
            }
        )

    return lost


def _en_passant_capture_on(
    board: chess.Board,
    square: chess.Square,
    attacking_color: chess.Color,
) -> chess.Move | None:
    """A legal en passant capture that removes the pawn on ``square``."""
    work = board
    if work.turn != attacking_color:
        work = board.copy(stack=False)
        work.turn = attacking_color

    for move in work.legal_moves:
        if not work.is_en_passant(move):
            continue
        captured_square = chess.square(
            chess.square_file(move.to_square),
            chess.square_rank(move.from_square),
        )
        if captured_square == square:
            return move
    return None


def _attacked_by_lesser(board: chess.Board, square: chess.Square, color: chess.Color) -> bool:
    """True when a legal attacker of strictly lesser value exists."""
    piece = board.piece_at(square)
    if piece is None or piece.color != color:
        return False

    value = piece_value(board, square)
    for move in legal_captures_on_square(board, square, not color):
        if piece_value(board, move.from_square) < value:
            return True
    return False

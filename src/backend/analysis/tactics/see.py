"""
Static Exchange Evaluation (SEE) minimax implementation.
Zero Qt dependencies — headless and independently testable.
"""

from __future__ import annotations

import chess

from src.backend.analysis.tactics.board_utils import legal_defenders, piece_value


def static_exchange_evaluation(
    board: chess.Board,
    square: chess.Square,
    attacking_color: chess.Color,
) -> int:
    """
    Computes Static Exchange Evaluation (SEE) score in centipawns on `square`
    from the perspective of `attacking_color`.

    Simulates the sequence of best captures and recaptures on a single target
    square:
    - Least valuable legal attacker captures first.
    - Captures by pinned pieces are filtered unless along the pin ray.
    - King captures are prohibited if enemy defenders remain.
    - Handles pawn promotions (+800 cp net).

    Returns:
        Net material gain in centipawns (>= 0 if attacking side can choose
        not to continue when unfavorable).
    """
    target_piece = board.piece_at(square)
    if not target_piece:
        return 0

    attackers = legal_defenders(board, attacking_color, square)
    if not attackers:
        return 0

    enemy_color = not attacking_color
    enemy_defenders = legal_defenders(board, enemy_color, square)

    # Find the least valuable legal attacker
    best_attacker: chess.Square | None = None
    min_val = 99999

    for sq in attackers:
        attacker_piece = board.piece_at(sq)
        if not attacker_piece:
            continue
        # King cannot capture if defended by enemy
        if attacker_piece.piece_type == chess.KING and enemy_defenders:
            continue
        val = piece_value(board, sq)
        if val < min_val:
            min_val = val
            best_attacker = sq

    if best_attacker is None:
        return 0

    captured_val = piece_value(board, square) * 100

    board_copy = board.copy(stack=False)
    attacker_p = board.piece_at(best_attacker)
    promotion = None
    if attacker_p and attacker_p.piece_type == chess.PAWN and chess.square_rank(square) in (0, 7):
        promotion = chess.QUEEN
        captured_val += 800  # Promotion adds net Queen value over pawn

    board_copy.push(chess.Move(best_attacker, square, promotion=promotion))

    recapture_gain = static_exchange_evaluation(board_copy, square, enemy_color)
    return max(0, captured_val - recapture_gain)


def is_safely_placed(
    board_after: chess.Board,
    sq: chess.Square,
    color: chess.Color,
) -> bool:
    """
    Returns True if the piece on `sq` belonging to `color` is not capturable
    for free or with net material profit by the enemy on their immediate turn.
    """
    can_be_captured = any(m.to_square == sq for m in board_after.legal_moves)
    if not can_be_captured:
        return True
    defenders = legal_defenders(board_after, color, sq)
    if not defenders:
        return False
    return static_exchange_evaluation(board_after, sq, not color) <= 0

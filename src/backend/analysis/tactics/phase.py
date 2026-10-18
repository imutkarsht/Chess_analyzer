"""
Game phase classification (Opening, Middlegame, Endgame).
Zero Qt dependencies — headless and independently testable.
"""

from __future__ import annotations

import chess

from src.backend.analysis.tactics.constants import (
    ENDGAME_LOW_TOTAL_NON_PAWN,
    ENDGAME_NO_QUEEN_TOTAL_MAX,
    ENDGAME_SOLO_PIECE_MAX,
    OPENING_MAX_PLY,
    OPENING_MIN_NON_PAWN,
    PIECE_VALUES,
    GamePhase,
)


def non_pawn_material(board: chess.Board, color: chess.Color) -> int:
    """Calculates total non-pawn, non-king material value for a given color."""
    return sum(
        PIECE_VALUES[p.piece_type]
        for p in board.piece_map().values()
        if p.color == color and p.piece_type not in (chess.KING, chess.PAWN)
    )


def classify_game_phase(
    board: chess.Board,
    ply: int,
    is_book_move: bool = False,
) -> str:
    """
    Classifies a position into 'opening', 'middlegame', or 'endgame'.

    Rules:
    - Opening: In opening book OR ply <= 16 with queens present and
      non-pawn material >= 20 points for each side.
    - Endgame:
        * Neither side has a queen and total non-pawn material <= 26 points, OR
        * Total non-pawn material for both sides <= 18 points, OR
        * Either side has non-pawn material <= 6 points.
    - Middlegame: All positions between Opening and Endgame.
    """
    if is_book_move:
        return GamePhase.OPENING.value

    white_non_pawn = non_pawn_material(board, chess.WHITE)
    black_non_pawn = non_pawn_material(board, chess.BLACK)
    total_non_pawn = white_non_pawn + black_non_pawn

    has_white_queen = bool(board.pieces(chess.QUEEN, chess.WHITE))
    has_black_queen = bool(board.pieces(chess.QUEEN, chess.BLACK))

    # Endgame check:
    # 1. Neither side has a queen and total non-pawn material is moderately low (<= 26)
    # 2. Total non-pawn material is <= 18 points
    # 3. Either side has <= 6 points of non-pawn pieces
    if (
        (
            not has_white_queen
            and not has_black_queen
            and total_non_pawn <= ENDGAME_NO_QUEEN_TOTAL_MAX
        )
        or total_non_pawn <= ENDGAME_LOW_TOTAL_NON_PAWN
        or white_non_pawn <= ENDGAME_SOLO_PIECE_MAX
        or black_non_pawn <= ENDGAME_SOLO_PIECE_MAX
    ):
        return GamePhase.ENDGAME.value

    # Opening check:
    if (
        ply <= OPENING_MAX_PLY
        and white_non_pawn >= OPENING_MIN_NON_PAWN
        and black_non_pawn >= OPENING_MIN_NON_PAWN
    ):
        return GamePhase.OPENING.value

    return GamePhase.MIDDLEGAME.value

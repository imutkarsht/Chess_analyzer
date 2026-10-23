"""Presentation helpers for engine lines.

The lines returned here are already White-perspective ``EngineLine`` objects,
so callers never have to know whose turn it is.
"""

from __future__ import annotations

import chess

from src.backend.analysis.engine_line import (
    EngineLine,
    line_from_cached,
    position_after,
)
from src.backend.storage.models import MoveAnalysis


def lines_for_move(
    move: MoveAnalysis, chess960: bool = False
) -> tuple[list[EngineLine], str]:
    """Engine lines for the position *before* ``move`` and its FEN.

    MultiPV lines belong to the position the move was played from.  When the
    move delivers checkmate the game is over, so the other entries are
    alternatives to the mating move rather than continuations: keep only the
    line that starts with the played move (falling back to the top line).
    """
    try:
        board = chess.Board(move.fen_before, chess960=chess960)
        turn = board.turn
    except (AssertionError, ValueError):
        board = None
        turn = chess.WHITE

    lines = [
        line_from_cached(pv_data, turn, rank=index + 1, board=board)
        for index, pv_data in enumerate(move.multi_pvs or [])
    ]

    if not move.is_checkmate:
        return lines, move.fen_before

    for line in lines:
        if line.first_move == move.uci:
            return [line], move.fen_before
    return lines[:1], move.fen_before


def lines_for_index(
    moves: list[MoveAnalysis], index: int, chess960: bool = False
) -> tuple[list[EngineLine], str]:
    """Lines matching the board after ``index`` (``-1`` = initial position).

    The board shows the position *after* the selected move, so the matching
    cached analysis is the next move's ``fen_before``.  For the final move
    there is no successor: a checkmate keeps its mating line, otherwise the
    position after the move is returned so it can be analysed live instead of
    showing the position *before* the move (which the board no longer shows).
    """
    if not moves:
        return [], chess.STARTING_FEN
    if index < 0:
        # The position before the first move is the initial position.
        return lines_for_move(moves[0], chess960=chess960)
    if index + 1 < len(moves):
        return lines_for_move(moves[index + 1], chess960=chess960)

    move = moves[index]
    if move.is_checkmate:
        return lines_for_move(move, chess960=chess960)
    return [], position_after(move, chess960=chess960)

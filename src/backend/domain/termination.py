# SPDX-License-Identifier: GPL-3.0-only
"""Board-aware game termination detection and display descriptions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import chess

if TYPE_CHECKING:
    from src.backend.storage.models import MoveAnalysis


def detect_termination(
    headers: dict,
    moves: list[MoveAnalysis],
    starting_fen: str | None = None,
    chess960: bool = False,
) -> tuple[str, str]:
    """Return ``(termination_mode, termination_description)``.

    Descriptions match the wording used by Chess.com and Lichess.
    """
    result = headers.get("Result", "*").strip()
    header_term = headers.get("Termination", "").strip()
    term_lower = header_term.lower()

    # Replay board state to check physical terminal rules
    board = chess.Board(starting_fen) if starting_fen else chess.Board(chess960=chess960)
    for move in moves:
        try:
            board.push_uci(move.uci)
        except Exception:
            break

    winner_name = None
    if result == "1-0":
        winner_name = headers.get("White", "White")
    elif result == "0-1":
        winner_name = headers.get("Black", "Black")

    # 1. Authoritative Board States
    if board.is_checkmate():
        if result == "1-0":
            return "checkmate", f"{headers.get('White', 'White')} won by checkmate"
        elif result == "0-1":
            return "checkmate", f"{headers.get('Black', 'Black')} won by checkmate"
        return "checkmate", "Game won by checkmate"

    if board.is_stalemate():
        return "stalemate", "Drawn by stalemate"

    if board.is_insufficient_material():
        return "insufficient_material", "Drawn by insufficient material"

    if (
        board.is_fivefold_repetition()
        or board.can_claim_threefold_repetition()
        or board.is_repetition(3)
    ):
        return "threefold_repetition", "Drawn by repetition"

    if (
        board.is_seventyfive_moves()
        or board.can_claim_fifty_moves()
        or board.is_fifty_moves()
    ):
        return "fifty_moves", "Drawn by 50-move rule"

    # 2. Explicit PGN Headers (Chess.com / Lichess strings)
    if "checkmate" in term_lower or "check mate" in term_lower:
        if winner_name:
            return "checkmate", f"{winner_name} won by checkmate"
        return "checkmate", "Game won by checkmate"

    if "stalemate" in term_lower:
        return "stalemate", "Drawn by stalemate"

    if "resign" in term_lower:
        if winner_name:
            return "resignation", f"{winner_name} won by resignation"
        return "resignation", "Game won by resignation"

    if any(
        keyword in term_lower
        for keyword in (
            "abandon",
            "disconnected",
            "left the game",
            "no-show",
            "no show",
        )
    ):
        if winner_name:
            return "abandonment", f"{winner_name} won - game abandoned"
        return "abandonment", "Game abandoned"

    if any(
        keyword in term_lower
        for keyword in ("time", "clock", "timeout", "flag", "forfeit")
    ):
        # Check for timeout vs insufficient material
        if result in ("1/2-1/2", "Draw"):
            return "timeout_insufficient", "Drawn on time (insufficient material)"
        if winner_name:
            return "timeout", f"{winner_name} won on time"
        return "timeout", "Game won on time"

    if any(
        keyword in term_lower for keyword in ("rules", "cheat", "disqualif")
    ):
        if winner_name:
            return "rules_violation", f"{winner_name} won by rules violation"
        return "rules_violation", "Game won by rules violation"

    if "repetition" in term_lower:
        return "threefold_repetition", "Drawn by repetition"

    if "50-move" in term_lower or "fifty-move" in term_lower:
        return "fifty_moves", "Drawn by 50-move rule"

    if "insufficient" in term_lower:
        return "insufficient_material", "Drawn by insufficient material"

    if any(
        keyword in term_lower for keyword in ("agreed", "agreement", "mutual")
    ):
        return "agreed_draw", "Drawn by agreement"

    # 3. Fallback when Header is Missing or Generic ("Normal")
    if moves:
        # Check if losing player timed out (clock == 0)
        if result == "1-0":
            # Black lost. If Black's last clock is 0, it's a timeout.
            black_clocks = [
                move.time_left
                for move in moves
                if move.ply % 2 == 0 and move.time_left is not None
            ]
            if black_clocks and black_clocks[-1] == 0:
                return "timeout", f"{headers.get('White', 'White')} won on time"
        elif result == "0-1":
            # White lost. If White's last clock is 0, it's a timeout.
            white_clocks = [
                move.time_left
                for move in moves
                if move.ply % 2 == 1 and move.time_left is not None
            ]
            if white_clocks and white_clocks[-1] == 0:
                return "timeout", f"{headers.get('Black', 'Black')} won on time"

    # Result-based fallback
    if result == "1-0":
        return "resignation", f"{headers.get('White', 'White')} won by resignation"
    elif result == "0-1":
        return "resignation", f"{headers.get('Black', 'Black')} won by resignation"
    elif result in ("1/2-1/2", "Draw"):
        return "agreed_draw", "Drawn by agreement"

    return "unterminated", "Game unterminated"


__all__ = ["detect_termination"]

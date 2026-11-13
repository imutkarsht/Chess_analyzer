"""
Parsed move context shared by attribution, motif detection and game analysis.

Parsing happens once per game so the tactics pipeline never rebuilds boards or
re-parses SAN/UCI in inner loops.

Zero Qt dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import chess

from src.backend.analysis.tactics.board_utils import to_user_cp, to_user_wp
from src.backend.analysis.tactics.phase import classify_game_phase


@dataclass(frozen=True)
class MoveCtx:
    """Immutable data context for a single analyzed ply."""

    ply: int
    move_number: int
    san: str
    uci: str
    fen_before: str
    fen_after: str
    classification: str
    eval_user_cp: int | None
    eval_after_user: int | None
    eval_diff: int | None
    wp_drop: float
    player_wp_before: float
    player_wp_after: float
    is_user_move: bool
    is_book: bool
    is_mating_move: bool
    is_checkmate_move: bool
    board_before: chess.Board
    board_after: chess.Board | None
    move_obj: chess.Move | None
    phase: str
    time_spent: float | None = None
    time_left: float | None = None
    opening_name: str = ""
    explanation: str = ""
    engine_pv: tuple[str, ...] = ()


def build_contexts(
    moves_data: list[dict[str, Any]],
    is_user_white: bool,
) -> list[MoveCtx | None]:
    """Parse every ply once into an immutable context."""
    return [
        _build_context(move_dict, index, is_user_white)
        for index, move_dict in enumerate(moves_data)
    ]


def _build_context(
    move_dict: dict[str, Any],
    index: int,
    is_user_white: bool,
) -> MoveCtx | None:
    ply = move_dict.get("ply", index)
    move_number = move_dict.get("move_number", (ply + 1) // 2)
    san = move_dict.get("san", "")
    uci = move_dict.get("uci", "")
    fen_before = move_dict.get("fen_before", "")
    fen_after = move_dict.get("fen_after", "")
    classification = move_dict.get("classification", "")
    is_book = bool(move_dict.get("is_book_move", move_dict.get("is_book", False)))

    player_wp_before = to_user_wp(
        move_dict.get("win_chance_before", 0.5), is_user_white
    )
    player_wp_after = to_user_wp(
        move_dict.get("win_chance_after", 0.5), is_user_white
    )

    try:
        board_before = chess.Board(fen_before) if fen_before else chess.Board()
    except Exception:  # noqa: BLE001 - malformed PGN must never crash analysis
        return None

    is_white_turn = board_before.turn == chess.WHITE if fen_before else (ply % 2 == 0)
    move_obj, board_after = _parse_move(board_before, uci, san, fen_after)
    if board_after is not None:
        fen_after = board_after.fen()

    eval_user_cp = to_user_cp(move_dict.get("eval_before_cp"), is_user_white)
    eval_after_user = to_user_cp(move_dict.get("eval_after_cp"), is_user_white)
    eval_diff = (
        eval_user_cp - eval_after_user
        if eval_user_cp is not None and eval_after_user is not None
        else move_dict.get("eval_diff")
    )

    return MoveCtx(
        ply=ply,
        move_number=move_number,
        san=san,
        uci=uci,
        fen_before=fen_before,
        fen_after=fen_after,
        classification=classification,
        eval_user_cp=eval_user_cp,
        eval_after_user=eval_after_user,
        eval_diff=eval_diff,
        wp_drop=max(0.0, player_wp_before - player_wp_after),
        player_wp_before=player_wp_before,
        player_wp_after=player_wp_after,
        is_user_move=is_white_turn == is_user_white,
        is_book=is_book,
        is_mating_move=_is_mating_move(move_dict, is_user_white),
        is_checkmate_move=bool(san) and san.endswith("#"),
        board_before=board_before,
        board_after=board_after,
        move_obj=move_obj,
        phase=classify_game_phase(board_before, ply, is_book_move=is_book),
        time_spent=move_dict.get("time_spent"),
        time_left=move_dict.get("time_left"),
        opening_name=move_dict.get("opening_name", ""),
        explanation=move_dict.get("explanation", ""),
        engine_pv=_engine_pv(move_dict),
    )


def _parse_move(
    board_before: chess.Board,
    uci: str,
    san: str,
    fen_after: str,
) -> tuple[chess.Move | None, chess.Board | None]:
    """Validate the played move and return the resulting board."""
    if not (uci or san):
        if not fen_after:
            return None, None
        try:
            return None, chess.Board(fen_after)
        except ValueError:
            return None, None

    try:
        move_obj = chess.Move.from_uci(uci) if uci else board_before.parse_san(san)
    except (ValueError, chess.IllegalMoveError):
        return None, None

    if move_obj not in board_before.legal_moves:
        return None, None

    if fen_after:
        try:
            return move_obj, chess.Board(fen_after)
        except ValueError:
            return None, None

    board_after = board_before.copy()
    board_after.push(move_obj)
    return move_obj, board_after


def _is_mating_move(move_dict: dict[str, Any], is_user_white: bool) -> bool:
    """True when the move leaves a forced mate for the player to move."""
    eval_after_mate = move_dict.get("eval_after_mate")
    if eval_after_mate is None:
        return False
    return (is_user_white and eval_after_mate > 0) or (
        not is_user_white and eval_after_mate < 0
    )


def _engine_pv(move_dict: dict[str, Any]) -> tuple[str, ...]:
    """Best stored PV, preferring the first multi-PV entry."""
    multi_pvs = move_dict.get("multi_pvs") or []
    if multi_pvs:
        pv = multi_pvs[0].get("pv") or []
        if pv:
            return tuple(pv)
    return tuple(move_dict.get("pv") or ())


__all__ = ["MoveCtx", "build_contexts"]

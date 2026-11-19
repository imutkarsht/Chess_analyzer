# SPDX-License-Identifier: GPL-3.0-only
"""Shared PGN header and mainline metadata extraction."""

from __future__ import annotations

import io
from collections.abc import Mapping
from dataclasses import dataclass, replace

import chess.pgn

from src.utils.time_control import classify_time_control


@dataclass(frozen=True)
class PgnMetadata:
    """Raw metadata from one PGN game, plus final-position details if parsed."""

    white: str = "?"
    black: str = "?"
    result: str = "*"
    date: str = "?"
    event: str = "?"
    white_elo: str | None = None
    black_elo: str | None = None
    time_control: str = ""
    opening: str | None = None
    eco: str | None = None
    termination: str | None = None
    variant: str | None = None
    white_rating_diff: str | None = None
    black_rating_diff: str | None = None
    starting_fen: str | None = None
    move_count: int | None = None
    last_fen: str | None = None
    last_move_uci: str | None = None


def metadata_from_headers(headers: Mapping[str, str]) -> PgnMetadata:
    """Map PGN headers without parsing the movetext."""
    return PgnMetadata(
        white=headers.get("White", "?"),
        black=headers.get("Black", "?"),
        result=headers.get("Result", "*"),
        date=headers.get("Date", "?"),
        event=headers.get("Event", "?"),
        white_elo=headers.get("WhiteElo"),
        black_elo=headers.get("BlackElo"),
        time_control=headers.get("TimeControl", ""),
        opening=headers.get("Opening"),
        eco=headers.get("ECO"),
        termination=headers.get("Termination"),
        variant=headers.get("Variant"),
        white_rating_diff=headers.get("WhiteRatingDiff"),
        black_rating_diff=headers.get("BlackRatingDiff"),
        starting_fen=headers.get("FEN"),
    )


def metadata_from_game(game: chess.pgn.Game) -> PgnMetadata:
    """Map headers and compute the final position from an already parsed game."""
    board = game.end().board()
    last_move_uci = board.peek().uci() if board.move_stack else None
    return replace(
        metadata_from_headers(game.headers),
        move_count=(len(board.move_stack) + 1) // 2,
        last_fen=board.fen(),
        last_move_uci=last_move_uci,
    )


def extract_pgn_metadata(
    pgn: str | None,
    *,
    require_moves: bool = False,
) -> PgnMetadata | None:
    """Parse one PGN string; return ``None`` for absent/malformed games."""
    if not pgn:
        return None

    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
    except Exception:
        return None

    if game is None or (require_moves and game.next() is None):
        return None

    try:
        return metadata_from_game(game)
    except Exception:
        return None


def parse_pgn_headers(
    pgn: str,
    default_white="?",
    default_black="?",
    default_result="*",
    default_date_str="????.??.??",
    default_white_elo=None,
    default_black_elo=None,
    default_time_class=None,
    default_opening=None,
):
    """Extract API-cache fields from PGN, falling back to caller defaults."""
    metadata = extract_pgn_metadata(pgn)
    if metadata is None:
        return (
            default_white,
            default_black,
            default_result,
            default_date_str,
            default_white_elo,
            default_black_elo,
            default_time_class,
            default_opening,
            None,
        )

    white = metadata.white if metadata.white not in ("", "?") else default_white
    black = metadata.black if metadata.black not in ("", "?") else default_black
    result = (
        metadata.result if metadata.result not in ("", "*") else default_result
    )

    date_str = metadata.date
    if date_str in ("", "????.??.??"):
        date_str = default_date_str
    if date_str and "." in date_str:
        date_str = date_str.replace(".", "-")

    white_elo = (
        metadata.white_elo
        if metadata.white_elo not in (None, "", "?")
        else default_white_elo
    )
    black_elo = (
        metadata.black_elo
        if metadata.black_elo not in (None, "", "?")
        else default_black_elo
    )

    time_class = default_time_class
    if metadata.time_control and metadata.time_control not in ("?", "-"):
        classified = classify_time_control(metadata.time_control)
        if classified != "Unknown":
            time_class = classified

    if not time_class:
        event = metadata.event
        if event and event not in ("?", "Lichess Game", "Chess.com Game"):
            time_class = event

    opening = (
        metadata.opening
        if metadata.opening not in (None, "", "?")
        else default_opening
    )

    return (
        white,
        black,
        result,
        date_str,
        white_elo,
        black_elo,
        time_class,
        opening,
        metadata.move_count,
    )

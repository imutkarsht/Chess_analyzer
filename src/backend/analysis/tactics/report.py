"""
Per-game tactical report projection.

Turns the validated ``analyze_game_tactics`` output into a small, UI-ready list
of entries. The projection is deliberately Qt-free so it can be tested headless
and reused by any presentation layer.

Zero Qt dependencies.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import chess


class MoveLike(Protocol):
    """Minimal move shape needed to resolve a tactic to a board index."""

    ply: int
    uci: str
    san: str
    move_number: int
    fen_before: str


@dataclass(frozen=True)
class GameTacticEntry:
    """One tactical event in a game, ready for display."""

    role: str  # executed | allowed | missed | lost | won
    motif: str
    move_index: int
    ply: int
    move_label: str
    summary: str
    classification: str = ""
    eval_text: str = ""
    target_square: str | None = None
    target_piece: str | None = None
    details: tuple[str, ...] = ()
    line: tuple[str, ...] = ()


@dataclass(frozen=True)
class GameTacticsReport:
    """All tactical events for one side of one game."""

    side: str
    executed: tuple[GameTacticEntry, ...] = ()
    allowed: tuple[GameTacticEntry, ...] = ()
    missed: tuple[GameTacticEntry, ...] = ()
    lost: tuple[GameTacticEntry, ...] = ()
    won: tuple[GameTacticEntry, ...] = ()

    @property
    def total(self) -> int:
        return sum(len(section) for section in self.sections)

    @property
    def sections(self) -> tuple[tuple[GameTacticEntry, ...], ...]:
        return (self.executed, self.allowed, self.missed, self.lost, self.won)

    @property
    def summary(self) -> dict[str, int]:
        return {
            "executed": len(self.executed),
            "allowed": len(self.allowed),
            "missed": len(self.missed),
            "lost": len(self.lost),
            "won": len(self.won),
        }

    @property
    def is_empty(self) -> bool:
        return self.total == 0


def build_game_tactics_report(
    tactics: dict[str, Any],
    moves: Sequence[MoveLike],
    side: str = "white",
) -> GameTacticsReport:
    """Project the tactics summary into role-based display sections."""
    if not moves:
        return GameTacticsReport(side=side)

    by_ply = {move.ply: index for index, move in enumerate(moves)}
    by_uci = {move.uci: index for index, move in enumerate(moves) if move.uci}

    executed = _executed_entries(tactics, moves, by_ply, by_uci)
    allowed = _allowed_entries(tactics, moves, by_ply, by_uci)
    missed = _missed_entries(tactics, moves, by_ply, by_uci)
    lost = _lost_entries(tactics, moves, by_ply, by_uci)
    won = _won_entries(tactics, moves, by_ply, by_uci)

    return GameTacticsReport(
        side=side,
        executed=executed,
        allowed=allowed,
        missed=missed,
        lost=lost,
        won=won,
    )


def _executed_entries(
    tactics: dict[str, Any],
    moves: Sequence[MoveLike],
    by_ply: dict[int, int],
    by_uci: dict[str, int],
) -> tuple[GameTacticEntry, ...]:
    entries: list[GameTacticEntry] = []
    for detail in tactics.get("tactical_motifs_details") or []:
        motif = detail.get("motif", "")
        if detail.get("role") != "executed" or motif == "hanging_piece":
            continue
        index = _move_index(detail.get("ply"), detail.get("uci"), by_ply, by_uci)
        if index is None:
            continue
        entries.append(
            _entry(
                role="executed",
                motif=motif,
                move=moves[index],
                index=index,
                summary=str(detail.get("evidence") or ""),
                detail=detail,
            )
        )
    return tuple(sorted(entries, key=lambda entry: entry.move_index))


def _allowed_entries(
    tactics: dict[str, Any],
    moves: Sequence[MoveLike],
    by_ply: dict[int, int],
    by_uci: dict[str, int],
) -> tuple[GameTacticEntry, ...]:
    entries: list[GameTacticEntry] = []
    for detail in tactics.get("tactical_motifs_details") or []:
        motif = detail.get("motif", "")
        if detail.get("role") != "allowed" or motif == "hanging_piece":
            continue

        index = _move_index(detail.get("blunder_ply"), None, by_ply, by_uci)
        if index is None:
            reply_index = _move_index(
                detail.get("ply"), detail.get("uci"), by_ply, by_uci
            )
            if reply_index is not None and reply_index > 0:
                index = reply_index - 1
        if index is None:
            continue

        punishment = detail.get("san") or "the reply"
        entries.append(
            _entry(
                role="allowed",
                motif=motif,
                move=moves[index],
                index=index,
                summary=f"Allowed {punishment}",
                detail=detail,
            )
        )
    return tuple(sorted(entries, key=lambda entry: entry.move_index))


def _missed_entries(
    tactics: dict[str, Any],
    moves: Sequence[MoveLike],
    by_ply: dict[int, int],
    by_uci: dict[str, int],
) -> tuple[GameTacticEntry, ...]:
    entries: list[GameTacticEntry] = []
    for detail in tactics.get("missed_tactics_details") or []:
        index = _move_index(detail.get("ply"), detail.get("uci"), by_ply, by_uci)
        if index is None:
            continue

        motif = str(detail.get("motif") or "hanging_piece")
        if motif == "back_rank_mate":
            summary = f"Missed mate in one ({detail.get('missed_san', '?')})"
        else:
            piece = str(detail.get("missed_piece") or "piece").title()
            square = detail.get("missed_square") or "?"
            summary = f"Missed {piece.lower()} on {square}"

        entries.append(
            _entry(
                role="missed",
                motif=motif,
                move=moves[index],
                index=index,
                summary=summary,
                detail=detail,
            )
        )
    return tuple(sorted(entries, key=lambda entry: entry.move_index))


def _lost_entries(
    tactics: dict[str, Any],
    moves: Sequence[MoveLike],
    by_ply: dict[int, int],
    by_uci: dict[str, int],
) -> tuple[GameTacticEntry, ...]:
    groups: dict[int, list[dict[str, Any]]] = {}
    for detail in tactics.get("hung_pieces_details") or []:
        index = _move_index(detail.get("ply"), detail.get("uci"), by_ply, by_uci)
        if index is None:
            continue
        groups.setdefault(index, []).append(detail)

    entries: list[GameTacticEntry] = []
    for index, details in groups.items():
        pieces: list[tuple[str, str]] = []
        tooltip: list[str] = []
        for detail in details:
            piece = str(detail.get("piece_name") or "piece")
            square = detail.get("square") or "?"
            pieces.append((piece, square))
            if detail.get("loss_kind") == "punished" and detail.get("punished_by"):
                tooltip.append(f"{piece.title()} {square} · {detail['punished_by']}")
            else:
                tooltip.append(f"{piece.title()} {square} · immediate")

        summary = tooltip[0] if len(details) == 1 else _pieces_summary(pieces)
        entries.append(
            _entry(
                role="lost",
                motif="hanging_piece",
                move=moves[index],
                index=index,
                summary=summary,
                detail=details[0],
                details=tuple(tooltip),
                piece_name=pieces[0][0],
            )
        )
    return tuple(sorted(entries, key=lambda entry: entry.move_index))


def _won_entries(
    tactics: dict[str, Any],
    moves: Sequence[MoveLike],
    by_ply: dict[int, int],
    by_uci: dict[str, int],
) -> tuple[GameTacticEntry, ...]:
    groups: dict[int, list[dict[str, Any]]] = {}
    for detail in tactics.get("opp_captured_details") or []:
        index = _move_index(detail.get("ply"), detail.get("uci"), by_ply, by_uci)
        if index is None:
            continue
        groups.setdefault(index, []).append(detail)

    entries: list[GameTacticEntry] = []
    for index, details in groups.items():
        pieces = [
            (str(detail.get("piece_name") or "piece"), detail.get("square") or "?")
            for detail in details
        ]
        summary = (
            f"Won {pieces[0][0]} {pieces[0][1]}"
            if len(pieces) == 1
            else _pieces_summary(pieces)
        )
        entries.append(
            _entry(
                role="won",
                motif="hanging_piece",
                move=moves[index],
                index=index,
                summary=summary,
                detail=details[0],
                details=tuple(f"{piece.title()} {square}" for piece, square in pieces),
                piece_name=pieces[0][0],
            )
        )
    return tuple(sorted(entries, key=lambda entry: entry.move_index))


def _entry(
    *,
    role: str,
    motif: str,
    move: MoveLike,
    index: int,
    summary: str,
    detail: dict[str, Any],
    details: tuple[str, ...] = (),
    piece_name: str | None = None,
) -> GameTacticEntry:
    return GameTacticEntry(
        role=role,
        motif=motif,
        move_index=index,
        ply=move.ply,
        move_label=_move_label(move),
        summary=summary,
        classification=str(detail.get("classification") or ""),
        eval_text=_eval_text(detail),
        target_square=detail.get("target_square"),
        target_piece=piece_name or detail.get("target_piece"),
        details=details,
        line=tuple(detail.get("line") or ()),
    )


def _pieces_summary(pieces: list[tuple[str, str]]) -> str:
    """Compact summary for multiple pieces lost or won on one move."""
    if not pieces:
        return ""
    if len(pieces) == 1:
        piece, square = pieces[0]
        return f"{piece.title()} {square}"
    if len({piece for piece, _ in pieces}) == 1:
        squares = ", ".join(square for _, square in pieces)
        return f"{pieces[0][0].title()}s {squares}"
    return ", ".join(f"{piece.title()} {square}" for piece, square in pieces)


def _move_index(
    ply: Any,
    uci: Any,
    by_ply: dict[int, int],
    by_uci: dict[str, int],
) -> int | None:
    if isinstance(ply, int) and ply in by_ply:
        return by_ply[ply]
    if isinstance(uci, str) and uci in by_uci:
        return by_uci[uci]
    return None


def _move_label(move: MoveLike) -> str:
    prefix = f"{move.move_number}." if _is_white_move(move) else f"{move.move_number}..."
    return f"{prefix} {move.san}"


def _is_white_move(move: MoveLike) -> bool:
    try:
        return chess.Board(move.fen_before).turn == chess.WHITE
    except Exception:  # noqa: BLE001 - malformed FEN must not break the report
        return move.ply % 2 == 0


def _eval_text(detail: dict[str, Any]) -> str:
    before = detail.get("eval_before_cp")
    after = detail.get("eval_after_cp")
    if before is None or after is None:
        return ""
    return f"{_format_cp(before)} → {_format_cp(after)}"


def _format_cp(cp: int) -> str:
    return f"{cp / 100:+.1f}"


__all__ = ["GameTacticEntry", "GameTacticsReport", "build_game_tactics_report"]

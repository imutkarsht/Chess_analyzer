"""Source-independent candidates passed from the Load Game dialog to import."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from src.backend.models.game_info import GameInfo
from src.backend.storage.game_identity import game_identity_key
from src.backend.storage.pgn_parser import PGNIndex
from src.utils.time_control import classify_time_control

from .boards import summarize_pgn

_TIME_CONTROL_RE = re.compile(r'\[TimeControl "([^"]+)"\]')
_NAMED_TIME_CLASSES = {
    "ultrabullet": "UltraBullet",
    "ultra bullet": "UltraBullet",
    "bullet": "Bullet",
    "blitz": "Blitz",
    "rapid": "Rapid",
    "classical": "Classical",
    "daily": "Daily",
    "correspondence": "Daily",
}

_GENERIC_EVENTS = {
    "rated blitz game",
    "rated rapid game",
    "rated bullet game",
    "rated ultrabullet game",
    "rated classical game",
    "live chess",
    "chess.com game",
    "lichess game",
    "?",
}


def _meaningful_event(event: str | None) -> str:
    value = (event or "").strip()
    return "" if value.casefold() in _GENERIC_EVENTS else value


def _resolve_time_class(raw: str | None, pgn: str | None) -> str:
    """Prefer PGN TimeControl; fall back to the API's named speed."""
    match = _TIME_CONTROL_RE.search(pgn or "")
    if match:
        classified = classify_time_control(match.group(1))
        if classified != "Unknown":
            return classified

    value = (raw or "").strip()
    named = _NAMED_TIME_CLASSES.get(value.casefold())
    if named:
        return named
    if value.casefold() in ("live chess", "standard"):
        return "Unknown"
    return value if value and value not in ("?", "-") else "Unknown"


@dataclass
class GameCandidate:
    candidate_id: int
    source: str
    white: str
    black: str
    date: str
    result: str
    time_class: str
    event: str
    opening: str | None
    white_elo: str | None
    black_elo: str | None
    move_count: int | None
    last_fen: str | None = None
    source_data: dict[str, Any] | None = None
    pgn: str | None = None
    index: PGNIndex | None = None
    summary_index: int | None = None
    in_history: bool = False

    def pgn_text(self) -> str:
        if self.pgn is not None:
            return self.pgn
        if self.index is not None and self.summary_index is not None:
            return self.index.game_text(self.summary_index)
        return ""

    @property
    def identity_key(self) -> tuple[str, str, str, str]:
        return game_identity_key(self.date, self.white, self.black, self.result)

    @property
    def search_blob(self) -> str:
        return " ".join(
            (
                self.date,
                self.white,
                self.black,
                self.result,
                self.time_class,
                self.event,
                self.opening or "",
            )
        ).casefold()


@dataclass
class GameBatch:
    label: str
    candidates: list[GameCandidate]

    @classmethod
    def from_game_infos(
        cls,
        infos: list[GameInfo],
        saved_keys: set[tuple[str, str, str, str]],
        label: str,
    ) -> GameBatch:
        candidates = []
        for position, info in enumerate(infos):
            parsed_moves, last_fen = summarize_pgn(info.pgn)
            candidates.append(
                GameCandidate(
                    candidate_id=position,
                    source=info.source,
                    white=info.white,
                    black=info.black,
                    date=info.date,
                    result=info.result,
                    time_class=_resolve_time_class(info.time_class, info.pgn),
                    event="",
                    opening=info.opening,
                    white_elo=info.white_elo,
                    black_elo=info.black_elo,
                    move_count=(
                        info.move_count
                        if info.move_count is not None
                        else parsed_moves
                    ),
                    last_fen=last_fen,
                    source_data=info.to_dict(),
                    pgn=info.pgn,
                    in_history=game_identity_key(
                        info.date, info.white, info.black, info.result
                    )
                    in saved_keys,
                )
            )
        return cls(label=label, candidates=candidates)

    @classmethod
    def from_pgn_index(
        cls,
        index: PGNIndex,
        saved_keys: set[tuple[str, str, str, str]],
        label: str,
    ) -> GameBatch:
        candidates = []
        for position, game in enumerate(index.games):
            in_history = (
                game_identity_key(game.date, game.white, game.black, game.result)
                in saved_keys
            )
            candidates.append(
                GameCandidate(
                    candidate_id=position,
                    source="file",
                    white=game.white,
                    black=game.black,
                    date=game.date,
                    result=game.result,
                    time_class=classify_time_control(game.time_control),
                    event=_meaningful_event(game.event),
                    opening=game.opening,
                    white_elo=game.white_elo,
                    black_elo=game.black_elo,
                    move_count=None,
                    index=index,
                    summary_index=position,
                    in_history=in_history,
                )
            )
        return cls(label=label, candidates=candidates)

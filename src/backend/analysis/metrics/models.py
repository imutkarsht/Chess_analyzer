"""
Data models and typed structures for metrics aggregation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from src.backend.analysis.tactics import analyze_game_tactics
from src.backend.storage.pgn_parser import PGNParser
from src.utils.logger import logger

from .constants import QUALITY_NAMES
from .termination import classify_termination


class Outcome(StrEnum):
    WIN = "win"
    DRAW = "draw"
    LOSS = "loss"


def outcome_for(result: str, user_color: str) -> Outcome | None:
    """
    Determine the normalized game outcome for the given player color.
    Returns None for unfinished or unparseable games (e.g. '*').
    """
    res = (result or "").strip()
    if res in ("1/2-1/2", "Draw", "draw", "1/2"):
        return Outcome.DRAW
    if res == "1-0":
        return Outcome.WIN if user_color == "white" else Outcome.LOSS
    if res == "0-1":
        return Outcome.WIN if user_color == "black" else Outcome.LOSS
    return None


@dataclass
class GameRecord:
    """Parsed, strongly-typed representation of a single game for statistical analysis."""

    game_id: str | None
    raw_game: dict[str, Any]
    user_color: str
    result: str
    outcome: Outcome | None
    term_type: str
    draw_type: str | None
    speed: str
    opp_name: str
    opp_rating_str: str
    opp_elo: int
    opening: str
    eco: str
    game_acc: float
    quality_counts: dict[str, int]
    blunders_count: int
    tactics_data: dict[str, Any] | None
    game_meta: dict[str, Any] = field(default_factory=dict)

    @property
    def is_win(self) -> bool:
        return self.outcome == Outcome.WIN

    @property
    def is_draw(self) -> bool:
        return self.outcome == Outcome.DRAW

    @property
    def is_loss(self) -> bool:
        return self.outcome == Outcome.LOSS

    @classmethod
    def from_dict(
        cls,
        game: dict[str, Any],
        user_color: str,
    ) -> GameRecord:
        """Parse raw game dictionary into a structured GameRecord."""
        res = (game.get("result") or "*").strip()
        outcome = outcome_for(res, user_color)
        term_type, draw_type = classify_termination(game, is_draw=(outcome == Outcome.DRAW))

        # Speed category detection
        is_960 = bool(game.get("chess960", 0))
        if is_960:
            speed = "Chess960"
        else:
            speed = (game.get("speed_category") or "").strip()
            if not speed:
                speed = PGNParser.detect_speed_category(game.get("time_control"), game.get("event"))
            if not speed:
                speed = "Other"

        # Opponent extraction
        opp_name_key = "black" if user_color == "white" else "white"
        opp_elo_key = "black_elo" if user_color == "white" else "white_elo"
        opp_name = game.get(opp_name_key, "Unknown")
        opp_rating_str = str(game.get(opp_elo_key) or "")
        try:
            opp_elo = int(opp_rating_str) if opp_rating_str else 0
        except (ValueError, TypeError):
            opp_elo = 0

        # Opening extraction
        op_name = game.get("opening") or ""
        eco_code = game.get("eco") or ""
        if not op_name or not eco_code:
            pgn = game.get("pgn", "")
            if not op_name and 'Opening "' in pgn:
                match_op = re.search(r'\[Opening "([^"]+)"\]', pgn)
                if match_op:
                    op_name = match_op.group(1)
            if not eco_code and 'ECO "' in pgn:
                match_eco = re.search(r'\[ECO "([^"]+)"\]', pgn)
                if match_eco:
                    eco_code = match_eco.group(1)

        # Accuracy & Quality Counts
        game_acc = 0.0
        quality_counts: dict[str, int] = {k: 0 for k in QUALITY_NAMES}
        blunders_count = 0
        tactics_data = None

        if game.get("summary_json"):
            try:
                summary = json.loads(game["summary_json"])
                s_data = summary.get(user_color, {})
                acc = float(s_data.get("accuracy", 0.0))
                if acc > 0:
                    game_acc = acc
                for qk in QUALITY_NAMES:
                    quality_counts[qk] = s_data.get(qk, 0)
                blunders_count = s_data.get("Blunder", 0)
                tactics_data = s_data.get("tactics")
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                logger.debug("Failed parsing summary_json for game %s: %s", game.get("id"), exc)

        # Tactical analysis: recompute if missing or older format
        if game.get("moves_json") and (
            not tactics_data
            or "phase_move_counts" not in tactics_data
            or "clock_metrics" not in tactics_data
            or "hung_pieces_details" not in tactics_data
        ):
            try:
                moves_data = json.loads(game["moves_json"])
                tactics_data = analyze_game_tactics(
                    moves_data, user_color, res, speed_category=speed
                )
            except Exception as exc:
                logger.warning("Failed to recompute tactics for game %s: %s", game.get("id"), exc)

        if not game.get("summary_json") and tactics_data:
            blunders_details = tactics_data.get("blunders_details", [])
            blunders_count = len(blunders_details)
            quality_counts["Blunder"] = blunders_count

        game_meta = {
            "game_id": game.get("id"),
            "opponent": opp_name,
            "opponent_elo": opp_rating_str,
            "date": game.get("date", ""),
            "result": res,
            "user_color": user_color,
            "speed_category": speed,
            "opening": op_name or game.get("opening", ""),
        }

        return cls(
            game_id=game.get("id"),
            raw_game=game,
            user_color=user_color,
            result=res,
            outcome=outcome,
            term_type=term_type,
            draw_type=draw_type,
            speed=speed,
            opp_name=opp_name,
            opp_rating_str=opp_rating_str,
            opp_elo=opp_elo,
            opening=op_name,
            eco=eco_code,
            game_acc=game_acc,
            quality_counts=quality_counts,
            blunders_count=blunders_count,
            tactics_data=tactics_data,
            game_meta=game_meta,
        )

"""
Game filtering and user color resolution module.
Filters games by user color, speed/time format, data source, and date range.
"""

from __future__ import annotations

import datetime
import time
from typing import Any

from src.backend.storage.pgn_parser import PGNParser
from src.utils.logger import logger

from .constants import VALID_DATE_FILTERS

_DATE_FILTER_SECONDS: dict[str, float] = {
    "Last 24 Hours": 86400.0,
    "Last 7 Days": 7 * 86400.0,
    "Last 30 Days": 30 * 86400.0,
    "Last 90 Days": 90 * 86400.0,
}


def extract_game_timestamp(game: dict[str, Any]) -> float | None:
    """Extract a Unix epoch timestamp from a game record."""
    ts = game.get("timestamp")
    if ts is not None:
        try:
            return float(ts)
        except (ValueError, TypeError):
            pass

    date_str = str(game.get("date") or "").strip()
    if date_str:
        try:
            d_clean = date_str.replace(".", "-")
            if len(d_clean) >= 10:
                dt = datetime.datetime.strptime(d_clean[:10], "%Y-%m-%d").replace(
                    tzinfo=datetime.timezone.utc
                )
                return dt.timestamp()
            elif len(d_clean) >= 4 and d_clean[:4].isdigit():
                dt = datetime.datetime(int(d_clean[:4]), 1, 1, tzinfo=datetime.timezone.utc)
                return dt.timestamp()
        except (ValueError, TypeError) as exc:
            logger.debug("Failed parsing date string '%s': %s", date_str, exc)

    return None


def _within_date(date_filter: str, ts: float | None, now: float | None = None) -> bool:
    """Check if the timestamp falls within the specified date filter."""
    if date_filter == "All Time" or not date_filter:
        return True

    if date_filter not in VALID_DATE_FILTERS:
        logger.warning("Unrecognized date_filter '%s'; rejecting game", date_filter)
        return False

    if ts is None:
        return False

    current_time = now if now is not None else time.time()

    if date_filter in _DATE_FILTER_SECONDS:
        max_age = _DATE_FILTER_SECONDS[date_filter]
        return (current_time - ts) <= max_age

    if date_filter == "This Year":
        try:
            game_year = time.localtime(ts).tm_year
            current_year = time.localtime(current_time).tm_year
            return game_year == current_year
        except (ValueError, OverflowError):
            return False

    return False


def get_user_color(
    game: dict[str, Any],
    usernames: list[str] | set[str] | frozenset[str],
) -> str | None:
    """
    Determine whether the tracked user was playing White or Black.
    Returns 'white', 'black', or None if neither side matches.
    """
    usernames_lower = {u.lower() for u in usernames}
    white = (game.get("white") or "").lower()
    if white in usernames_lower:
        return "white"
    black = (game.get("black") or "").lower()
    if black in usernames_lower:
        return "black"
    return None


def matches_filters(
    game: dict[str, Any],
    user_color: str | None,
    color_filter: str = "All Colors",
    format_filter: str = "All Formats",
    source_filter: str = "All Sources",
    date_filter: str = "All Time",
    now: float | None = None,
) -> bool:
    """Determine if a game matches user-selected criteria."""
    # 0. User identity validation
    if user_color is None or user_color not in ("white", "black"):
        return False

    # 1. Color filter
    if color_filter == "White" and user_color != "white":
        return False
    if color_filter == "Black" and user_color != "black":
        return False

    # 2. Format / Time Control filter
    is_960 = bool(game.get("chess960", 0))
    if format_filter == "Freestyle (Chess960)":
        if not is_960:
            return False
    else:
        if is_960 and format_filter != "All Formats":
            return False

        if format_filter != "All Formats":
            speed = (game.get("speed_category") or "").strip()
            if not speed:
                speed = PGNParser.detect_speed_category(game.get("time_control"), game.get("event"))
            if speed.lower() != format_filter.lower():
                return False

    # 3. Source filter
    if source_filter != "All Sources":
        src = (game.get("source") or "file").lower()
        target = source_filter.lower()
        if "chess" in target and "lichess" not in target:
            if "lichess" in src or not ("chesscom" in src or "chess.com" in src or src == "chess"):
                return False
        elif "lichess" in target:
            if "lichess" not in src:
                return False
        elif "file" in target and src not in ("file", "pgn", "local", "text"):
            return False

    # 4. Date Range filter
    if date_filter != "All Time":
        ts = extract_game_timestamp(game)
        if not _within_date(date_filter, ts, now=now):
            return False

    return True


def filter_games(
    games: list[dict[str, Any]],
    usernames: list[str] | set[str],
    color_filter: str = "All Colors",
    format_filter: str = "All Formats",
    source_filter: str = "All Sources",
    date_filter: str = "All Time",
) -> list[tuple[dict[str, Any], str]]:
    """Filter raw games by user-specified criteria, returning tuples of (game, user_color)."""
    usernames_lower = {u.lower() for u in usernames}
    now = time.time()
    matched: list[tuple[dict[str, Any], str]] = []

    for g in games:
        user_color = get_user_color(g, usernames_lower)
        if user_color is None:
            continue
        if matches_filters(
            g,
            user_color,
            color_filter=color_filter,
            format_filter=format_filter,
            source_filter=source_filter,
            date_filter=date_filter,
            now=now,
        ):
            matched.append((g, user_color))

    return matched

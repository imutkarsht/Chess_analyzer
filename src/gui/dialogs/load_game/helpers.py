"""
Helper utilities for the Load Game dialog panels.
"""

import datetime
import os

from ....utils.path_utils import get_resource_path


def icon_path(filename: str) -> str:
    return get_resource_path(os.path.join("assets", "icons", filename))


def format_display_date(value: str | None) -> str:
    """Render API/PGN dates in the same human format as the query summary."""
    if not value or value in ("?", "????.??.??", "????-??-??"):
        return "Unknown date"
    text = str(value).replace(".", "-")
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%d").strftime("%b %d, %Y")
    except ValueError:
        return str(value)


def game_row(
    *,
    date: str | None,
    time_class: str | None,
    result: str | None,
    moves: int | str | None,
    white: str | None,
    black: str | None,
    white_elo: str | int | None,
    black_elo: str | int | None,
    opening: str | None = None,
) -> tuple[str, str]:
    """One consistent display row for API and PGN results."""
    line1 = (
        f"{format_display_date(date)}  ·  "
        f"{(time_class or 'standard').upper()}  ·  "
        f"{result or '?'}  ·  {moves if moves is not None else '?'} moves"
    )
    line2 = (
        f"{white or '?'} ({white_elo or '?'})  vs  "
        f"{black or '?'} ({black_elo or '?'})"
    )
    if opening:
        line2 += f"  ·  {opening}"
    return line1, line2


def classify_time_control(tc: str) -> str:
    """Return Bullet/Blitz/Rapid/Classical/Correspondence from a TimeControl string."""
    if not tc or tc in ("-", "?", ""):
        return "Unknown"
    try:
        # Handle formats like "600", "600+5", "40/7200:1800+30"
        base = 0
        for period in tc.split(":"):
            base_part = period.split("+")[0]
            sec_part = base_part.split("/")[-1]
            try:
                base += int(sec_part)
            except ValueError:
                pass

        if base == 0:
            return tc

        if base < 180:
            return "Bullet"
        if base < 600:
            return "Blitz"
        if base < 1800:
            return "Rapid"
        if base >= 86400:
            return "Daily"
        return "Classical"
    except Exception:
        return tc

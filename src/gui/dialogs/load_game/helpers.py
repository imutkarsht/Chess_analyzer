"""
Helper utilities for the Load Game dialog panels.
"""

import datetime
import os

from ....utils.path_utils import get_resource_path
from ....utils.time_control import classify_time_control

__all__ = [
    "classify_time_control",
    "format_display_date",
    "game_row",
    "icon_path",
]


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
    parts = [
        format_display_date(date),
        (time_class or "standard").upper(),
        result or "?",
    ]
    if moves is not None:
        parts.append(f"{moves} moves")
    line1 = "  ·  ".join(parts)
    line2 = (
        f"{white or '?'} ({white_elo or '?'})  vs  "
        f"{black or '?'} ({black_elo or '?'})"
    )
    if opening:
        line2 += f"  ·  {opening}"
    return line1, line2




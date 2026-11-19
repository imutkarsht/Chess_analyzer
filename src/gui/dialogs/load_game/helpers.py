"""
Helper utilities for the Load Game dialog panels.
"""

from src.utils.date_utils import format_display_date
from src.utils.time_control import classify_time_control

__all__ = [
    "classify_time_control",
    "game_row",
]


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




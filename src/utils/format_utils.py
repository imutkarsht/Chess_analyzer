# SPDX-License-Identifier: GPL-3.0-only
"""Pure formatting helpers shared by the backend and GUI layers."""

from __future__ import annotations

import math


def format_clock(
    seconds: float | None,
    *,
    precision: int = 0,
    pad_minutes: bool = False,
    compact_under: float | None = None,
    round_seconds: bool = False,
    none_text: str = "-",
) -> str:
    """Format a duration as a chess clock.

    ``precision=0`` truncates fractional seconds, while ``precision=1`` keeps
    one decimal place. ``pad_minutes`` zero-pads minutes when hours are absent.
    ``compact_under`` renders sub-minute values as a single decimal (for live
    clocks that switch to tenths below 20 seconds). ``round_seconds`` rounds to
    the nearest whole second before formatting (elapsed/ETA timers).
    """
    if seconds is None:
        return none_text

    if round_seconds:
        seconds = max(0, round(float(seconds)))
    else:
        seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    remainder = seconds - hours * 3600 - minutes * 60

    if (
        compact_under is not None
        and hours == 0
        and minutes == 0
        and remainder < compact_under
    ):
        return f"{remainder:.1f}"

    if precision > 0:
        seconds_text = f"{remainder:0{3 + precision}.{precision}f}"
    else:
        seconds_text = f"{int(remainder):02d}"

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds_text}"
    if pad_minutes:
        return f"{minutes:02d}:{seconds_text}"
    return f"{minutes}:{seconds_text}"


def format_eval(
    cp: int | None,
    mate: int | None,
    *,
    mate_style: str = "M",
    decimals: int = 2,
    signed_cp: bool = True,
    none_text: str | None = "?",
) -> str | None:
    """Format a Stockfish evaluation in the style used by its caller.

    ``mate_style="M"`` renders ``M4`` / ``-M4``; ``"signed"`` renders ``+M4`` /
    ``-M4``; ``"pgn"`` renders ``#4`` / ``#-4``. ``signed_cp=False`` omits the
    leading ``+`` for positive centipawn scores.
    """
    if mate is not None:
        try:
            mate_value = int(mate)
        except (TypeError, ValueError):
            mate_value = 0
        if mate_style == "pgn":
            return f"#{mate_value}"
        if mate_value > 0:
            prefix = "+" if mate_style == "signed" else ""
            return f"{prefix}M{mate_value}"
        return f"-M{abs(mate_value)}"

    if cp is None:
        return none_text

    try:
        cp_value = int(cp)
    except (TypeError, ValueError):
        return none_text

    sign = "+" if signed_cp else ""
    return f"{cp_value / 100:{sign}.{decimals}f}"


def format_pgn_clock(seconds: float | None) -> str | None:
    """Format a clock value for a PGN ``[%clk]`` comment."""
    if seconds is None or seconds < 0:
        return None

    tenths = round(seconds * 10)
    hours, remainder = divmod(tenths, 36_000)
    minutes, remainder = divmod(remainder, 600)
    whole_seconds, fractional = divmod(remainder, 10)
    seconds_text = (
        f"{whole_seconds:02d}.{fractional}" if fractional else f"{whole_seconds:02d}"
    )
    return f"{hours}:{minutes:02d}:{seconds_text}"


def format_count(
    count: int | float | None,
    *,
    none_text: str = "—",
    thousands: bool = True,
) -> str:
    """Format a non-negative count, with thousands separators by default."""
    if count is None or isinstance(count, bool):
        return none_text
    try:
        value = max(0, int(float(count)))
    except (TypeError, ValueError, OverflowError):
        return none_text
    return f"{value:,}" if thousands else str(value)


def format_bytes(size: int | float | None, *, none_text: str = "—") -> str:
    """Format a byte size with one decimal, e.g. ``42.6 MB``."""
    if size is None or isinstance(size, bool):
        return none_text
    try:
        value = float(max(0, size))
    except (TypeError, ValueError):
        return none_text

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def format_percent(
    value: float | None,
    *,
    decimals: int = 1,
    none_text: str = "--",
) -> str:
    """Format a percentage, returning ``none_text`` for missing/non-finite data."""
    if value is None or isinstance(value, bool):
        return none_text
    try:
        number = float(value)
    except (TypeError, ValueError):
        return none_text
    if not math.isfinite(number):
        return none_text
    return f"{number:.{decimals}f}%"


def format_duration(seconds: float) -> str:
    """Format a think time as a compact duration, e.g. ``1.2h`` or ``3.4m``."""
    if seconds >= 3600:
        return f"{seconds / 3600:.1f}h"
    if seconds >= 60:
        return f"{seconds / 60:.1f}m"
    if seconds >= 10:
        return f"{seconds:.0f}s"
    return f"{seconds:.1f}s"

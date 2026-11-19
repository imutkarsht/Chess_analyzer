# SPDX-License-Identifier: GPL-3.0-only
"""Pure date and cache-age formatting helpers."""

from __future__ import annotations

import datetime
import time


def format_display_date(value: str | None) -> str:
    """Render API/PGN dates consistently for the UI."""
    if not value or value in ("?", "????.??.??", "????-??-??"):
        return "Unknown date"
    text = str(value).replace(".", "-")
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%d").strftime("%b %d, %Y")
    except ValueError:
        return str(value)


def format_cache_age(fetched_at: float, now: float | None = None) -> str:
    """Human-readable age for a cached profile snapshot."""
    if not fetched_at:
        return ""
    current = time.time() if now is None else now
    seconds = max(0, current - fetched_at)
    if seconds < 90:
        return "just now"

    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} min ago"

    hours = int(seconds // 3600)
    if hours < 24:
        return f"{hours} hr ago" if hours == 1 else f"{hours} hrs ago"

    days = int(seconds // 86400)
    if days < 30:
        return f"{days} day ago" if days == 1 else f"{days} days ago"
    return time.strftime("%d %b %Y", time.localtime(fetched_at))

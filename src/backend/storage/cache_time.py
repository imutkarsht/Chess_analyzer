# SPDX-License-Identifier: GPL-3.0-only
"""Shared cache timestamp and TTL helpers."""

from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any

_CACHE_TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")


def now_iso() -> str:
    """Current local time in the database's standard cache format."""
    return time.strftime("%Y-%m-%d %H:%M:%S")


def parse_cached_at(value: Any) -> float:
    """Parse a numeric epoch or an ISO-like cache timestamp into an epoch."""
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    for fmt in _CACHE_TIME_FORMATS:
        try:
            return time.mktime(time.strptime(str(value), fmt))
        except (TypeError, ValueError, OverflowError):
            pass
    return 0.0


def resolve_ttl_seconds(hours: Any, default_seconds: float) -> float | None:
    """Resolve a configurable hour-based TTL, preserving explicit ``None``."""
    if hours is None:
        return None
    try:
        return max(1, int(hours)) * 3600.0
    except (TypeError, ValueError):
        return default_seconds


def is_fresh(cached_at: Any, ttl_seconds: float, *, now: float | None = None) -> bool:
    """True when ``cached_at`` is within ``ttl_seconds`` of now."""
    current = time.time() if now is None else now
    return current - parse_cached_at(cached_at) <= ttl_seconds


def cache_is_fresh(
    entries: Iterable[Any],
    ttl_seconds: float,
    *,
    now: float | None = None,
) -> bool:
    """True when at least one cached entry is still fresh."""
    return any(
        is_fresh(cached_at, ttl_seconds, now=now)
        for entry in entries
        if (cached_at := getattr(entry, "cached_at", None))
    )

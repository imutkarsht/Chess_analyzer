"""Human-readable time-control parsing and classification shared by backend and GUI."""

from __future__ import annotations

import re
from dataclasses import dataclass

_PERIOD_PATTERN = re.compile(r"(?:(\d+)/)?(\d+)(?:\+(\d+))?")


@dataclass(frozen=True)
class TimeControlPhase:
    """One PGN time-control period: base seconds, optional moves, increment."""

    base_seconds: int
    moves: int | None = None
    increment: int = 0


def parse_time_control(tc: str | None) -> list[TimeControlPhase] | None:
    """Parse ``600+5``, ``40/7200:1800`` or ``1/86400`` into periods.

    Returns ``None`` for placeholders and unrecognised strings so callers can
    fall back to showing the raw value.
    """
    if not tc:
        return None

    text = tc.strip()
    if not text or text in {"-", "?", "*"}:
        return None

    phases: list[TimeControlPhase] = []
    for period in text.split(":"):
        match = _PERIOD_PATTERN.fullmatch(period)
        if match is None:
            return None
        moves, seconds, increment = match.groups()
        phases.append(
            TimeControlPhase(
                base_seconds=int(seconds),
                moves=int(moves) if moves is not None else None,
                increment=int(increment) if increment is not None else 0,
            )
        )
    return phases


def format_time_control(tc: str | None) -> str:
    """Render a time control in standard chess notation (``3+2``, ``1d``).

    One period is shown exactly like the History list; multi-period controls
    are joined with ``then``. Unrecognised values fall back to the raw PGN
    string so nothing is silently dropped.
    """
    if not tc or tc in ("-", "?"):
        return ""

    phases = parse_time_control(tc)
    if not phases:
        return tc

    with_unit = len(phases) > 1
    parts: list[str] = []
    for phase in phases:
        part = _format_period(phase, with_unit=with_unit)
        if part is None:
            return tc
        parts.append(part)
    return " then ".join(parts)


def _format_period(phase: TimeControlPhase, with_unit: bool = False) -> str | None:
    """Compact one period, or ``None`` when its PGN form has no shorthand."""
    seconds = phase.base_seconds
    if phase.moves is None:
        if seconds < 60:
            base = f"{seconds}s"
        elif seconds % 60 == 0:
            base = str(seconds // 60)
            if with_unit:
                base = f"{base}m"
        else:
            base = f"{seconds / 60:.1f}".rstrip("0").rstrip(".")
            if with_unit:
                base = f"{base}m"
        # Chess notation always pairs the base time with an increment, so a
        # missing increment is shown explicitly as +0 rather than "10".
        return f"{base}+{phase.increment}"

    # Correspondence periods (1/86400 = one move per day) read better as 1d.
    if phase.moves == 1:
        if seconds >= 86400:
            return f"{seconds // 86400}d"
        if seconds >= 3600:
            return f"{seconds // 3600}h"
        return None

    if phase.moves > 1 and phase.increment == 0:
        return f"{phase.moves}m/{seconds // 60}m"
    return None


def classify_time_control(
    tc: str | None,
    event: str | None = None,
    *,
    default: str = "Unknown",
    empty_default: str | None = None,
) -> str:
    """Classify a time control into UltraBullet/Bullet/Blitz/Rapid/Classical/Daily.

    ``tc`` may be PGN notation (``600+5``, ``40/7200:1800``, ``1/86400``) or a
    named speed such as ``blitz``. When the numeric form is absent, the named
    speed is checked first, then ``event``. ``empty_default`` lets UI callers
    keep their historical placeholder label without changing the shared logic.
    """
    text = (tc or "").strip()
    placeholder = not text or text in {"-", "?", "*"}

    if not placeholder:
        phases = parse_time_control(text)
        if phases is not None:
            if any(
                phase.moves == 1 and phase.base_seconds >= 3600
                for phase in phases
            ):
                return "Daily"

            total = sum(
                phase.base_seconds + 40 * phase.increment for phase in phases
            )
            if total >= 86400:
                return "Daily"
            if total < 30:
                return "UltraBullet"
            if total < 180:
                return "Bullet"
            if total < 600:
                return "Blitz"
            if total < 1800:
                return "Rapid"
            return "Classical"

    haystack = "".join(f"{text} {event or ''}".casefold().split())
    if "ultrabullet" in haystack:
        return "UltraBullet"
    if "bullet" in haystack:
        return "Bullet"
    if "blitz" in haystack:
        return "Blitz"
    if "rapid" in haystack:
        return "Rapid"
    if "daily" in haystack or "correspondence" in haystack:
        return "Daily"
    if "classical" in haystack:
        return "Classical"

    if placeholder and empty_default is not None:
        return empty_default
    return default

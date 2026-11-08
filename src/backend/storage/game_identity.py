"""Normalized identity keys for matching imported games to history rows."""

from __future__ import annotations


def normalize_date(value: str | None) -> str:
    """PGN dates use 2024.05.06; API dates use 2024-05-06."""
    return (value or "").strip().replace("-", ".").replace("/", ".")


def game_identity_key(
    date: str | None,
    white: str | None,
    black: str | None,
    result: str | None,
) -> tuple[str, str, str, str]:
    """Return the cheap natural key used for 'already in history' badges."""
    return (
        normalize_date(date),
        (white or "").strip().casefold(),
        (black or "").strip().casefold(),
        (result or "").strip(),
    )

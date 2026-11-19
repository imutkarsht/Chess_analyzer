# SPDX-License-Identifier: GPL-3.0-only
"""Pure text helpers shared across backend and GUI layers."""

from __future__ import annotations

import re


def is_error_message(text: str | None) -> bool:
    """True when a worker returned a backend error string."""
    return bool(text) and text.lstrip().startswith("Error")


def initials_for(name: str | None) -> str:
    """Two-letter avatar fallback that tolerates underscores and dots."""
    parts = [part for part in re.split(r"[\s_.\-]+", (name or "").strip()) if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def country_flag(code: str | None) -> str:
    """Turn an ISO country code into a flag emoji without shipping assets."""
    if not code or len(code) != 2 or not code.isalpha():
        return ""
    return "".join(
        chr(0x1F1E6 + ord(char.upper()) - ord("A")) for char in code
    )

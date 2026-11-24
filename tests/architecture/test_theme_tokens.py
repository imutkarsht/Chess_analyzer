# SPDX-License-Identifier: GPL-3.0-only
"""Guard against hardcoded colours outside the theme layer."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUI = ROOT / "src" / "gui"
ALLOWED = {
    "src/gui/theme/palette.py",
    "src/gui/theme/system.py",
    "src/gui/theme/bundles/oled.py",
}
HEX = re.compile(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b")
RGBA = re.compile(r"rgba?\(\s*\d")


def _offenders(pattern: re.Pattern[str]) -> list[str]:
    found: list[str] = []
    for path in GUI.rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        if relative in ALLOWED or relative.startswith("src/gui/styles/"):
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                found.append(f"{relative}:{lineno}: {line.strip()}")
    return found


def test_no_hardcoded_hex_colours_outside_theme_layer():
    assert _offenders(HEX) == []


def test_no_hardcoded_rgba_colours_outside_theme_layer():
    assert _offenders(RGBA) == []

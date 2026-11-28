# SPDX-License-Identifier: GPL-3.0-only
"""Guardrails for the central icon layer."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUI = ROOT / "src" / "gui"
ICON_PACKAGE = GUI / "icons"
RAW_FONT_ICON = re.compile(r"fa[0-9]*[sbrlbd]\.[a-z0-9-]+")

# Content artwork and app identity assets may still construct QIcons directly.
RAW_QICON_ALLOWLIST = {
    "src/gui/analysis/moves/cell.py",
    "src/gui/analysis/moves/view.py",
    "src/gui/board/promotion_dialog.py",
    "src/gui/main_window/window.py",
    "src/gui/resources.py",
    "src/gui/views/settings/board_pieces_settings.py",
}

# Brand glyphs and a few Font Awesome 6-only legend glyphs remain explicit
# until they have pack-independent equivalents.
RAW_FONT_ALLOWLIST = {
    "src/gui/components/layout/welcome_panel.py",
    "src/gui/views/metrics/ending_distribution_card.py",
    "src/gui/views/settings/links_settings.py",
}

SETICON_ALLOWLIST = {
    "src/gui/analysis/moves/cell.py",
    "src/gui/analysis/moves/view.py",
    "src/gui/main_window/window.py",
    "src/gui/views/history_view.py",
    "src/gui/views/settings/board_pieces_settings.py",
}


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_only_the_icon_layer_imports_qtawesome() -> None:
    offenders: list[str] = []
    for path in GUI.rglob("*.py"):
        if ICON_PACKAGE in path.parents:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name == "qtawesome" for alias in node.names):
                    offenders.append(_relative(path))
            elif isinstance(node, ast.ImportFrom) and node.module == "qtawesome":
                offenders.append(_relative(path))

    assert offenders == [], (
        "Use src.gui.icons instead of importing qtawesome directly:\n"
        + "\n".join(offenders)
    )


def test_raw_font_icon_names_stay_in_the_icon_layer_or_brand_allowlist() -> None:
    offenders: list[str] = []
    for path in GUI.rglob("*.py"):
        relative = _relative(path)
        if ICON_PACKAGE in path.parents or relative in RAW_FONT_ALLOWLIST:
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if RAW_FONT_ICON.search(line):
                offenders.append(f"{relative}:{lineno}: {line.strip()}")

    assert offenders == [], (
        "Use pack-independent icon keys instead of raw font names:\n"
        + "\n".join(offenders)
    )


def test_seticon_calls_stay_in_the_icon_layer_or_content_allowlist() -> None:
    offenders: list[str] = []
    for path in GUI.rglob("*.py"):
        relative = _relative(path)
        if (
            ICON_PACKAGE in path.parents
            or relative.startswith("src/gui/components/")
            or relative in SETICON_ALLOWLIST
        ):
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if "setIcon(" in line:
                offenders.append(f"{relative}:{lineno}: {line.strip()}")

    assert offenders == []


def test_qicon_construction_stays_in_the_icon_layer_or_content_allowlist() -> None:
    offenders: list[str] = []
    for path in GUI.rglob("*.py"):
        relative = _relative(path)
        if (
            ICON_PACKAGE in path.parents
            or relative.startswith("src/gui/components/")
            or relative in RAW_QICON_ALLOWLIST
        ):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (
                func.id
                if isinstance(func, ast.Name)
                else func.attr
                if isinstance(func, ast.Attribute)
                else ""
            )
            if name == "QIcon":
                offenders.append(f"{relative}:{node.lineno}")

    assert offenders == []

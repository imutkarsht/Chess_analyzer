# SPDX-License-Identifier: GPL-3.0-only
"""Guardrails for the central icon layer."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUI = ROOT / "src" / "gui"
ICON_LAYER = GUI / "utils" / "icons.py"

# Content artwork and app identity assets may still construct QIcons directly.
RAW_QICON_ALLOWLIST = {
    "src/gui/analysis/moves/cell.py",
    "src/gui/analysis/moves/view.py",
    "src/gui/board/promotion_dialog.py",
    "src/gui/dialogs/splash_screen.py",
    "src/gui/dialogs/wizard/wizard_pages.py",
    "src/gui/main_window/window.py",
    "src/gui/resources.py",
    "src/gui/views/settings/board_pieces_settings.py",
    "src/gui/views/settings/links_settings.py",
}


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_only_the_icon_layer_imports_qtawesome() -> None:
    offenders: list[str] = []
    for path in GUI.rglob("*.py"):
        if path == ICON_LAYER:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name == "qtawesome" for alias in node.names):
                    offenders.append(_relative(path))
            elif isinstance(node, ast.ImportFrom) and node.module == "qtawesome":
                offenders.append(_relative(path))

    assert offenders == [], (
        "Use src.gui.utils.icons instead of importing qtawesome directly:\n"
        + "\n".join(offenders)
    )


def test_qicon_construction_stays_in_the_icon_layer_or_content_allowlist() -> None:
    offenders: list[str] = []
    for path in GUI.rglob("*.py"):
        relative = _relative(path)
        if (
            path == ICON_LAYER
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

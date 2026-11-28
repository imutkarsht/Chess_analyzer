# SPDX-License-Identifier: GPL-3.0-only
"""Guardrails for the central icon layer."""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.hygiene_rules import (
    RAW_FONT_ALLOWLIST,
    RAW_FONT_ICON,
    RAW_QICON_ALLOWLIST,
    SETICON_ALLOWLIST,
)

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
ICON_PACKAGE = SRC / "gui" / "icons"


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_only_the_icon_layer_imports_qtawesome() -> None:
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
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
    for path in SRC.rglob("*.py"):
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
    for path in SRC.rglob("*.py"):
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
    for path in SRC.rglob("*.py"):
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

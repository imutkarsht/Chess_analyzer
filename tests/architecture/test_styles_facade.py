# SPDX-License-Identifier: GPL-3.0-only
"""Guard the public Styles facade against direct mixin imports."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_styles_is_a_package_with_a_single_public_facade():
    assert (ROOT / "src" / "gui" / "styles" / "__init__.py").is_file()
    assert not (ROOT / "src" / "gui" / "styles.py").exists()


def test_gui_code_imports_styles_through_the_facade():
    styles_root = ROOT / "src" / "gui" / "styles"
    offenders: list[str] = []
    for path in (ROOT / "src" / "gui").rglob("*.py"):
        if path.is_relative_to(styles_root):
            continue
        text = path.read_text(encoding="utf-8")
        if "src.gui.styles._" in text:
            offenders.append(path.relative_to(ROOT).as_posix())

    assert offenders == []

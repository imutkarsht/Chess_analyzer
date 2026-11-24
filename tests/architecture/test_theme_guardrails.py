# SPDX-License-Identifier: GPL-3.0-only
"""Guardrails for the centralized theme architecture.

These tests fail when a change reintroduces the two patterns that caused the
original theme-refactor regressions:

1. Declaration-only stylesheets (``setStyleSheet("background: ...")``) act as
   a wildcard rule for the widget *and every descendant*, overriding the
   application stylesheet for child buttons/inputs.
2. A universal ``QWidget { background-color: ... }`` rule paints a rectangle
   behind every child widget, forcing every container to fight it.

They also pin the ownership contract: the central template must not target
component widgets through broad descendant ``QWidget`` transparency rules.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUI = ROOT / "src" / "gui"
TEMPLATE = GUI / "theme" / "theme_template.qss"

# Declaration-only stylesheets: a property name at the start of the string with
# no selector block. Matches setStyleSheet("background: ..."), setStyleSheet(
# f"color: ..."), and multi-line f-strings that begin with a property.
_DECLARATION_ONLY = re.compile(
    r"""setStyleSheet\(\s*(?:f)?"{2,3}\s*\n?\s*(?:background|border|color|padding|font|margin)\b""",
    re.MULTILINE,
)

# Broad descendant transparency inside the template: "#SomeId QWidget { ... }"
# or a plain "QWidget QWidget { ... }".
_BROAD_DESCENDANT = re.compile(
    r"^[^\n{}]*#[A-Za-z_][\w]*\s+QWidget\s*\{", re.MULTILINE
)
_UNIVERSAL_BACKGROUND = re.compile(
    r"^QWidget\s*\{\s*\n\s*background-color:", re.MULTILINE
)


def test_no_declaration_only_stylesheets() -> None:
    offenders: list[str] = []
    for path in GUI.rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        for match in _DECLARATION_ONLY.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            offenders.append(f"{relative}:{line}")
    assert offenders == [], (
        "Declaration-only setStyleSheet calls are wildcard rules for all "
        "descendants. Use Styles.apply_transparent(widget) or an object-name "
        "rule in theme_template.qss instead."
    )


def test_no_universal_widget_background() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    assert _UNIVERSAL_BACKGROUND.search(text) is None, (
        "Do not paint a background on every QWidget; only window/dialog/page "
        "containers own backgrounds (QMainWindow, QDialog, appBackground)."
    )


def test_no_broad_descendant_widget_transparency() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    offenders = _BROAD_DESCENDANT.findall(text)
    assert offenders == [], (
        "Do not style descendant QWidgets through an ancestor rule "
        "(e.g. '#MetricCard QWidget { background: transparent }'); it also "
        "strips backgrounds from buttons and inputs."
    )

# SPDX-License-Identifier: GPL-3.0-only
"""Shared icon, rich-text/link, and badge primitives."""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from src.gui.components import (
    BadgeVariant,
    IconLabel,
    LinkLabel,
    RichTextLabel,
    StatusBadge,
    TextRole,
    TextTone,
)
from src.gui.styles import Styles


def test_icon_label_uses_a_pixmap_and_falls_back_to_glyph(qtbot):
    pixmap = QPixmap(8, 8)
    pixmap.fill(Qt.GlobalColor.white)
    label = IconLabel(pixmap, size=16)
    qtbot.addWidget(label)
    assert not label.pixmap().isNull()

    missing = IconLabel("definitely.not.an.icon", size=16, fallback="?")
    qtbot.addWidget(missing)
    assert missing.text() == "?"


def test_rich_text_label_keeps_html_format(qtbot):
    label = RichTextLabel("<b>White</b>", role=TextRole.BODY)
    qtbot.addWidget(label)

    assert label.textFormat() is Qt.TextFormat.RichText
    assert label.text() == "<b>White</b>"
    assert label.styleSheet() == ""


def test_link_label_builds_an_external_link(qtbot):
    link = LinkLabel("https://example.com/game", "View game")
    qtbot.addWidget(link)

    assert link.openExternalLinks() is True
    assert 'href="https://example.com/game"' in link.text()
    assert "View game" in link.text()
    assert Styles.COLOR_ACCENT.lower() in link.text().lower()


def test_link_label_uses_the_shared_tone_resolver(qtbot, monkeypatch):
    monkeypatch.setattr(
        Styles,
        "get_tone_color",
        classmethod(lambda cls, tone: "#123456"),
    )
    link = LinkLabel("https://example.com", "Example")
    qtbot.addWidget(link)

    assert "#123456" in link.text().lower()


def test_status_badge_variants_and_mono(qtbot):
    soft = StatusBadge("Win", TextTone.RESULT_WIN)
    outline = StatusBadge("Win", TextTone.RESULT_WIN, variant=BadgeVariant.OUTLINE)
    solid = StatusBadge("Win", TextTone.RESULT_WIN, variant=BadgeVariant.SOLID)
    mono = StatusBadge("1-0", TextTone.PRIMARY, mono=True)
    for badge in (soft, outline, solid, mono):
        qtbot.addWidget(badge)

    assert Styles.COLOR_SURFACE_LIGHT in soft.styleSheet()
    assert "background-color: transparent" in outline.styleSheet()
    assert Styles.COLOR_ON_ACCENT in solid.styleSheet()
    assert "monospace" in mono.styleSheet()

    outline.set_tone(TextTone.BEST)
    assert Styles.COLOR_BEST in outline.styleSheet()
    assert outline.tone == TextTone.BEST.value


def test_status_badge_rejects_unknown_tones(qapp):
    with pytest.raises(ValueError):
        StatusBadge("x", "banana")

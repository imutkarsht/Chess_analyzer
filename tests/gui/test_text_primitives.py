# SPDX-License-Identifier: GPL-3.0-only
"""Shared icon, rich-text/link, and badge primitives."""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from src.gui.components import (
    Avatar,
    BadgeVariant,
    ChipLabel,
    ClockLabel,
    ColorLabel,
    EngineScoreBadge,
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
    quiet = StatusBadge("⌘O", TextTone.MUTED, variant=BadgeVariant.QUIET)
    mono = StatusBadge("1-0", TextTone.PRIMARY, mono=True)
    for badge in (soft, outline, solid, quiet, mono):
        qtbot.addWidget(badge)

    assert Styles.COLOR_SURFACE_LIGHT in soft.styleSheet()
    assert "background-color: transparent" in outline.styleSheet()
    assert Styles.COLOR_ON_ACCENT in solid.styleSheet()
    assert Styles.COLOR_SURFACE in quiet.styleSheet()
    assert Styles.COLOR_BORDER in quiet.styleSheet()
    assert "monospace" in mono.styleSheet()

    outline.set_tone(TextTone.BEST)
    assert Styles.COLOR_BEST in outline.styleSheet()
    assert outline.tone == TextTone.BEST.value


def test_status_badge_rejects_unknown_tones(qapp):
    with pytest.raises(ValueError):
        StatusBadge("x", "banana")


def test_color_label_keeps_data_colours_out_of_the_tone_system(qtbot):
    label = ColorLabel("12", "#e67e22", role=TextRole.BODY, size=12, weight=700)
    qtbot.addWidget(label)

    assert "#e67e22" in label.styleSheet()
    label.set_color("#3498db")
    assert "#3498db" in label.styleSheet()
    assert label.property("textWeight") == "700"


def test_chip_label_owns_its_colours_and_optional_margin(qtbot):
    chip = ChipLabel(
        "♟³",
        foreground="#111111",
        background="#f0f0f0",
        font_size=26,
        padding="1px 6px",
        margin_right=4,
    )
    qtbot.addWidget(chip)

    qss = chip.styleSheet()
    assert "#111111" in qss
    assert "#f0f0f0" in qss
    assert "font-size: 26px" in qss
    assert "margin-right: 4px" in qss


def test_clock_label_applies_the_digital_clock_style(qtbot):
    clock = ClockLabel(compact=True)
    qtbot.addWidget(clock)
    clock.set_clock(
        "9.4",
        background=Styles.COLOR_BLUNDER,
        foreground="#FFFFFF",
        border=Styles.COLOR_BLUNDER,
    )

    assert clock.text() == "9.4"
    assert Styles.COLOR_BLUNDER in clock.styleSheet()
    assert "font-family" in clock.styleSheet()


def test_engine_score_badge_tracks_the_line_payload(qtbot):
    from types import SimpleNamespace

    badge = EngineScoreBadge()
    qtbot.addWidget(badge)
    line = SimpleNamespace(score_text="+1.20", cp=120, mate=None)

    badge.set_line(line)
    assert badge.text() == "+1.20"
    assert "monospace" in badge.styleSheet()

    badge.clear()
    assert badge.text() == ""


def test_icon_label_can_scale_with_its_own_geometry(qtbot):
    pixmap = QPixmap(10, 10)
    pixmap.fill(Qt.GlobalColor.white)
    label = IconLabel(pixmap, size=10, fixed_size=False, scaled=True)
    qtbot.addWidget(label)

    label.resize(40, 40)
    assert label.hasScaledContents() is True
    assert label.size().width() == 40
    assert not label.pixmap().isNull()


def test_avatar_switches_between_image_and_initials(qtbot):
    avatar = Avatar(44)
    qtbot.addWidget(avatar)
    pixmap = QPixmap(44, 44)
    pixmap.fill(Qt.GlobalColor.white)

    avatar.set_content(pixmap)
    assert avatar.text() == ""
    assert not avatar.pixmap().isNull()

    avatar.set_content(None, "AB")
    assert avatar.text() == "AB"
    assert Styles.COLOR_ACCENT in avatar.styleSheet()
    assert "border-radius: 22px" in avatar.styleSheet()

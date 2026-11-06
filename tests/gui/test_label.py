# SPDX-License-Identifier: GPL-3.0-only
"""Shared Label component: roles, tones, overrides, and theme behaviour."""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from src.gui.components import Label, TextRole, TextTone
from src.gui.styles import Styles


@pytest.fixture
def typography_sheet(qapp):
    """Apply only the generated typography block for fast font/colour checks."""
    previous = qapp.styleSheet()
    qapp.setStyleSheet(
        "QLabel { background: transparent; border: none; }\n"
        + Styles.get_typography_qss()
    )
    yield
    qapp.setStyleSheet(previous)


def _polished(qtbot, label: Label) -> Label:
    qtbot.addWidget(label)
    label.ensurePolished()
    return label


def test_label_publishes_role_and_tone_properties(qtbot, typography_sheet):
    label = _polished(qtbot, Label("Settings", role=TextRole.PAGE_TITLE))

    assert label.text() == "Settings"
    assert label.role is TextRole.PAGE_TITLE
    assert label.tone is TextTone.PRIMARY
    assert label.property("role") == "page_title"
    assert label.property("tone") == "primary"
    assert label.textFormat() is Qt.TextFormat.PlainText
    assert label.styleSheet() == ""


def test_role_applies_size_weight_case_and_spacing(qtbot, typography_sheet):
    title = _polished(qtbot, Label("Performance", role=TextRole.PAGE_TITLE))
    card_title = _polished(qtbot, Label("Accuracy Trend", role=TextRole.CARD_TITLE))
    mono = _polished(qtbot, Label("1. e4 e5", role=TextRole.MONO))

    assert title.font().pixelSize() == 24
    assert title.font().weight() == QFont.Weight.Bold
    assert card_title.font().pixelSize() == 12
    assert card_title.font().weight() == QFont.Weight.DemiBold
    assert card_title.font().capitalization() is QFont.Capitalization.AllUppercase
    assert card_title.font().letterSpacing() == 0.5
    assert any("mono" in family.lower() for family in mono.font().families())


def test_size_and_weight_overrides_beat_the_role_default(qtbot, typography_sheet):
    label = _polished(
        qtbot,
        Label("Compact", role=TextRole.BODY, size=22, weight=500),
    )

    assert label.font().pixelSize() == 22
    assert label.font().weight() == QFont.Weight.Medium


def test_set_tone_repolishes_without_a_stylesheet(qtbot, typography_sheet):
    label = _polished(qtbot, Label("Blunder", tone=TextTone.BLUNDER))

    assert label.palette().color(label.foregroundRole()).name().lower() == (
        Styles.COLOR_BLUNDER.lower()
    )

    label.set_tone(TextTone.BEST)

    assert label.tone is TextTone.BEST
    assert label.palette().color(label.foregroundRole()).name().lower() == (
        Styles.COLOR_BEST.lower()
    )
    assert label.styleSheet() == ""


def test_set_role_changes_the_font(qtbot, typography_sheet):
    label = _polished(qtbot, Label("Text", role=TextRole.BODY))
    assert label.font().pixelSize() == 13

    label.set_role(TextRole.SECTION_TITLE)

    assert label.font().pixelSize() == 18
    assert label.font().weight() == QFont.Weight.Bold


@pytest.mark.parametrize("size", [7, 19, 23, 100])
def test_label_rejects_unsupported_sizes(qapp, size):
    with pytest.raises(ValueError):
        Label("x", size=size)


@pytest.mark.parametrize("weight", [100, 300, 450, 900])
def test_label_rejects_unsupported_weights(qapp, weight):
    with pytest.raises(ValueError):
        Label("x", weight=weight)

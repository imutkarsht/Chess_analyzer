# SPDX-License-Identifier: GPL-3.0-only
"""Elided labels expose the full text only when the visible text is truncated."""

from src.gui.components import ElidedLabel, TextRole


def test_tooltip_appears_only_while_the_label_is_elided(qtbot, qapp):
    label = ElidedLabel("Najdorf Variation, English Attack", role=TextRole.BODY)
    qtbot.addWidget(label)

    label.resize(80, 24)
    label.show()
    qapp.processEvents()

    assert label.text() != label.full_text
    assert label.toolTip() == label.full_text

    label.resize(500, 24)
    qapp.processEvents()

    assert label.text() == label.full_text
    assert label.toolTip() == ""


def test_tooltip_can_be_disabled_for_elided_labels(qtbot, qapp):
    label = ElidedLabel(
        "Najdorf Variation, English Attack",
        role=TextRole.BODY,
        tooltip_when_elided=False,
    )
    qtbot.addWidget(label)
    label.resize(80, 24)
    label.show()
    qapp.processEvents()

    assert label.text() != label.full_text
    assert label.toolTip() == ""


def test_set_text_refreshes_the_elision(qtbot, qapp):
    label = ElidedLabel("Short", role=TextRole.BODY)
    qtbot.addWidget(label)
    label.resize(80, 24)
    label.show()
    qapp.processEvents()

    label.setText("A much longer label that cannot fit in eighty pixels")
    qapp.processEvents()

    assert label.text() != label.full_text
    assert label.toolTip() == label.full_text

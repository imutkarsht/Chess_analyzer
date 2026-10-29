"""Behavior tests for the shared status badge."""

import pytest

from src.gui.components.feedback.status_badge import StatusBadge


def test_text_and_tone_update_independently(qtbot):
    badge = StatusBadge("0 Brilliancies", tone="neutral")
    qtbot.addWidget(badge)

    badge.set_text("2 Brilliancies")
    badge.set_tone("brilliant")

    assert badge.text() == "2 Brilliancies"
    assert badge.tone == "brilliant"


def test_unknown_tone_is_rejected():
    with pytest.raises(ValueError):
        StatusBadge("Bad", tone="banana")

    badge = StatusBadge("Fine")
    with pytest.raises(ValueError):
        badge.set_tone("banana")

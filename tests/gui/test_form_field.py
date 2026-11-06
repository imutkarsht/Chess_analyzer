# SPDX-License-Identifier: GPL-3.0-only
"""FormField uses the shared Label roles and owns no stylesheet."""

from PyQt6.QtWidgets import QWidget

from src.gui.components import FormField, Label, TextRole, TextTone


def test_form_field_uses_shared_labels(qtbot):
    field = FormField("Username", QWidget(), description="Public handle")
    qtbot.addWidget(field)

    assert isinstance(field.label, Label)
    assert field.label.role is TextRole.CAPTION
    assert field.label.tone is TextTone.PRIMARY
    assert field.label.text() == "Username"
    assert field.styleSheet() == ""

    assert isinstance(field._description, Label)
    assert field._description.role is TextRole.MICRO
    assert field._description.tone is TextTone.SECONDARY
    assert field._description.isVisibleTo(field) is True

    assert isinstance(field._error, Label)
    assert field._error.tone is TextTone.BLUNDER


def test_form_field_error_temporarily_replaces_the_description(qtbot):
    field = FormField("Username", QWidget(), description="Public handle")
    qtbot.addWidget(field)

    field.set_error("Username is required")

    assert field._error.text() == "Username is required"
    assert field._error.isVisibleTo(field) is True
    assert field._description.isVisibleTo(field) is False

    field.clear_error()

    assert field._error.text() == ""
    assert field._error.isVisibleTo(field) is False
    assert field._description.isVisibleTo(field) is True

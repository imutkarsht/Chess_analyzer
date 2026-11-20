# SPDX-License-Identifier: GPL-3.0-only
"""Horizontal radio group bound to a single setting value."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QHBoxLayout, QRadioButton, QWidget

from src.gui.styles import Styles


class RadioChoice(QWidget):
    """Horizontal radio group bound to a single value.

    Implements the binder widget protocol (``valueChanged`` +
    ``settingValue``/``setSettingValue``) so radio groups need no special
    casing in settings binders.
    """

    valueChanged = pyqtSignal(object)

    def __init__(self, choices, *, trailing: QWidget | None = None, parent=None):
        super().__init__(parent)
        self.setStyleSheet(Styles.get_transparent_style())
        self._values: dict[QRadioButton, object] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._group = QButtonGroup(self)
        for value, label in choices:
            radio = QRadioButton(label)
            self._group.addButton(radio)
            self._values[radio] = value
            layout.addWidget(radio)

        if trailing is not None:
            layout.addWidget(trailing)

        layout.addStretch(1)
        self._group.buttonClicked.connect(self._on_button_clicked)
        self.refresh_styles()

    def _on_button_clicked(self, button: QRadioButton) -> None:
        self.valueChanged.emit(self._values[button])

    def radios(self) -> list[QRadioButton]:
        return list(self._values)

    def value(self):
        for radio, value in self._values.items():
            if radio.isChecked():
                return value
        return None

    def setValue(self, value) -> None:
        """Select the radio for ``value`` without emitting ``valueChanged``."""
        for radio, candidate in self._values.items():
            if candidate == value:
                radio.setChecked(True)
                return
        first = next(iter(self._values), None)
        if first is not None:
            first.setChecked(True)

    # -- Binder widget protocol -------------------------------------------
    def settingValue(self):
        return self.value()

    def setSettingValue(self, value) -> None:
        self.setValue(value)

    def refresh_styles(self) -> None:
        style = Styles.get_radio_group_style()
        for radio in self._values:
            radio.setStyleSheet(style)


__all__ = ["RadioChoice"]

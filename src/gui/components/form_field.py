"""Stacked label + control + helper text, shadcn-style."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.gui.styles import Styles
from src.gui.theme import ThemeManager


class FormField(QWidget):
    """A labelled form control with optional helper and error text.

    The control is supplied by the caller so inputs keep the central component
    and styling rules (QLineEdit, DatePicker, etc.) while the label/description
    rhythm stays identical across forms.
    """

    def __init__(
        self,
        label: str,
        control: QWidget,
        description: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.control = control
        self._description_text = description

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._label = QLabel(label)
        self._label.setObjectName("FormFieldLabel")
        self._label.setVisible(bool(label))
        layout.addWidget(self._label)

        layout.addWidget(control)

        self._description = QLabel(description)
        self._description.setObjectName("FormFieldDescription")
        self._description.setWordWrap(True)
        self._description.setVisible(bool(description))
        layout.addWidget(self._description)

        self._error = QLabel()
        self._error.setObjectName("FormFieldError")
        self._error.setWordWrap(True)
        self._error.hide()
        layout.addWidget(self._error)

        manager = ThemeManager.instance()
        manager.theme_changed.connect(self._on_theme_changed)
        manager.accent_changed.connect(self._on_theme_changed)
        self.refresh_styles()

    @property
    def label(self) -> QLabel:
        return self._label

    def set_description(self, text: str) -> None:
        self._description_text = text
        self._description.setText(text)
        self._description.setVisible(bool(text))

    def set_error(self, message: str) -> None:
        self._error.setText(message)
        self._error.setVisible(bool(message))
        self._description.setVisible(bool(self._description_text) and not message)

    def clear_error(self) -> None:
        self._error.clear()
        self._error.hide()
        self._description.setVisible(bool(self._description_text))

    def _on_theme_changed(self, *_args) -> None:
        self.refresh_styles()

    def refresh_styles(self) -> None:
        self.setStyleSheet(Styles.get_form_field_qss())

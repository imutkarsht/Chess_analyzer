"""Stacked label + control + helper text, shadcn-style."""

from __future__ import annotations

from PyQt6.QtWidgets import QVBoxLayout, QWidget

from src.gui.theme.typography import TextRole, TextTone

from ..display.label import Label


class FormField(QWidget):
    """A labelled form control with optional helper and error text.

    The control is supplied by the caller so inputs keep the central
    :class:`~src.gui.components.controls.input.Input` / ``DatePicker`` styling while the
    label/description rhythm stays identical across forms.
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

        # Labels must be parented before setVisible(): a parentless QLabel is a
        # top-level window, so setVisible(True) would show a stray native window
        # that steals focus (and can pull macOS to another display/Space).
        self._label = Label(
            label,
            role=TextRole.CAPTION,
            weight=500,
            parent=self,
        )
        self._label.setVisible(bool(label))
        layout.addWidget(self._label)

        layout.addWidget(control)

        self._description = Label(
            description,
            role=TextRole.MICRO,
            tone=TextTone.SECONDARY,
            wrap=True,
            parent=self,
        )
        self._description.setVisible(bool(description))
        layout.addWidget(self._description)

        self._error = Label(
            "",
            role=TextRole.MICRO,
            tone=TextTone.BLUNDER,
            weight=500,
            wrap=True,
            parent=self,
        )
        self._error.hide()
        layout.addWidget(self._error)

    @property
    def label(self) -> Label:
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

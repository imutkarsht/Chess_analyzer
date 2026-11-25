# SPDX-License-Identifier: GPL-3.0-only
"""Path input with optional Browse/Clear actions."""

from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

from src.gui.components.controls.button import Button, ButtonVariant
from src.gui.components.controls.input import Input


class PathField(QWidget):
    """Path input with optional Browse/Clear actions at a fixed compact width."""

    def __init__(
        self,
        placeholder: str = "",
        *,
        browse_callback=None,
        clear_callback=None,
        parent=None,
        input_width: int = 520,
    ):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.line_edit = Input(placeholder, full_width=True)
        self.line_edit.setMinimumWidth(min(320, input_width))
        self.line_edit.setMaximumWidth(input_width)
        layout.addWidget(self.line_edit, 1)

        self.browse_btn = Button(
            "Browse",
            ButtonVariant.FILLED,
            icon="fa5s.folder-open",
            tooltip="Choose a file",
            on_click=browse_callback,
            parent=self,
        )
        self.browse_btn.setMaximumWidth(120)
        self.browse_btn.setMinimumWidth(110)
        layout.addWidget(self.browse_btn)

        self.clear_btn = None
        if clear_callback is not None:
            self.clear_btn = Button(
                "Clear",
                ButtonVariant.FILLED,
                icon="fa5s.times",
                tooltip="Clear the path",
                on_click=clear_callback,
                parent=self,
            )
            self.clear_btn.setMaximumWidth(100)
            self.clear_btn.setMinimumWidth(90)
            layout.addWidget(self.clear_btn)

        layout.addStretch(1)

    def text(self) -> str:
        return self.line_edit.text()

    def setText(self, text: str) -> None:
        self.line_edit.setText(text)

    def clear(self) -> None:
        self.line_edit.clear()

    @property
    def editingFinished(self):
        return self.line_edit.editingFinished

    def setPlaceholderText(self, text: str) -> None:
        self.line_edit.setPlaceholderText(text)


__all__ = ["PathField"]

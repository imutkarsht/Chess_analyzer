"""Shared segmented chip control built on the central Button component."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QWidget

from src.gui.components.button import Button, ButtonSize, ButtonVariant
from src.gui.styles import Styles
from src.gui.theme import ThemeManager

_UNSET = object()


class SegmentedControl(QFrame):
    """A row of mutually exclusive chips backed by checkable Buttons.

    ``options`` is an iterable of ``(label, value)`` pairs. The control owns the
    checked look through ``ButtonVariant.SEGMENT``; call sites never ship chip
    QSS.
    """

    valueChanged = pyqtSignal(object)

    def __init__(
        self,
        options: Iterable[tuple[str, Any]],
        value: Any = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SegmentedControl")

        self._buttons: dict[Any, Button] = {}
        self._value: Any = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        first_value = _UNSET
        for label, option_value in options:
            if first_value is _UNSET:
                first_value = option_value
            button = Button(
                label,
                ButtonVariant.SEGMENT,
                ButtonSize.XS,
                checkable=True,
            )
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            button.clicked.connect(
                lambda _checked=False, v=option_value: self._on_clicked(v)
            )
            self._buttons[option_value] = button
            layout.addWidget(button)

        initial = first_value if value is None else value
        if initial is _UNSET or initial not in self._buttons:
            raise ValueError(f"value must be one of {tuple(self._buttons)}")
        self._value = initial
        self._sync_checks()

        theme_manager = ThemeManager.instance()
        theme_manager.theme_changed.connect(self._on_theme_changed)
        theme_manager.accent_changed.connect(self._on_theme_changed)
        self.refresh_styles()

    def value(self) -> Any:
        return self._value

    def button(self, value: Any) -> Button:
        return self._buttons[value]

    def set_value(self, value: Any, emit: bool = False) -> None:
        if value not in self._buttons:
            raise ValueError(f"value must be one of {tuple(self._buttons)}")
        changed = value != self._value
        self._value = value
        self._sync_checks()
        if emit and changed:
            self.valueChanged.emit(value)

    def _on_clicked(self, value: Any) -> None:
        if value == self._value:
            # Re-assert the checked chip after a checkable button toggled itself.
            self._sync_checks()
            return
        self._value = value
        self._sync_checks()
        self.valueChanged.emit(value)

    def _sync_checks(self) -> None:
        for option_value, button in self._buttons.items():
            button.setChecked(option_value == self._value)

    def _on_theme_changed(self, *_args) -> None:
        self.refresh_styles()

    def refresh_styles(self) -> None:
        self.setStyleSheet(
            f"""
            QFrame#SegmentedControl {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border-radius: 6px;
                border: none;
            }}
            """
        )
        for button in self._buttons.values():
            button.refresh_styles()

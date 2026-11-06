# SPDX-License-Identifier: GPL-3.0-only
"""Label for data-driven colours that are not semantic palette tones."""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from src.gui.theme.typography import TextRole, TextTone

from .label import Label


class ColorLabel(Label):
    """A :class:`Label` whose colour comes from data, such as a chart series.

    Typography still comes from the shared role/weight rules; only the colour
    is emitted inline so arbitrary series colours keep matching their chart.
    Call ``set_color`` when the series colour changes, or rebuild the label.
    """

    def __init__(
        self,
        text: str = "",
        color: str = "",
        role: TextRole | str = TextRole.BODY,
        tone: TextTone | str = TextTone.PRIMARY,
        *,
        size: int | None = None,
        weight: int | None = None,
        wrap: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        self._color = color
        super().__init__(
            text,
            role,
            tone,
            size=size,
            weight=weight,
            wrap=wrap,
            parent=parent,
        )
        self._apply_color()

    def set_color(self, color: str) -> None:
        self._color = color
        self._apply_color()

    def refresh_styles(self) -> None:
        super().refresh_styles()
        self._apply_color()

    def _apply_color(self) -> None:
        self.setStyleSheet(
            f"color: {self._color}; background: transparent; border: none;"
        )

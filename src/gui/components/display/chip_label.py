# SPDX-License-Identifier: GPL-3.0-only
"""Small coloured chip used for captured pieces and material counts."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QWidget


class ChipLabel(QLabel):
    """A compact text chip with explicit foreground and background colours.

    Use this for data-driven chips (captured pieces, material advantage) where
    the colours are not semantic text tones. The chip owns its QSS so callers
    do not construct styled labels inline.
    """

    def __init__(
        self,
        text: str = "",
        *,
        foreground: str,
        background: str,
        font_size: int = 12,
        weight: int = 400,
        padding: str = "0px",
        radius: int = 4,
        margin_right: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._foreground = foreground
        self._background = background
        self._font_size = font_size
        self._weight = weight
        self._padding = padding
        self._radius = radius
        self._margin_right = margin_right
        self.refresh_styles()

    def set_colors(self, foreground: str, background: str) -> None:
        self._foreground = foreground
        self._background = background
        self.refresh_styles()

    def refresh_styles(self) -> None:
        margin = (
            f"margin-right: {self._margin_right}px;"
            if self._margin_right
            else ""
        )
        self.setStyleSheet(
            f"""
            color: {self._foreground};
            background-color: {self._background};
            font-size: {self._font_size}px;
            font-weight: {self._weight};
            padding: {self._padding};
            border-radius: {self._radius}px;
            {margin}
            """
        )

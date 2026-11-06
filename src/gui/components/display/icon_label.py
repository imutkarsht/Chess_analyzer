# SPDX-License-Identifier: GPL-3.0-only
"""Shared icon-only label."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QLabel, QWidget

from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.gui.theme.typography import TextTone
from src.gui.utils.icons import icon_pixmap


class IconLabel(QLabel):
    """A transparent, fixed-size label that renders an icon or fallback glyph.

    Use this for pixmap/icon labels instead of constructing a raw ``QLabel``
    and repeating the transparent style. Pass ``tone`` when the icon should
    follow the live palette; pass an explicit ``color`` for one-off icons.
    """

    def __init__(
        self,
        icon: str | QIcon | QPixmap | None = None,
        *,
        size: int = 16,
        icon_size: int | None = None,
        color: str | None = None,
        tone: TextTone | str | None = None,
        fallback: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: transparent; border: none;")
        self._icon = icon
        self._icon_size = icon_size or size
        self._color = color
        self._tone = TextTone(tone) if tone is not None else None
        self._fallback = fallback

        manager = ThemeManager.instance()
        manager.theme_changed.connect(self._on_theme_changed)
        manager.accent_changed.connect(self._on_theme_changed)
        if icon is not None:
            self.set_icon(icon)

    def set_icon(self, icon: str | QIcon | QPixmap | None) -> None:
        self._icon = icon
        self._apply_icon()

    def set_tone(self, tone: TextTone | str | None) -> None:
        self._tone = TextTone(tone) if tone is not None else None
        self._apply_icon()

    def set_color(self, color: str | None) -> None:
        self._color = color
        self._apply_icon()

    def set_fallback(self, text: str) -> None:
        self._fallback = text
        if self._icon is None:
            self._show_fallback()

    def refresh_styles(self) -> None:
        self._apply_icon()

    def _on_theme_changed(self, *_args) -> None:
        self._apply_icon()

    def _resolved_color(self) -> str:
        if self._tone is not None:
            return Styles.get_tone_color(self._tone)
        return self._color or Styles.COLOR_TEXT_SECONDARY

    def _apply_icon(self) -> None:
        icon = self._icon
        if isinstance(icon, QPixmap):
            if icon.isNull():
                self._show_fallback()
                return
            self.setPixmap(
                icon.scaled(
                    self._icon_size,
                    self._icon_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            return
        if isinstance(icon, QIcon):
            pixmap = icon.pixmap(self._icon_size, self._icon_size)
            if pixmap.isNull():
                self._show_fallback()
                return
            self.setPixmap(pixmap)
            return
        if isinstance(icon, str) and icon:
            pixmap = icon_pixmap(icon, self._resolved_color(), self._icon_size)
            if pixmap is not None and not pixmap.isNull():
                self.setPixmap(pixmap)
                return
        self._show_fallback()

    def _show_fallback(self) -> None:
        self.clear()
        if self._fallback:
            self.setText(self._fallback)

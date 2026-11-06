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
    """A transparent label that renders an icon or fallback glyph.

    Use this for pixmap/icon labels instead of constructing a raw ``QLabel``
    and repeating the transparent style. Pass ``tone`` when the icon should
    follow the live palette; pass an explicit ``color`` for one-off icons.
    ``scaled`` lets the pixmap follow the label's size instead of a fixed icon
    size (used by the board's dragged-piece ghost).
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
        fallback_size: int | None = None,
        fixed_size: bool = True,
        scaled: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if fixed_size:
            self.setFixedSize(size, size)
        else:
            self.resize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: transparent; border: none;")
        self._icon = icon
        self._icon_size = icon_size or size
        self._color = color
        self._tone = TextTone(tone) if tone is not None else None
        self._fallback = fallback
        self._fallback_size = fallback_size
        self._fixed_size = fixed_size
        self._scaled = scaled
        self.setScaledContents(scaled)

        manager = ThemeManager.instance()
        manager.theme_changed.connect(self._on_theme_changed)
        manager.accent_changed.connect(self._on_theme_changed)
        if icon is not None:
            self.set_icon(icon)

    def set_icon(self, icon: str | QIcon | QPixmap | None) -> None:
        self._icon = icon
        self._apply_icon()

    def set_icon_size(self, size: int) -> None:
        self._icon_size = max(1, int(size))
        if self._fixed_size:
            self.setFixedSize(self._icon_size, self._icon_size)
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

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        if self._scaled:
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
            if self._scaled:
                self.setPixmap(icon)
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
            target = max(1, self.width(), self.height()) if self._scaled else self._icon_size
            pixmap = icon.pixmap(target, target)
            if pixmap.isNull():
                self._show_fallback()
                return
            self.setPixmap(pixmap)
            return
        if isinstance(icon, str) and icon:
            target = max(1, self.width(), self.height()) if self._scaled else self._icon_size
            pixmap = icon_pixmap(icon, self._resolved_color(), target)
            if pixmap is not None and not pixmap.isNull():
                self.setPixmap(pixmap)
                return
        self._show_fallback()

    def _show_fallback(self) -> None:
        self.clear()
        if self._fallback:
            self.setText(self._fallback)
            size = (
                f"font-size: {self._fallback_size}px;"
                if self._fallback_size is not None
                else ""
            )
            self.setStyleSheet(
                "background: transparent; border: none; "
                f"color: {self._resolved_color()}; {size}"
            )

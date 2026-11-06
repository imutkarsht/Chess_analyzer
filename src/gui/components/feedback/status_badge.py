# SPDX-License-Identifier: GPL-3.0-only
"""Shared status, result, classification, and count badges."""

from __future__ import annotations

from enum import StrEnum

from PyQt6.QtWidgets import QLabel, QWidget

from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.gui.theme.typography import TextTone

_TONES = {"neutral", *(tone.value for tone in TextTone)}


class BadgeVariant(StrEnum):
    SOFT = "soft"
    OUTLINE = "outline"
    SOLID = "solid"


class StatusBadge(QLabel):
    """Small semantic pill used for status, results, classifications and counts.

    Variants:
    - ``soft``: tinted surface with a semantic border (default)
    - ``outline``: transparent surface with a semantic border
    - ``solid``: filled semantic surface with contrasting text
    """

    def __init__(
        self,
        text: str = "",
        tone: str = "neutral",
        *,
        variant: BadgeVariant | str = BadgeVariant.SOFT,
        mono: bool = False,
        font_size: int = 11,
        weight: int = 600,
        padding: str = "3px 8px",
        radius: int = 6,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        if tone not in _TONES:
            raise ValueError(f"tone must be one of {sorted(_TONES)}")
        self._tone = tone
        self._variant = BadgeVariant(variant)
        self._mono = mono
        self._font_size = font_size
        self._weight = weight
        self._padding = padding
        self._radius = radius

        theme_manager = ThemeManager.instance()
        theme_manager.theme_changed.connect(self._on_theme_changed)
        theme_manager.accent_changed.connect(self._on_theme_changed)
        self.refresh_styles()

    @property
    def tone(self) -> str:
        return self._tone

    @property
    def variant(self) -> BadgeVariant:
        return self._variant

    def set_tone(self, tone: str) -> None:
        if tone not in _TONES:
            raise ValueError(f"tone must be one of {sorted(_TONES)}")
        if tone == self._tone:
            return
        self._tone = tone
        self.refresh_styles()

    def set_variant(self, variant: BadgeVariant | str) -> None:
        self._variant = BadgeVariant(variant)
        self.refresh_styles()

    def set_mono(self, mono: bool) -> None:
        self._mono = bool(mono)
        self.refresh_styles()

    def set_text(self, text: str) -> None:
        self.setText(text)

    def set_weight(self, weight: int) -> None:
        self._weight = weight
        self.refresh_styles()

    def _on_theme_changed(self, *_args) -> None:
        self.refresh_styles()

    def _tone_color(self) -> str:
        if self._tone == "neutral":
            return Styles.COLOR_TEXT_SECONDARY
        return Styles.get_tone_color(self._tone)

    def _tone_colors(self) -> tuple[str, str, str]:
        """Return ``(foreground, border, background)`` for the active tone."""
        color = self._tone_color()
        if self._variant is BadgeVariant.OUTLINE:
            return color, color, "transparent"
        if self._variant is BadgeVariant.SOLID:
            return Styles.COLOR_ON_ACCENT, color, color
        return color, color, Styles.COLOR_SURFACE_LIGHT

    def refresh_styles(self) -> None:
        foreground, border, background = self._tone_colors()
        family = ""
        if self._mono:
            family = (
                'font-family: "SFMono-Regular", "Menlo", "Consolas", '
                '"Liberation Mono", monospace;'
            )
        self.setStyleSheet(
            f"""
            background-color: {background};
            color: {foreground};
            {family}
            font-size: {self._font_size}px;
            font-weight: {self._weight};
            border: 1px solid {border};
            border-radius: {self._radius}px;
            padding: {self._padding};
            """
        )

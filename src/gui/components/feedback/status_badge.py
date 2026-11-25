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
    TONAL = "tonal"
    SOFT = "soft"  # legacy alias for tonal
    OUTLINE = "outline"
    SOLID = "solid"
    QUIET = "quiet"


class BadgeSize(StrEnum):
    SM = "sm"
    MD = "md"


_SIZE_SPECS = {
    BadgeSize.SM: {"font_size": 11, "weight": 500, "padding": "2px 6px", "radius": 4},
    BadgeSize.MD: {"font_size": 12, "weight": 500, "padding": "3px 8px", "radius": 4},
}


class StatusBadge(QLabel):
    """Small semantic pill used for status, results, classifications and counts.

    Variants:
    - ``tonal``: subtle tone wash, no border (default)
    - ``outline``: transparent surface with a semantic border (keycaps)
    - ``solid``: filled semantic surface with contrasting text (active steps)
    - ``quiet``: text only, no surface or border
    """

    def __init__(
        self,
        text: str = "",
        tone: str = "neutral",
        *,
        variant: BadgeVariant | str = BadgeVariant.TONAL,
        size: BadgeSize | str = BadgeSize.SM,
        mono: bool = False,
        font_size: int | None = None,
        weight: int | None = None,
        padding: str | None = None,
        radius: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        if tone not in _TONES:
            raise ValueError(f"tone must be one of {sorted(_TONES)}")
        spec = _SIZE_SPECS[BadgeSize(size)]
        self._tone = tone
        self._variant = BadgeVariant(variant)
        self._mono = mono
        self._font_size = spec["font_size"] if font_size is None else font_size
        self._weight = spec["weight"] if weight is None else weight
        self._padding = spec["padding"] if padding is None else padding
        self._radius = spec["radius"] if radius is None else radius

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

    def _tone_colors(self) -> tuple[str, str | None, str]:
        """Return ``(foreground, border, background)`` for the active tone."""
        if self._tone == "neutral":
            if self._variant in (BadgeVariant.TONAL, BadgeVariant.SOFT):
                return Styles.COLOR_TEXT_SECONDARY, None, Styles.COLOR_SURFACE_LIGHT
            if self._variant is BadgeVariant.OUTLINE:
                return Styles.COLOR_TEXT_SECONDARY, Styles.COLOR_BORDER, "transparent"
            if self._variant is BadgeVariant.SOLID:
                return Styles.COLOR_TEXT_PRIMARY, None, Styles.COLOR_SURFACE_LIGHT
            return Styles.COLOR_TEXT_SECONDARY, None, "transparent"

        color = self._tone_color()
        if self._variant in (BadgeVariant.TONAL, BadgeVariant.SOFT):
            return Styles.COLOR_TEXT_PRIMARY, None, Styles.get_tone_surface(self._tone)
        if self._variant is BadgeVariant.OUTLINE:
            return color, color, "transparent"
        if self._variant is BadgeVariant.SOLID:
            return Styles.COLOR_ON_ACCENT, None, color
        return color, None, "transparent"

    def refresh_styles(self) -> None:
        foreground, border, background = self._tone_colors()
        family = ""
        if self._mono:
            family = (
                'font-family: "SFMono-Regular", "Menlo", "Consolas", '
                '"Liberation Mono", monospace;'
            )
        border_rule = (
            f"border: 1px solid {border};" if border is not None else "border: none;"
        )
        self.setStyleSheet(
            f"""
            QLabel {{
                background-color: {background};
                color: {foreground};
                {family}
                font-size: {self._font_size}px;
                font-weight: {self._weight};
                {border_rule}
                border-radius: {self._radius}px;
                padding: {self._padding};
            }}
            """
        )

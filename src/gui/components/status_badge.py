"""Shared pill badge for card headers and status labels."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QWidget

from src.gui.styles import Styles
from src.gui.theme import ThemeManager

_TONES = ("neutral", "accent", "best", "mistake", "blunder", "brilliant", "engine_busy")


class StatusBadge(QLabel):
    """Small header pill with a semantic tone.

    Keeps the neutral ``action_badge`` look and the dynamic tone colours used
    by cards (for example Brilliancy Hall switching to the brilliant tone when
    the count is non-zero). Callers use :meth:`set_tone`, never raw QSS.
    """

    def __init__(
        self,
        text: str = "",
        tone: str = "neutral",
        *,
        font_size: int = 11,
        weight: int = 600,
        padding: str = "3px 8px",
        radius: int = 6,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        if tone not in _TONES:
            raise ValueError(f"tone must be one of {_TONES}")
        self._tone = tone
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

    def set_tone(self, tone: str) -> None:
        if tone not in _TONES:
            raise ValueError(f"tone must be one of {_TONES}")
        if tone == self._tone:
            return
        self._tone = tone
        self.refresh_styles()

    def set_text(self, text: str) -> None:
        self.setText(text)

    def set_weight(self, weight: int) -> None:
        self._weight = weight
        self.refresh_styles()

    def _on_theme_changed(self, *_args) -> None:
        self.refresh_styles()

    def _tone_colors(self) -> tuple[str, str, str]:
        """Return ``(foreground, border, background)`` for the active tone."""
        surface = Styles.COLOR_SURFACE_LIGHT
        neutral = (Styles.COLOR_TEXT_SECONDARY, Styles.COLOR_BORDER, surface)
        tones = {
            "neutral": neutral,
            "accent": (Styles.COLOR_ACCENT, Styles.COLOR_ACCENT, surface),
            "best": (Styles.COLOR_BEST, Styles.COLOR_BEST, surface),
            "mistake": (Styles.COLOR_MISTAKE, Styles.COLOR_MISTAKE, surface),
            "blunder": (Styles.COLOR_BLUNDER, Styles.COLOR_BLUNDER, surface),
            "brilliant": (Styles.COLOR_BRILLIANT, Styles.COLOR_BRILLIANT, surface),
            "engine_busy": (Styles.COLOR_ENGINE_BUSY, Styles.COLOR_ENGINE_BUSY, surface),
        }
        return tones[self._tone]

    def refresh_styles(self) -> None:
        foreground, border, background = self._tone_colors()
        self.setStyleSheet(
            f"""
            background-color: {background};
            color: {foreground};
            font-size: {self._font_size}px;
            font-weight: {self._weight};
            border: 1px solid {border};
            border-radius: {self._radius}px;
            padding: {self._padding};
            """
        )

"""Shared compact progress bar for dashboard cards."""

from __future__ import annotations

from PyQt6.QtWidgets import QProgressBar, QSizePolicy, QWidget

from src.gui.styles import Styles


class MiniBar(QProgressBar):
    """A slim, text-free progress bar with card-consistent styling.

    Cards rebuild the bar when ``MetricCard.refresh_styles`` re-renders their
    content, so palette colours are captured per construction.
    """

    def __init__(
        self,
        value: int = 0,
        color: str = Styles.COLOR_ACCENT,
        *,
        height: int = 6,
        radius: int = 3,
        track_color: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._color = color
        self._radius = radius
        self._track_color = track_color

        self.setRange(0, 100)
        self.setValue(max(0, min(100, int(value))))
        self.setTextVisible(False)
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.refresh_styles()

    def refresh_styles(self) -> None:
        track = self._track_color or Styles.COLOR_SURFACE
        chunk = self._color if self.value() > 0 else "transparent"
        self.setStyleSheet(
            f"""
            QProgressBar {{
                background-color: {track};
                border: none;
                border-radius: {self._radius}px;
            }}
            QProgressBar::chunk {{
                background-color: {chunk};
                border-radius: {self._radius}px;
            }}
            """
        )

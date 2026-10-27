"""Shared empty-state label for dashboard cards and data panels."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QWidget

from src.gui.styles import Styles
from src.gui.theme import ThemeManager


class EmptyState(QLabel):
    """Centered, word-wrapped secondary text used when a card has no data.

    The label owns its QSS so cards never repeat the empty-state block, and it
    re-applies the live palette on theme/accent changes.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)

        theme_manager = ThemeManager.instance()
        theme_manager.theme_changed.connect(self._on_theme_changed)
        theme_manager.accent_changed.connect(self._on_theme_changed)
        self.refresh_styles()

    def _on_theme_changed(self, *_args) -> None:
        self.refresh_styles()

    def refresh_styles(self) -> None:
        self.setStyleSheet(
            f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 12px;
            padding: 40px 10px;
            background: transparent;
            """
        )

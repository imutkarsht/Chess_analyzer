# SPDX-License-Identifier: GPL-3.0-only
"""Themed list widget for navigation rails."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QFrame, QListWidget, QWidget

from src.gui.theme import ThemeManager


class ListView(QListWidget):
    """The app's themed navigation list; theme refreshes happen here."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NavList")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSpacing(2)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        manager = ThemeManager.instance()
        manager.theme_changed.connect(self._on_theme_changed)
        manager.accent_changed.connect(self._on_theme_changed)
        self.refresh_styles()

    def refresh_styles(self) -> None:
        """Nav-list chrome is global; repolish keeps the widget coherent."""
        self.style().unpolish(self)
        self.style().polish(self)

    def _on_theme_changed(self, *_args) -> None:
        self.refresh_styles()


__all__ = ["ListView"]

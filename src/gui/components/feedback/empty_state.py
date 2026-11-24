"""Shared empty-state label for dashboard cards and data panels."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QWidget


class EmptyState(QLabel):
    """Centered, word-wrapped secondary text used when a card has no data.

    The look is owned by the global QSS template via ``#EmptyState``; the
    label only sets alignment, wrapping, and the object name.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("EmptyState")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)

    def refresh_styles(self) -> None:
        """Global chrome; repolish keeps the label coherent."""
        self.style().unpolish(self)
        self.style().polish(self)

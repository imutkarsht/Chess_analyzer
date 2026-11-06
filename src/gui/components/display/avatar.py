# SPDX-License-Identifier: GPL-3.0-only
"""Circular avatar label with an initials fallback."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QWidget

from src.gui.styles import Styles


class Avatar(QLabel):
    """Fixed-size avatar that shows a circular image or initials."""

    def __init__(self, size: int = 44, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._size = size
        self._pixmap: QPixmap | None = None
        self._initials = ""
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hide()

    def set_content(self, pixmap: QPixmap | None, initials: str = "") -> None:
        self._pixmap = pixmap if pixmap is not None and not pixmap.isNull() else None
        self._initials = initials
        self._apply()

    def refresh_styles(self) -> None:
        self._apply()

    def _apply(self) -> None:
        if self._pixmap is not None:
            self.setPixmap(self._pixmap)
            self.setText("")
            self.setStyleSheet(
                "background: transparent; border: none; padding: 0px;"
            )
            return

        self.setPixmap(QPixmap())
        self.setText(self._initials)
        self.setStyleSheet(
            f"""
            QLabel {{
                background-color: {Styles.COLOR_ACCENT_SUBTLE};
                color: {Styles.COLOR_ACCENT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: {self._size // 2}px;
                font-size: 18px;
                font-weight: 700;
            }}
            """
        )

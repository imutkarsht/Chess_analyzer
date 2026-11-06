# SPDX-License-Identifier: GPL-3.0-only
"""Digital chess-clock label used by the captured-pieces row."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QWidget

from src.gui.styles import Styles


class ClockLabel(QLabel):
    """Monospace clock pill with the shared digital-clock styling."""

    def __init__(self, *, compact: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._compact = compact
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hide()

    def set_clock(
        self,
        text: str,
        *,
        background: str,
        foreground: str,
        border: str,
    ) -> None:
        self.setText(text)
        self.setStyleSheet(
            Styles.get_digital_clock_style(
                background,
                foreground,
                border,
                compact=self._compact,
            )
        )

    def set_compact(self, compact: bool) -> None:
        self._compact = bool(compact)

    def refresh_styles(
        self,
        *,
        background: str,
        foreground: str,
        border: str,
    ) -> None:
        self.setStyleSheet(
            Styles.get_digital_clock_style(
                background,
                foreground,
                border,
                compact=self._compact,
            )
        )

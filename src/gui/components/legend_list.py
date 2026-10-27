"""Shared chart legend list for dashboard cards."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.gui.styles import Styles


class LegendList(QWidget):
    """Vertical legend with an optional icon, label and colored value.

    Cards rebuild the legend when ``MetricCard.refresh_styles`` re-renders
    their content, so palette colours are captured per construction.
    """

    def __init__(self, spacing: int = 6, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self._layout.setSpacing(spacing)

    def add_row(
        self,
        label: str,
        value: str,
        color: str,
        pixmap: QPixmap | None = None,
    ) -> None:
        row = QHBoxLayout()
        row.setSpacing(8)

        if pixmap is not None and not pixmap.isNull():
            icon_lbl = QLabel()
            icon_lbl.setPixmap(pixmap)
            icon_lbl.setStyleSheet("border: none; background: transparent;")
            row.addWidget(icon_lbl)
        else:
            dot = QLabel("●")
            dot.setStyleSheet(
                f"color: {color}; font-size: 14px; border: none; background: transparent;"
            )
            row.addWidget(dot)

        name_lbl = QLabel(label)
        name_lbl.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; "
            "font-weight: 500; border: none; background: transparent;"
        )
        row.addWidget(name_lbl)

        row.addStretch()

        value_lbl = QLabel(value)
        value_lbl.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: bold; "
            "border: none; background: transparent;"
        )
        row.addWidget(value_lbl)

        self._layout.addLayout(row)

    def add_empty(self, text: str, italic: bool = False) -> None:
        label = QLabel(text)
        style = (
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; "
            "border: none; background: transparent;"
        )
        if italic:
            style = (
                f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; "
                "font-style: italic; border: none; background: transparent;"
            )
        label.setStyleSheet(style)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(label)

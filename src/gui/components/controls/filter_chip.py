"""Removable filter token with separate open and remove actions."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QWidget

from src.gui.components.controls.button import Button, ButtonSize, ButtonVariant
from src.gui.styles import Styles


def _dot_icon(color: str) -> QIcon:
    pixmap = QPixmap(8, 8)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(1, 1, 6, 6)
    painter.end()
    return QIcon(pixmap)


class FilterChip(QFrame):
    """A compact token whose body opens a filter and whose × removes it."""

    open_requested = pyqtSignal()
    remove_requested = pyqtSignal()

    def __init__(
        self,
        text: str,
        *,
        dot_color: str,
        accessible_label: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("FilterChip")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 1, 2, 1)
        layout.setSpacing(0)

        self.body = Button(
            text,
            ButtonVariant.GHOST,
            ButtonSize.SM,
            icon=_dot_icon(dot_color),
            icon_position="left",
            icon_size=8,
            font_weight=600,
            on_click=lambda: self.open_requested.emit(),
            parent=self,
        )
        self.body.setAccessibleName(
            f"{accessible_label}. Open filter." if accessible_label else text
        )
        layout.addWidget(self.body)

        self.close_button = Button(
            variant=ButtonVariant.GHOST,
            size=ButtonSize.SM,
            icon="fa5s.times",
            icon_position="only",
            tooltip="Remove filter",
            on_click=lambda: self.remove_requested.emit(),
            parent=self,
        )
        self.close_button.setAccessibleName(
            f"Remove {accessible_label}" if accessible_label else "Remove filter"
        )
        layout.addWidget(self.close_button)
        self.refresh_styles()

    def refresh_styles(self) -> None:
        self.setStyleSheet(Styles.get_filter_chip_style())
        self.body.refresh_styles()
        self.close_button.refresh_styles()

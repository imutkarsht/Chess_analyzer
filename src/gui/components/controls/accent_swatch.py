# SPDX-License-Identifier: GPL-3.0-only
"""Circular accent preset used by Appearance settings."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QAbstractButton, QWidget

from src.gui.theme import ThemeManager


class AccentSwatch(QAbstractButton):
    """A checkable colour chip with a painted focus and selection ring."""

    def __init__(
        self,
        color: str,
        name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._color = color
        self._name = name
        self._hovered = False

        self.setObjectName("AccentSwatch")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(32, 32)
        self.setAccessibleName(f"{name} accent")
        self.setAccessibleDescription(f"Use the {name.lower()} accent colour.")
        self.setToolTip(f"{name} accent")

    @property
    def color(self) -> str:
        return self._color

    @property
    def name(self) -> str:
        return self._name

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        del event
        palette = ThemeManager.palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        side = float(min(self.width(), self.height()))
        fill = QRectF(6.0, 6.0, side - 12.0, side - 12.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._color))
        painter.drawEllipse(fill)

        ring = QRectF(3.0, 3.0, side - 6.0, side - 6.0)
        if self.isChecked():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(palette.text_primary), 2.0))
            painter.drawEllipse(ring)
        elif self._hovered:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(palette.border_light), 1.5))
            painter.drawEllipse(ring)

        if self.hasFocus():
            focus_pen = QPen(QColor(palette.ui_accent), 1.25)
            focus_pen.setStyle(Qt.PenStyle.DotLine)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(focus_pen)
            painter.drawEllipse(QRectF(0.75, 0.75, side - 1.5, side - 1.5))

        painter.end()


__all__ = ["AccentSwatch"]

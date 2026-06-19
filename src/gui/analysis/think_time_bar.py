"""
Custom widget representing a horizontal bar visualising the time a side spent thinking on a move.
"""
from typing import Optional
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QBrush, QLinearGradient
from ..styles import Styles

class ThinkTimeBar(QWidget):
    """
    Horizontal bar visualising the time a side spent thinking on a move.

    Colour goes from green (fast, ≤5 s) through yellow (10–20 s) to red
    (very long, ≥30 s). The bar is rendered to a percentage of the
    configurable max_seconds; if the value is missing the widget shows
    an empty grey bar with no text.
    """

    def __init__(self, max_seconds: float = 30.0, parent: QWidget = None):
        super().__init__(parent)
        self._value: Optional[float] = None
        self._max = max(1.0, float(max_seconds))
        self.setMinimumWidth(50)
        self.setMinimumHeight(18)

    def set_value(self, seconds: Optional[float]) -> None:
        if seconds is not None:
            try:
                self._value = float(seconds)
            except (ValueError, TypeError):
                self._value = None
        else:
            self._value = None
        self._update_tooltip()
        self.update()

    def _update_tooltip(self) -> None:
        if self._value is None:
            self.setToolTip("No clock data")
        else:
            self.setToolTip(f"Think time: {self._value:.1f}s")

    def _colour_for(self, ratio: float) -> QColor:
        """ratio ∈ [0, 1] → colour along green→yellow→red gradient."""
        ratio = max(0.0, min(1.0, ratio))
        # 0.0 → green, 0.5 → yellow, 1.0 → red
        if ratio < 0.5:
            t = ratio / 0.5
            r = int(76 + (255 - 76) * t)   # 76 → 255
            g = int(175 + (193 - 175) * t)  # 175 → 193
            b = int(80 + 7 * t)             # 80 → 7
            return QColor(r, g, b)
        else:
            t = (ratio - 0.5) / 0.5
            r = int(255 + (231 - 255) * t)  # 255 → 231
            g = int(193 + (76 - 193) * t)   # 193 → 76
            b = int(7 + (60 - 7) * t)       # 7 → 60
            return QColor(r, g, b)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()

        # Background (empty track)
        p.setBrush(QBrush(QColor(60, 60, 60)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect.adjusted(2, 4, -2, -4), 4, 4)

        if self._value is None:
            p.end()
            return

        ratio = min(1.0, self._value / self._max)
        fill_width = int(rect.width() * ratio) - 4
        if fill_width < 1:
            p.end()
            return

        colour = self._colour_for(ratio)
        # Gradient for a softer look
        gradient = QLinearGradient(0, 0, fill_width, 0)
        gradient.setColorAt(0.0, colour.darker(110))
        gradient.setColorAt(1.0, colour)
        p.setBrush(QBrush(gradient))
        p.drawRoundedRect(rect.adjusted(2, 4, -2, -4), 4, 4)

        # Numeric label inside (or beside) the bar
        p.setPen(QColor(255, 255, 255))
        font = p.font()
        font.setPointSize(9)
        font.setBold(True)
        p.setFont(font)
        
        if self._value >= 3600:
            time_str = f"{self._value / 3600:.1f}h"
        elif self._value >= 60:
            time_str = f"{self._value / 60:.1f}m"
        else:
            time_str = f"{self._value:.1f}s"
            
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, time_str)
        p.end()

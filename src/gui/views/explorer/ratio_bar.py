"""Compact white/draw/black result bar for explorer game rows."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath
from PyQt6.QtWidgets import QWidget

from src.gui.styles import Styles


class RatioBar(QWidget):
    """Painted result bar; text is drawn so the widget owns its geometry."""

    def __init__(self, w_pct, d_pct, b_pct, parent=None):
        super().__init__(parent)
        self.setFixedSize(140, 16)
        self._segments = (
            (w_pct, Styles.COLOR_RESULT_WIN),
            (d_pct, Styles.COLOR_RESULT_DRAW),
            (b_pct, Styles.COLOR_RESULT_LOSS),
        )
        self.setToolTip(
            f"White Wins: {w_pct}%  |  Draws: {d_pct}%  |  Black Wins: {b_pct}%"
        )

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        bounds = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(bounds, 4, 4)
        painter.setClipPath(clip)

        font = QFont(self.font())
        font.setPixelSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))

        x = bounds.left()
        for pct, color in self._segments:
            if pct <= 0:
                continue
            width = bounds.width() * (pct / 100.0)
            segment = QRectF(x, bounds.top(), width, bounds.height())
            painter.fillRect(segment, QColor(color))
            if pct >= 12:
                painter.drawText(
                    segment,
                    Qt.AlignmentFlag.AlignCenter,
                    f"{pct}%",
                )
            x += width

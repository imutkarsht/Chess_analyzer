"""
CircularAccuracyWidget - Centered circular progress arc gauge for accuracy % and ACPL stats.
Matches reference UI design with centered number inside gauge, side label, and ACPL text.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont
from src.gui.styles import Styles


class CircularArcGauge(QWidget):
    """Clean QPainter circular arc progress gauge starting from 12 o'clock (-90 deg)."""

    def __init__(self, accuracy=0.0, parent=None):
        super().__init__(parent)
        self._accuracy = accuracy
        self.setFixedSize(68, 68)

    def set_accuracy(self, accuracy: float):
        self._accuracy = max(0.0, min(100.0, float(accuracy)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        stroke_width = 5.0
        padding = stroke_width / 2.0 + 2.0
        rect = QRectF(padding, padding, width - 2 * padding, height - 2 * padding)

        # Track background
        bg_pen = QPen(QColor(Styles.COLOR_SURFACE_LIGHT), stroke_width, Qt.PenStyle.SolidLine)
        bg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(bg_pen)
        painter.drawEllipse(rect)

        # Progress Arc (12 o'clock top center)
        hex_color = Styles.get_accuracy_color(self._accuracy)
        arc_pen = QPen(QColor(hex_color), stroke_width, Qt.PenStyle.SolidLine)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen)

        start_angle = 90 * 16
        span_angle = -int((self._accuracy / 100.0) * 360 * 16)
        painter.drawArc(rect, start_angle, span_angle)

        # Center accuracy number (e.g. 92.6)
        painter.setPen(QColor(Styles.COLOR_TEXT_PRIMARY))
        font = QFont("Inter", 11, QFont.Weight.Bold)
        painter.setFont(font)
        acc_text = f"{self._accuracy:.1f}" if self._accuracy < 99.95 else f"{self._accuracy:.0f}"
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, acc_text)
        painter.end()


class CircularAccuracyWidget(QWidget):
    """Centered accuracy gauge unit (Gauge + Side Title + ACPL)."""

    def __init__(self, side="White", accuracy=0.0, acpl=None, parent=None):
        super().__init__(parent)
        self.side = side
        self.accuracy = accuracy
        self.acpl = acpl

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Arc Gauge
        self.gauge = CircularArcGauge(accuracy=self.accuracy)
        layout.addWidget(self.gauge, 0, Qt.AlignmentFlag.AlignCenter)

        # Side Title ("White" / "Black")
        self.side_label = QLabel(self.side)
        self.side_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.side_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px; font-weight: bold; background: transparent; border: none;")
        layout.addWidget(self.side_label)

        # ACPL Label ("ACPL 18")
        acpl_str = f"ACPL {self.acpl:.0f}" if self.acpl is not None else "ACPL -"
        self.acpl_label = QLabel(acpl_str)
        self.acpl_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.acpl_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 11px; background: transparent; border: none;")
        layout.addWidget(self.acpl_label)

    def set_data(self, accuracy: float, acpl=None):
        self.accuracy = accuracy
        self.acpl = acpl
        self.gauge.set_accuracy(accuracy)
        acpl_str = f"ACPL {self.acpl:.0f}" if self.acpl is not None else "ACPL -"
        self.acpl_label.setText(acpl_str)

    def refresh_styles(self):
        self.side_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px; font-weight: bold; background: transparent; border: none;")
        self.acpl_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 11px; background: transparent; border: none;")
        if hasattr(self, 'gauge'):
            self.gauge.update()

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QPen, QLinearGradient
import math

class LoadingOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setVisible(False)
        self.setCursor(Qt.CursorShape.WaitCursor)
        
        # Spinner state
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        
        # Shimmer state
        self._shimmer_pos = 0.0
        self._shimmer_animation = QPropertyAnimation(self, b"shimmer_pos")
        self._shimmer_animation.setDuration(2000)
        self._shimmer_animation.setStartValue(0.0)
        self._shimmer_animation.setEndValue(1.0)
        self._shimmer_animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._shimmer_animation.setLoopCount(-1)
        
        # Layout for text
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.setSpacing(10)
        
        self.text_label = QLabel("")
        self.text_label.setStyleSheet("color: white; font-weight: bold; font-size: 18px; background: transparent;")
        
        self.sub_label = QLabel("")
        self.sub_label.setStyleSheet("color: #cccccc; font-size: 14px; background: transparent;")
        
        self.layout.addStretch()
        self.layout.addSpacing(60)
        self.layout.addWidget(self.text_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.sub_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addStretch()

    @pyqtProperty(float)
    def shimmer_pos(self):
        return self._shimmer_pos
        
    @shimmer_pos.setter
    def shimmer_pos(self, value):
        self._shimmer_pos = value
        self.update()

    def start(self, text="Loading...", sub_text=""):
        self.text_label.setText(text)
        self.sub_label.setText(sub_text)
        self.sub_label.setVisible(bool(sub_text))
        self.setVisible(True)
        self.raise_()
        self.timer.start(50)
        self._shimmer_animation.start()
        parent = self.parent()
        if parent:
            self.resize(parent.size())

    def stop(self):
        self.timer.stop()
        self._shimmer_animation.stop()
        self.setVisible(False)

    def rotate(self):
        self.angle = (self.angle + 30) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Semi-transparent background with shimmer
        painter.fillRect(self.rect(), QColor(0, 0, 0, 140))
        
        # Shimmer effect
        shimmer_width = self.width() * 0.3
        shimmer_x = -shimmer_width + (self.width() + shimmer_width) * self._shimmer_pos
        
        gradient = QLinearGradient(shimmer_x, 0, shimmer_x + shimmer_width, self.height())
        gradient.setColorAt(0, QColor(255, 255, 255, 0))
        gradient.setColorAt(0.5, QColor(255, 255, 255, 15))
        gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(self.rect(), gradient)
        
        # Draw Spinner
        center_x = self.width() / 2
        center_y = self.height() / 2
        radius = 20
        
        painter.translate(center_x, center_y)
        painter.rotate(self.angle)
        
        pen = QPen(QColor("white"))
        pen.setWidth(4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        # Draw 8 ticks
        for i in range(8):
            painter.rotate(45)
            opacity = (i + 1) / 8.0
            color = QColor("white")
            color.setAlphaF(opacity)
            pen.setColor(color)
            painter.setPen(pen)
            painter.drawLine(radius + 5, 0, radius + 15, 0)

    def resizeEvent(self, event):
        if self.parent():
            self.resize(self.parent().size())
        super().resizeEvent(event)


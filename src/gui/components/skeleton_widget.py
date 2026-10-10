"""Skeleton loading placeholders for improved perceived performance."""
from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, pyqtProperty
from PyQt6.QtGui import QColor, QLinearGradient, QPainter
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget


class SkeletonWidget(QFrame):
    """A single skeleton placeholder with shimmer animation."""

    def __init__(self, width=None, height=24, radius=4, parent=None):
        super().__init__(parent)
        from .styles import Styles

        self._shimmer_pos = 0.0
        self._base_color = QColor(Styles.COLOR_SURFACE_LIGHT)
        self._highlight_color = QColor(Styles.COLOR_BORDER)
        self._radius = radius

        if width:
            self.setFixedWidth(width)
        else:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(height)

        # Shimmer animation
        self._animation = QPropertyAnimation(self, b"shimmer_pos")
        self._animation.setDuration(1200)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._animation.setLoopCount(-1)  # Infinite

    def start_animation(self):
        self._animation.start()

    def stop_animation(self):
        self._animation.stop()

    @pyqtProperty(float)
    def shimmer_pos(self):
        return self._shimmer_pos

    @shimmer_pos.setter
    def shimmer_pos(self, value):
        self._shimmer_pos = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Base rounded rect
        painter.setBrush(self._base_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), self._radius, self._radius)

        # Shimmer gradient overlay
        shimmer_width = self.width() * 0.4
        shimmer_x = -shimmer_width + (self.width() + shimmer_width) * self._shimmer_pos

        gradient = QLinearGradient(shimmer_x, 0, shimmer_x + shimmer_width, 0)
        gradient.setColorAt(0, QColor(0, 0, 0, 0))
        gradient.setColorAt(0.5, self._highlight_color)
        gradient.setColorAt(1, QColor(0, 0, 0, 0))

        painter.setBrush(gradient)
        painter.drawRoundedRect(self.rect(), self._radius, self._radius)


class SkeletonRow(QWidget):
    """A skeleton row for list items."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Icon placeholder
        self.icon_skel = SkeletonWidget(width=24, height=24, radius=12)
        layout.addWidget(self.icon_skel)

        # Text area
        text_layout = QVBoxLayout()
        text_layout.setSpacing(8)

        self.title_skel = SkeletonWidget(width=200, height=16, radius=4)
        self.subtitle_skel = SkeletonWidget(width=120, height=12, radius=4)

        text_layout.addWidget(self.title_skel)
        text_layout.addWidget(self.subtitle_skel)

        layout.addLayout(text_layout)
        layout.addStretch()

    def start_animation(self):
        self.icon_skel.start_animation()
        self.title_skel.start_animation()
        self.subtitle_skel.start_animation()

    def stop_animation(self):
        self.icon_skel.stop_animation()
        self.title_skel.stop_animation()
        self.subtitle_skel.stop_animation()




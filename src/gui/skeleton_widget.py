"""Skeleton loading placeholders for improved perceived performance."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, QSizePolicy
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QLinearGradient


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


class SkeletonList(QWidget):
    """A skeleton list with multiple rows."""
    
    def __init__(self, row_count=5, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        from .styles import Styles
        
        self.rows = []
        for i in range(row_count):
            row = SkeletonRow()
            row.setStyleSheet(f"border-bottom: 1px solid {Styles.COLOR_BORDER};")
            layout.addWidget(row)
            self.rows.append(row)
            
        layout.addStretch()
        
    def start_animation(self):
        for row in self.rows:
            row.start_animation()
            
    def stop_animation(self):
        for row in self.rows:
            row.stop_animation()


class SkeletonCard(QWidget):
    """A skeleton card placeholder."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        from .styles import Styles
        
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        self.header_skel = SkeletonWidget(width=150, height=20, radius=4)
        layout.addWidget(self.header_skel)
        
        # Content lines
        self.line1 = SkeletonWidget(height=14, radius=4)
        self.line2 = SkeletonWidget(width=200, height=14, radius=4)
        self.line3 = SkeletonWidget(width=100, height=14, radius=4)
        
        layout.addWidget(self.line1)
        layout.addWidget(self.line2)
        layout.addWidget(self.line3)
        
    def start_animation(self):
        self.header_skel.start_animation()
        self.line1.start_animation()
        self.line2.start_animation()
        self.line3.start_animation()
        
    def stop_animation(self):
        self.header_skel.stop_animation()
        self.line1.stop_animation()
        self.line2.stop_animation()
        self.line3.stop_animation()

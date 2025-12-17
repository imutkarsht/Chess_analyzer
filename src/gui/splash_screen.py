from PyQt6.QtWidgets import (QSplashScreen, QProgressBar, QVBoxLayout, 
                               QWidget, QLabel, QApplication)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QColor, QFont, QScreen
from src.utils.logger import logger
from src.gui.styles import Styles
import os

class SplashScreen(QSplashScreen):
    def __init__(self, logo_path, app_name="Chess Analyzer Pro"):
        super().__init__()
        
        # Basic Setup
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Layout container
        self.container = QWidget(self)
        self.container.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                border: 1px solid #333333;
                border-radius: 10px;
            }
        """)
        self.container.setFixedSize(400, 300)
        self.setFixedSize(400, 300)
        
        # Center on screen
        screen = QApplication.primaryScreen()
        if screen:
            rect = screen.availableGeometry()
            x = (rect.width() - self.width()) // 2
            y = (rect.height() - self.height()) // 2
            self.move(rect.left() + x, rect.top() + y)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(20, 40, 20, 40)
        layout.setSpacing(20)
        
        # Logo
        if os.path.exists(logo_path):
            logo_label = QLabel()
            pixmap = QPixmap(logo_path).scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_label.setStyleSheet("background: transparent; border: none;")
            layout.addWidget(logo_label)
        
        # App Name
        title_label = QLabel(app_name)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #ffffff; background: transparent; border: none;")
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        # Loading Status
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #aaaaaa; font-size: 12px; background: transparent; border: none;")
        layout.addWidget(self.status_label)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        accent_color = Styles.COLOR_ACCENT
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                background-color: #2d2d2d;
                height: 6px;
                border-radius: 3px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {accent_color};
                border-radius: 3px;
            }}
        """)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
    def update_progress(self, value, message=None):
        self.progress_bar.setValue(value)
        if message:
            self.status_label.setText(message)
        QApplication.processEvents()

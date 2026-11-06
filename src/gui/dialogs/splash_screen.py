import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication, QProgressBar, QSplashScreen, QVBoxLayout, QWidget

from src.gui.components import IconLabel, Label, TextRole, TextTone
from src.gui.styles import Styles
from src.gui.theme import ThemeManager


class SplashScreen(QSplashScreen):
    def __init__(self, logo_path, app_name="Chess Analyzer Pro"):
        super().__init__()

        # Basic Setup
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Layout container
        p = ThemeManager.palette()
        self.container = QWidget(self)
        self.container.setObjectName("SplashContainer")
        self.container.setStyleSheet(f"""
            QWidget#SplashContainer {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 10px;
            }}
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
            layout.addWidget(
                IconLabel(QPixmap(logo_path), size=100),
                0,
                Qt.AlignmentFlag.AlignCenter,
            )

        # App Name
        title_label = Label(app_name, role=TextRole.SUBHEADING, weight=700)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        layout.addStretch()

        # Loading Status
        self.status_label = Label(
            "Initializing...",
            role=TextRole.CAPTION,
            tone=TextTone.MUTED,
        )
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Progress Bar
        self.progress_bar = QProgressBar()
        accent_color = Styles.COLOR_ACCENT
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                background-color: {p.border};
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


from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QApplication
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QIcon
from .styles import Styles
from ..utils.path_utils import get_resource_path
import os

class Sidebar(QWidget):
    # Signals for navigation
    page_changed = pyqtSignal(int) # 0: Analyze, 1: History, 2: Settings

    def __init__(self):
        super().__init__()
        self.setFixedWidth(200) # Increased width for text
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 20, 10, 20)
        self.layout.setSpacing(10)
        
        # # Logo or Title Area
        # title = QLabel("Chess Analyzer")
        # title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; padding-bottom: 20px; padding-left: 5px;")
        # self.layout.addWidget(title)
        
        # Navigation Buttons
        self.btn_analyze = self.create_button("Analyze", "analyze.png", 0)
        self.btn_history = self.create_button("History", "history.png", 1)
        self.btn_stats = self.create_button("Stats", "stats.png", 2)
        self.btn_settings = self.create_button("Settings", "settings.png", 3)
        
        self.layout.addWidget(self.btn_analyze)
        self.layout.addWidget(self.btn_history)
        self.layout.addWidget(self.btn_stats)
        self.layout.addWidget(self.btn_settings)
        
        self.layout.addStretch()
        
        # Exit Button
        self.btn_exit = self.create_button("Exit", "exit.png", -1)
        self.btn_exit.clicked.connect(QApplication.instance().quit)
        self.layout.addWidget(self.btn_exit)
        
        # Style
        self.setStyleSheet(Styles.get_sidebar_style())
        
        # Set initial active
        self.set_active(0)

    def create_button(self, text, icon_name, index):
        btn = QPushButton(f"  {text}") # Add text with spacing
        btn.setFixedHeight(50)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Load icon
        icon_path = get_resource_path(os.path.join("assets", "icons", icon_name))
        if os.path.exists(icon_path):
            btn.setIcon(QIcon(icon_path))
            btn.setIconSize(QSize(24, 24))
            
        btn.setCheckable(True)
        
        if index >= 0:
            btn.clicked.connect(lambda: self.handle_click(index))
            
        return btn

    def handle_click(self, index):
        self.set_active(index)
        self.page_changed.emit(index)

    def set_active(self, index):
        self.btn_analyze.setChecked(index == 0)
        self.btn_history.setChecked(index == 1)
        self.btn_stats.setChecked(index == 2)
        self.btn_settings.setChecked(index == 3)

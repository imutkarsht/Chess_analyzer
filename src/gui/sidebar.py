from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QApplication
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QIcon
from .styles import Styles
from ..utils.path_utils import get_resource_path
import os

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False

# Map icon names to qtawesome icons
QTAWESOME_ICONS = {
    "help.png": "fa5s.question-circle",
    "exit.png": "fa5s.sign-out-alt",
    "analyze.png": "fa5s.chess-board",
    "history.png": "fa5s.history",
    "stats.png": "fa5s.chart-bar",
    "settings.png": "fa5s.cog",
    "build_position.png": "fa5s.th-large",
}

class Sidebar(QWidget):
    # Signals for navigation
    page_changed = pyqtSignal(int) # 0: Analyze, 1: History, 2: Settings
    # Emitted when the user clicks the Build Position sidebar entry.
    # The MainWindow connects this to the position-editor dialog.
    build_position_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFixedWidth(200) # Increased width for text

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 20, 10, 20)
        self.layout.setSpacing(10)

        # Navigation Buttons
        self.btn_analyze = self.create_button("Analyze", "analyze.png", 0)

        # Build Position lives under Analyze in the sidebar so it stays
        # close to the Analyze action but doesn't take up space in the
        # top toolbar. The button is not checkable and does not drive
        # page navigation; clicking it just fires the
        # ``build_position_requested`` signal. Visually it's a regular
        # sidebar button (same height, padding, hover style) wrapped in
        # a left-indented container so the grouping under "Analyze"
        # reads clearly without us having to override the global
        # sidebar stylesheet.
        self.btn_build_position = self.create_button(
            "Build Position", "build_position.png", -1
        )
        self.btn_build_position.setCheckable(True)
        self.btn_build_position.clicked.connect(self.build_position_requested.emit)
        self.layout.addWidget(self.btn_analyze)
        self.layout.addWidget(self.btn_build_position)
        self.btn_history = self.create_button("History", "history.png", 1)
        self.btn_stats = self.create_button("Stats", "stats.png", 2)
        self.btn_settings = self.create_button("Settings", "settings.png", 3)

        self.layout.addWidget(self.btn_history)
        self.layout.addWidget(self.btn_stats)
        self.layout.addWidget(self.btn_settings)
        
        self.layout.addStretch()
        
        # Help Button (for keyboard shortcuts)
        self.btn_help = self.create_button("Help (F1)", "help.png", -1)
        self.btn_help.clicked.connect(self.show_help)
        self.layout.addWidget(self.btn_help)
        
        # Exit Button
        self.btn_exit = self.create_button("Exit", "exit.png", -1)
        self.btn_exit.clicked.connect(QApplication.instance().quit)
        self.layout.addWidget(self.btn_exit)
        
        # Style
        self.setStyleSheet(Styles.get_sidebar_style())
        
        # Set initial active
        self.set_active(0)

    def _wrap_indented(self, button, indent=20):
        """Return a container that places ``button`` with a left indent.

        Used for sub-entries (e.g. "Build Position" under "Analyze") so
        the visual nesting is expressed via layout margins rather than
        a custom stylesheet — the global sidebar style still applies
        to the button inside.

        The button gets stretch=1 so its ``:checked`` / ``:hover``
        background fills the full available width (minus the indent),
        matching the visual weight of the main navigation buttons.
        """
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(indent, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(button, 1)
        return wrap

    def create_button(self, text, icon_name, index):
        btn = QPushButton(f"  {text}")
        btn.setFixedHeight(54)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        icon_path = get_resource_path(os.path.join("assets", "icons", icon_name))
        if os.path.exists(icon_path):
            btn.setIcon(QIcon(icon_path))
            btn.setIconSize(QSize(28, 28))
        elif HAS_QTAWESOME and icon_name in QTAWESOME_ICONS:
            # Fallback to qtawesome
            btn.setIcon(qta.icon(QTAWESOME_ICONS[icon_name], color=Styles.COLOR_TEXT_SECONDARY))
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
        self.btn_build_position.setChecked(False)

    def set_build_position_active(self, active: bool):
        """Highlight / un-highlight the Build Position sidebar entry.

        Call with ``True`` when the position-editor view is shown,
        ``False`` when the user leaves it (via Back / Use Position).
        """
        self.btn_build_position.setChecked(active)
        if active:
            # Uncheck all main navigation buttons so only one
            # sidebar entry appears selected at a time.
            self.btn_analyze.setChecked(False)
            self.btn_history.setChecked(False)
            self.btn_stats.setChecked(False)
            self.btn_settings.setChecked(False)
    
    def show_help(self):
        """Show the keyboard shortcuts help dialog."""
        from .dialogs import ShortcutHelpDialog
        dialog = ShortcutHelpDialog(self)
        dialog.exec()

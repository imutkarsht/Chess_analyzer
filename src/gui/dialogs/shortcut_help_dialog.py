"""
Keyboard Shortcuts Help Dialog for Chess Analyzer Pro.
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QScrollArea, QWidget)
from PyQt6.QtCore import Qt
from ..styles import Styles

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False


class ShortcutHelpDialog(QDialog):
    """Dialog showing all available keyboard shortcuts."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumSize(480, 420)
        self.setMaximumSize(560, 550)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Styles.COLOR_BACKGROUND};
            }}
        """)
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # Header with icon
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        if HAS_QTAWESOME:
            icon_label = QLabel()
            icon_label.setPixmap(qta.icon('fa5s.keyboard', color=Styles.COLOR_ACCENT).pixmap(28, 28))
            header_layout.addWidget(icon_label)
        
        title = QLabel("Keyboard Shortcuts")
        title.setStyleSheet(f"""
            font-size: 20px;
            font-weight: bold;
            color: {Styles.COLOR_TEXT_PRIMARY};
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Subtitle
        subtitle = QLabel("Master these shortcuts to analyze games faster")
        subtitle.setStyleSheet(f"""
            font-size: 12px;
            color: {Styles.COLOR_TEXT_SECONDARY};
            margin-bottom: 8px;
        """)
        layout.addWidget(subtitle)
        
        # Scroll Area for shortcuts
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND}; border: none;")
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Shortcuts grouped by category
        shortcuts = {
            "Navigation": [
                ("←  →", "Previous / Next move"),
                ("Home", "First move"),
                ("End", "Last move"),
            ],
            "Board": [
                ("F", "Flip board"),
            ],
            "Actions": [
                ("Ctrl+O", "Open PGN file"),
                ("Ctrl+A", "Analyze game"),
            ],
            "General": [
                ("F1", "Show this help"),
                ("Esc", "Close dialogs"),
            ],
        }
        
        for category, items in shortcuts.items():
            # Category Header
            cat_layout = QHBoxLayout()
            cat_layout.setSpacing(8)
            
            if HAS_QTAWESOME:
                cat_icons = {
                    "Navigation": "fa5s.arrows-alt",
                    "Board": "fa5s.chess-board", 
                    "Actions": "fa5s.bolt",
                    "General": "fa5s.cog"
                }
                cat_icon = QLabel()
                cat_icon.setPixmap(qta.icon(cat_icons.get(category, "fa5s.circle"), color=Styles.COLOR_ACCENT).pixmap(14, 14))
                cat_layout.addWidget(cat_icon)
            
            category_label = QLabel(category)
            category_label.setStyleSheet(f"""
                font-size: 13px;
                font-weight: 600;
                color: {Styles.COLOR_ACCENT};
            """)
            cat_layout.addWidget(category_label)
            cat_layout.addStretch()
            
            content_layout.addLayout(cat_layout)
            
            # Shortcut items
            for key, description in items:
                row = self._create_shortcut_row(key, description)
                content_layout.addWidget(row)
            
            # Add spacing between categories
            spacer = QWidget()
            spacer.setFixedHeight(4)
            content_layout.addWidget(spacer)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # Close button
        btn_close = QPushButton("Got it")
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_ACCENT};
                color: white;
                border: none;
                padding: 10px 28px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_ACCENT_HOVER};
            }}
        """)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
    
    def _create_shortcut_row(self, key, description):
        """Create a row with key badge and description."""
        row = QFrame()
        row.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_SURFACE};
                border-radius: 6px;
            }}
        """)
        
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 8, 12, 8)
        
        # Key badge
        key_label = QLabel(key)
        key_label.setStyleSheet(f"""
            background-color: {Styles.COLOR_SURFACE_LIGHT};
            color: {Styles.COLOR_TEXT_PRIMARY};
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            border: 1px solid {Styles.COLOR_BORDER};
        """)
        key_label.setMinimumWidth(80)
        key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row_layout.addWidget(key_label)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 12px;
            padding-left: 8px;
        """)
        row_layout.addWidget(desc_label)
        row_layout.addStretch()
        
        return row

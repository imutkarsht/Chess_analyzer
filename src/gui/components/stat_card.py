"""
Shared StatCard component for dashboard widgets.
"""
import os
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from ..styles import Styles
from ..gui_utils import resolve_asset  # Use shared utility


class StatCard(QFrame):
    """
    A reusable stat card for dashboards, showing title, value, optional subtitle and icon.
    
    Args:
        title: Header text for the card
        value: Main display value
        subtitle: Optional secondary text below the value
        icon: Optional icon name (without extension) to display
        color: Optional color for the value text
    """
    
    def __init__(self, title, value, subtitle=None, icon=None, color=None):
        super().__init__()
        
        self.setStyleSheet(Styles.get_card_style())
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        # Header (Title + Icon)
        header_layout = QHBoxLayout()
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 14px; font-weight: 600; {Styles.get_transparent_label_style()}")
        header_layout.addWidget(lbl_title)
        
        if icon:
            self._add_icon(header_layout, icon)
        else:
            header_layout.addStretch()
            
        layout.addLayout(header_layout)
        
        # Value
        lbl_value = QLabel(str(value))
        value_color = color if color else Styles.COLOR_TEXT_PRIMARY
        lbl_value.setStyleSheet(f"color: {value_color}; font-size: 36px; font-weight: bold; {Styles.get_transparent_label_style()}")
        layout.addWidget(lbl_value)
        
        # Subtitle
        if subtitle:
            lbl_sub = QLabel(subtitle)
            lbl_sub.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; {Styles.get_transparent_label_style()}")
            lbl_sub.setWordWrap(True)
            layout.addWidget(lbl_sub)
    
    def _add_icon(self, layout, icon):
        """Add icon to the header layout."""
        # Try to find icon file
        if not icon.endswith(('.png', '.svg')):
            icon_path = resolve_asset(f"{icon}.svg")
            if not icon_path:
                icon_path = resolve_asset(f"{icon}.png")
        else:
            icon_path = resolve_asset(icon)
        
        layout.addStretch()
        
        if icon_path and os.path.exists(icon_path):
            lbl_icon = QLabel()
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, 
                                       Qt.TransformationMode.SmoothTransformation)
                lbl_icon.setPixmap(pixmap)
                lbl_icon.setStyleSheet(Styles.get_transparent_label_style())
                layout.addWidget(lbl_icon)
                return
        
        # Fallback: show icon name as text
        lbl = QLabel(icon)
        lbl.setStyleSheet(f"color: {Styles.COLOR_ACCENT}; font-size: 16px; {Styles.get_transparent_label_style()}")
        layout.addWidget(lbl)


class SimpleStatCard(QFrame):
    """
    A simpler stat card variant for compact displays (e.g., analysis report).
    
    Args:
        title: Header text
        value: Display value
        color: Optional value color
    """
    
    def __init__(self, title, value, color=None):
        super().__init__()
        
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 10px;
            }}
            QLabel {{ border: none; background: transparent; }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        lbl_value = QLabel(str(value))
        lbl_value.setStyleSheet(f"color: {color if color else Styles.COLOR_TEXT_PRIMARY}; font-size: 18px; font-weight: bold;")
        lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_value)

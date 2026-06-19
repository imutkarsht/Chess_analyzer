"""
Shared StatCard component for dashboard widgets.
"""
import os
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from src.gui.styles import Styles
from src.gui.utils.gui_utils import resolve_asset  # Use shared utility


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
        
        # Cache properties for dynamic style refresh
        self._initial_color = color
        self._use_accent_color = (color == Styles.COLOR_ACCENT)
        
        # Modern card styling with subtle gradient
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 12px;
            }}
            QFrame:hover {{
                border: 1px solid {Styles.COLOR_ACCENT};
                background-color: {Styles.COLOR_SURFACE_LIGHT};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)
        
        # Header (Title + Icon)
        header_layout = QHBoxLayout()
        
        self.lbl_title = QLabel(title)
        # Uppercase title with letter-spacing for modern look
        self.lbl_title.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY}; 
            font-size: 12px; 
            font-weight: 600; 
            letter-spacing: 0.5px;
            text-transform: uppercase;
            border: none; 
            background: transparent;
        """)
        header_layout.addWidget(self.lbl_title)
        
        if icon:
            self._add_icon(header_layout, icon)
        else:
            header_layout.addStretch()
            
        layout.addLayout(header_layout)
        layout.addSpacing(4)
        
        # Value - Large, bold, eye-catching
        self.lbl_value = QLabel(str(value))
        value_color = color if color else Styles.COLOR_TEXT_PRIMARY
        self.lbl_value.setStyleSheet(f"""
            color: {value_color}; 
            font-size: 42px; 
            font-weight: 700; 
            letter-spacing: -1px;
            border: none; 
            background: transparent;
        """)
        layout.addWidget(self.lbl_value)
        
        # Subtitle - Subtle, smaller
        self.lbl_sub = None
        if subtitle:
            self.lbl_sub = QLabel(subtitle)
            self.lbl_sub.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_MUTED}; 
                font-size: 12px; 
                font-weight: 400;
                border: none; 
                background: transparent;
            """)
            self.lbl_sub.setWordWrap(True)
            layout.addWidget(self.lbl_sub)
            
    def refresh_styles(self):
        """Re-apply styles with the updated accent color."""
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 12px;
            }}
            QFrame:hover {{
                border: 1px solid {Styles.COLOR_ACCENT};
                background-color: {Styles.COLOR_SURFACE_LIGHT};
            }}
        """)
        
        self.lbl_title.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY}; 
            font-size: 12px; 
            font-weight: 600; 
            letter-spacing: 0.5px;
            text-transform: uppercase;
            border: none; 
            background: transparent;
        """)
        
        value_color = Styles.COLOR_ACCENT if self._use_accent_color else (self._initial_color if self._initial_color else Styles.COLOR_TEXT_PRIMARY)
        self.lbl_value.setStyleSheet(f"""
            color: {value_color}; 
            font-size: 42px; 
            font-weight: 700; 
            letter-spacing: -1px;
            border: none; 
            background: transparent;
        """)
        
        if self.lbl_sub:
            self.lbl_sub.setStyleSheet(f"""
                color: {Styles.COLOR_TEXT_MUTED}; 
                font-size: 12px; 
                font-weight: 400;
                border: none; 
                background: transparent;
            """)
    
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
        
        self._initial_color = color
        self._use_accent_color = (color == Styles.COLOR_ACCENT)
        
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
        
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px;")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_value = QLabel(str(value))
        value_color = Styles.COLOR_ACCENT if self._use_accent_color else (color if color else Styles.COLOR_TEXT_PRIMARY)
        self.lbl_value.setStyleSheet(f"color: {value_color}; font-size: 18px; font-weight: bold;")
        self.lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_value)

    def refresh_styles(self):
        """Re-apply styles with the updated accent color."""
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 10px;
            }}
            QLabel {{ border: none; background: transparent; }}
        """)
        self.lbl_title.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px;")
        value_color = Styles.COLOR_ACCENT if self._use_accent_color else (self._initial_color if self._initial_color else Styles.COLOR_TEXT_PRIMARY)
        self.lbl_value.setStyleSheet(f"color: {value_color}; font-size: 18px; font-weight: bold;")


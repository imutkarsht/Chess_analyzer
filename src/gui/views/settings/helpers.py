"""
Helper utilities for the settings view modules.
"""
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt
from ...styles import Styles

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False

def create_icon_button(text, icon_name, callback, parent=None, danger=False, primary=False):
    """Create a styled button with qtawesome icon."""
    btn = QPushButton(f"  {text}", parent)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    
    if HAS_QTAWESOME:
        if danger:
            icon_color = Styles.COLOR_BLUNDER
        elif primary:
            icon_color = "#ffffff"
        else:
            icon_color = Styles.COLOR_TEXT_SECONDARY
        btn.setIcon(qta.icon(icon_name, color=icon_color))
    
    if danger:
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_BACKGROUND};
                color: {Styles.COLOR_BLUNDER};
                border: 1px solid {Styles.COLOR_BLUNDER};
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_BLUNDER};
                color: white;
            }}
        """)
    elif primary:
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_ACCENT};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_ACCENT_HOVER};
            }}
        """)
    else:
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_SURFACE};
                border-color: {Styles.COLOR_ACCENT};
            }}
        """)
    
    btn.clicked.connect(callback)
    return btn

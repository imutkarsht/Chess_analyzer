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
        btn.setStyleSheet(Styles.get_settings_danger_button_style())
    elif primary:
        btn.setStyleSheet(Styles.get_button_style())
    else:
        btn.setStyleSheet(Styles.get_settings_default_button_style())
    
    btn.clicked.connect(callback)
    return btn

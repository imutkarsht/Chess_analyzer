"""
Shared GUI utility functions and widget factories.
"""
import os
from typing import Callable, Optional, List
from PyQt6.QtWidgets import (QLayout, QPushButton, QComboBox, QLineEdit, 
                             QLabel, QWidget, QHBoxLayout, QVBoxLayout)
from PyQt6.QtCore import Qt
from ..utils.path_utils import get_resource_path


def clear_layout(layout: QLayout) -> None:
    """
    Removes all widgets and sub-layouts from a QLayout.
    
    Args:
        layout: The QLayout to clear
    """
    if layout is None:
        return
        
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()
        elif item.layout():
            clear_layout(item.layout())


def resolve_asset(filename: str) -> str:
    """
    Robustly find assets using the project's standard resource resolver.
    
    Args:
        filename: Asset filename (with or without extension)
        
    Returns:
        Absolute path to asset, or None if not found
    """
    candidates = [
        os.path.join("assets", "images", filename),
        os.path.join("assets", "icons", filename),
        os.path.join("assets", filename)
    ]
    
    for rel_path in candidates:
        full_path = get_resource_path(rel_path)
        if os.path.exists(full_path):
            return full_path
    return None


def get_user_color(game: dict, usernames: list) -> str:
    """
    Determines the user's color in a game based on configured usernames.
    
    Args:
        game: Game dictionary with 'white' and 'black' keys
        usernames: List of usernames to check against
        
    Returns:
        'white' or 'black' depending on which player matches usernames
    """
    white = game.get('white', '').lower()
    if white in [u.lower() for u in usernames]:
        return 'white'
    return 'black'


# ============== Widget Factory Functions ==============

def create_button(
    text: str, 
    style: str = "primary",
    on_click: Optional[Callable] = None,
    cursor: bool = True
) -> QPushButton:
    """
    Factory function to create styled buttons.
    
    Args:
        text: Button text
        style: Style type - "primary", "secondary", "export", "import"
        on_click: Click handler callback
        cursor: Whether to show pointer cursor on hover
        
    Returns:
        Configured QPushButton
    """
    from .styles import Styles  # Import here to avoid circular imports
    
    btn = QPushButton(text)
    
    style_map = {
        "primary": Styles.get_button_style,
        "secondary": Styles.get_control_button_style,
        "export": Styles.get_export_button_style,
        "import": Styles.get_import_button_style,
    }
    
    style_func = style_map.get(style, Styles.get_button_style)
    btn.setStyleSheet(style_func())
    
    if cursor:
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
    
    if on_click:
        btn.clicked.connect(on_click)
    
    return btn


def create_combobox(
    items: List[str],
    current: Optional[str] = None,
    on_change: Optional[Callable] = None
) -> QComboBox:
    """
    Factory function to create styled comboboxes.
    
    Args:
        items: List of items to add
        current: Currently selected item
        on_change: Callback for selection changes
        
    Returns:
        Configured QComboBox
    """
    from .styles import Styles
    
    combo = QComboBox()
    combo.addItems(items)
    combo.setStyleSheet(Styles.get_combobox_style())
    
    if current:
        combo.setCurrentText(current)
    
    if on_change:
        combo.currentTextChanged.connect(on_change)
    
    return combo


def create_labeled_input(
    label_text: str,
    placeholder: str = "",
    password: bool = False,
    initial_value: str = ""
) -> tuple:
    """
    Factory function to create a labeled input field.
    
    Args:
        label_text: Text for the label
        placeholder: Placeholder text for input
        password: Whether to mask input
        initial_value: Initial value for the input
        
    Returns:
        Tuple of (QLabel, QLineEdit)
    """
    from .styles import Styles
    
    label = QLabel(label_text)
    label.setStyleSheet(Styles.get_secondary_label_style())
    
    input_field = QLineEdit()
    input_field.setStyleSheet(Styles.get_input_style())
    input_field.setPlaceholderText(placeholder)
    
    if password:
        input_field.setEchoMode(QLineEdit.EchoMode.Password)
    
    if initial_value:
        input_field.setText(initial_value)
    
    return label, input_field


def create_section_header(
    title: str,
    action_button: Optional[tuple] = None
) -> QWidget:
    """
    Factory function to create a section header with optional action button.
    
    Args:
        title: Header title text
        action_button: Optional tuple of (button_text, callback, style)
        
    Returns:
        QWidget containing the header layout
    """
    from .styles import Styles
    
    header = QWidget()
    layout = QHBoxLayout(header)
    layout.setContentsMargins(0, 0, 0, 0)
    
    title_label = QLabel(title)
    title_label.setStyleSheet(Styles.get_label_style(size=18, bold=True))
    layout.addWidget(title_label)
    
    layout.addStretch()
    
    if action_button:
        btn_text, callback, btn_style = action_button
        btn = create_button(btn_text, style=btn_style or "secondary", on_click=callback)
        layout.addWidget(btn)
    
    return header

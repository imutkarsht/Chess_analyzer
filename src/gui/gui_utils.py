"""
Shared GUI utility functions.
"""
import os
from PyQt6.QtWidgets import QLayout
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
    Checks:
    1. assets/images/ (SVGs)
    2. assets/icons/ (PNGs)
    3. assets/ (Root)
    
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

"""
Dialogs package - Dialog windows.
"""
from .game_selection_dialog import GameSelectionDialog
from .splash_screen import SplashScreen
from .shortcut_help_dialog import ShortcutHelpDialog
from .update_dialog import UpdateNotificationDialog
from .load_game_dialog import LoadGameDialog, SRC_PGN_FILE, SRC_PGN_TEXT, SRC_CHESSCOM, SRC_LICHESS
from .setup_wizard import SetupWizard

__all__ = [
    'GameSelectionDialog', 'SplashScreen', 'ShortcutHelpDialog',
    'UpdateNotificationDialog', 'LoadGameDialog', 'SetupWizard',
    'SRC_PGN_FILE', 'SRC_PGN_TEXT', 'SRC_CHESSCOM', 'SRC_LICHESS',
]

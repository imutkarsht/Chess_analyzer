"""
Dialogs package - Dialog windows.
"""
from .feedback_dialog import FeedbackDialog
from .game_selection_dialog import GameSelectionDialog
from .load_game_dialog import SRC_CHESSCOM, SRC_LICHESS, SRC_PGN_FILE, SRC_PGN_TEXT, LoadGameDialog
from .review_prompt_dialog import ReviewPromptDialog
from .setup_wizard import SetupWizard
from .shortcut_help_dialog import ShortcutHelpDialog
from .splash_screen import SplashScreen
from .update_dialog import UpdateNotificationDialog

__all__ = [
    'GameSelectionDialog', 'SplashScreen', 'ShortcutHelpDialog',
    'UpdateNotificationDialog', 'LoadGameDialog', 'SetupWizard',
    'ReviewPromptDialog', 'FeedbackDialog',
    'SRC_PGN_FILE', 'SRC_PGN_TEXT', 'SRC_CHESSCOM', 'SRC_LICHESS',
]

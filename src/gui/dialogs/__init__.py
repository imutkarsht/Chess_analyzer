"""
Dialogs package - Dialog windows.
"""
from src.gui.dialogs.feedback_dialog import FeedbackDialog
from src.gui.dialogs.game_selection_dialog import GameSelectionDialog
from src.gui.dialogs.load_game_dialog import (
    SRC_CHESSCOM,
    SRC_LICHESS,
    SRC_PGN_FILE,
    SRC_PGN_TEXT,
    LoadGameDialog,
)
from src.gui.dialogs.review_prompt_dialog import ReviewPromptDialog
from src.gui.dialogs.setup_wizard import SetupWizard
from src.gui.dialogs.shortcut_help_dialog import ShortcutHelpDialog
from src.gui.dialogs.splash_screen import SplashScreen
from src.gui.dialogs.update_dialog import UpdateNotificationDialog

__all__ = [
    'GameSelectionDialog', 'SplashScreen', 'ShortcutHelpDialog',
    'UpdateNotificationDialog', 'LoadGameDialog', 'SetupWizard',
    'ReviewPromptDialog', 'FeedbackDialog',
    'SRC_PGN_FILE', 'SRC_PGN_TEXT', 'SRC_CHESSCOM', 'SRC_LICHESS',
]

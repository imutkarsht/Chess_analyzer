"""
Dialogs package - Dialog windows, panels, and overlay launchers.
"""
from src.gui.dialogs.engine_error_dialog import (
    EngineNotFoundDialog,
    EngineNotFoundPanel,
    open_engine_not_found,
)
from src.gui.dialogs.feedback_dialog import (
    FeedbackDialog,
    FeedbackPanel,
    open_feedback_overlay,
)
from src.gui.dialogs.llm_error_dialog import (
    LlmNotConfiguredDialog,
    open_llm_not_configured,
)
from src.gui.dialogs.load_game_dialog import (
    SRC_CHESSCOM,
    SRC_LICHESS,
    SRC_PGN_FILE,
    SRC_PGN_TEXT,
    LoadGameDialog,
    LoadGamePanel,
    open_load_game_overlay,
)
from src.gui.dialogs.review_prompt_dialog import (
    ReviewPromptDialog,
    ReviewPromptPanel,
    open_review_prompt,
)
from src.gui.dialogs.setup_wizard import SetupWizard
from src.gui.dialogs.shortcut_help_dialog import (
    ShortcutHelpDialog,
    ShortcutHelpPanel,
    open_shortcut_help_overlay,
)
from src.gui.dialogs.splash_screen import SplashScreen
from src.gui.dialogs.update_dialog import (
    UpdateNotificationDialog,
    UpdateNotificationPanel,
    open_update_overlay,
)

__all__ = [
    'SplashScreen',
    'ShortcutHelpDialog',
    'ShortcutHelpPanel',
    'open_shortcut_help_overlay',
    'UpdateNotificationDialog',
    'UpdateNotificationPanel',
    'open_update_overlay',
    'LoadGameDialog',
    'LoadGamePanel',
    'open_load_game_overlay',
    'SetupWizard',
    'ReviewPromptDialog',
    'ReviewPromptPanel',
    'open_review_prompt',
    'FeedbackDialog',
    'FeedbackPanel',
    'open_feedback_overlay',
    'EngineNotFoundDialog',
    'EngineNotFoundPanel',
    'open_engine_not_found',
    'LlmNotConfiguredDialog',
    'open_llm_not_configured',
    'SRC_PGN_FILE',
    'SRC_PGN_TEXT',
    'SRC_CHESSCOM',
    'SRC_LICHESS',
]

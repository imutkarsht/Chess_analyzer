"""
Settings view modules.
"""
from .api_settings import ApiSettings, test_llm_sync
from .appearance_settings import AppearanceSettings
from .book_settings import BookSettings
from .coach_settings import CoachSettings
from .data_settings import DataSettings
from .engine_settings import EngineSettings
from .links_settings import LinksSettings
from .player_settings import PlayerSettings
from .shortcut_settings import ShortcutSettings

__all__ = [
    'EngineSettings',
    'BookSettings',
    'ApiSettings',
    'CoachSettings',
    'PlayerSettings',
    'ShortcutSettings',
    'AppearanceSettings',
    'DataSettings',
    'LinksSettings',
    'test_llm_sync',
]

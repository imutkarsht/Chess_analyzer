"""
Settings view modules.
"""
from .api_settings import ApiSettings, test_llm_sync
from .appearance_settings import AppearanceSettings
from .book_settings import BookSettings
from .coach_settings import CoachSettings
from .data_settings import DataSettings
from .engine_settings import EngineSettings
from .full_analysis_settings import FullAnalysisSettings
from .links_settings import LinksSettings
from .live_analysis_settings import LiveAnalysisSettings
from .player_settings import PlayerSettings
from .shortcut_settings import ShortcutSettings

__all__ = [
    'EngineSettings',
    'FullAnalysisSettings',
    'LiveAnalysisSettings',
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

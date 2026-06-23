"""
Settings view modules.
"""
from .engine_settings import EngineSettings
from .book_settings import BookSettings
from .api_settings import ApiSettings, test_llm_sync
from .player_settings import PlayerSettings
from .appearance_settings import AppearanceSettings
from .data_settings import DataSettings
from .links_settings import LinksSettings

__all__ = [
    'EngineSettings',
    'BookSettings',
    'ApiSettings',
    'PlayerSettings',
    'AppearanceSettings',
    'DataSettings',
    'LinksSettings',
    'test_llm_sync',
]

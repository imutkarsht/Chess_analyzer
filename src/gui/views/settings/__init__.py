"""
Settings view modules.
"""
from .api_settings import ApiSettings, test_llm_sync
from .board_pieces_settings import BoardPiecesSettings
from .book_settings import BookSettings
from .coach_settings import CoachSettings
from .data_settings import DataSettings
from .engine_settings import EngineSettings
from .full_analysis_settings import FullAnalysisSettings
from .links_settings import LinksSettings
from .live_analysis_settings import LiveAnalysisSettings
from .player_settings import PlayerSettings
from .shortcut_settings import ShortcutSettings
from .sound_settings import SoundSettings
from .theme_accent_settings import ThemeAccentSettings
from .window_layout_settings import WindowLayoutSettings

__all__ = [
    'EngineSettings',
    'FullAnalysisSettings',
    'LiveAnalysisSettings',
    'BookSettings',
    'ApiSettings',
    'CoachSettings',
    'PlayerSettings',
    'ShortcutSettings',
    'ThemeAccentSettings',
    'BoardPiecesSettings',
    'WindowLayoutSettings',
    'SoundSettings',
    'DataSettings',
    'LinksSettings',
    'test_llm_sync',
]

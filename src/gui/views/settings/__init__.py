"""
Settings view modules.
"""
from .api_settings import ApiSettings, test_llm_sync
from .backup_settings import BackupSettings
from .board_pieces_settings import BoardPiecesSettings
from .book_settings import BookSettings
from .coach_settings import CoachSettings
from .danger_settings import DangerSettings
from .engine_settings import EngineSettings
from .full_analysis_settings import FullAnalysisSettings
from .links_settings import LinksSettings
from .live_analysis_settings import LiveAnalysisSettings
from .maintenance_settings import MaintenanceSettings
from .player_settings import (
    ChessComCard,
    ImportNetworkCard,
    LichessCard,
    PlayerSettings,
)
from .retention_settings import RetentionSettings
from .shortcut_settings import ShortcutSettings
from .sound_settings import SoundSettings
from .storage_settings import StorageSettings
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
    'ChessComCard',
    'LichessCard',
    'ImportNetworkCard',
    'ShortcutSettings',
    'ThemeAccentSettings',
    'BoardPiecesSettings',
    'WindowLayoutSettings',
    'SoundSettings',
    'StorageSettings',
    'RetentionSettings',
    'MaintenanceSettings',
    'BackupSettings',
    'DangerSettings',
    'LinksSettings',
    'test_llm_sync',
]

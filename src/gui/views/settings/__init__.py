"""
Settings view modules.
"""
from src.gui.views.settings.api_settings import ApiSettings, test_llm_sync
from src.gui.views.settings.backup_settings import BackupSettings
from src.gui.views.settings.board_pieces_settings import BoardPiecesSettings
from src.gui.views.settings.book_settings import BookSettings
from src.gui.views.settings.coach_settings import CoachSettings
from src.gui.views.settings.danger_settings import DangerSettings
from src.gui.views.settings.dashboard_layout_settings import DashboardLayoutSettings
from src.gui.views.settings.engine_settings import EngineSettings
from src.gui.views.settings.full_analysis_settings import FullAnalysisSettings
from src.gui.views.settings.links_settings import LinksSettings
from src.gui.views.settings.live_analysis_settings import LiveAnalysisSettings
from src.gui.views.settings.maintenance_settings import MaintenanceSettings
from src.gui.views.settings.player_settings import (
    ChessComCard,
    ImportNetworkCard,
    LichessCard,
    PlayerSettings,
)
from src.gui.views.settings.retention_settings import RetentionSettings
from src.gui.views.settings.shortcut_settings import ShortcutSettings
from src.gui.views.settings.sound_settings import SoundSettings
from src.gui.views.settings.storage_settings import StorageSettings
from src.gui.views.settings.theme_accent_settings import ThemeAccentSettings
from src.gui.views.settings.window_layout_settings import WindowLayoutSettings

__all__ = [
    'EngineSettings',
    'FullAnalysisSettings',
    'LiveAnalysisSettings',
    'BookSettings',
    'ApiSettings',
    'CoachSettings',
    'DashboardLayoutSettings',
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

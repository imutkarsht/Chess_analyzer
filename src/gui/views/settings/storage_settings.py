"""Read-only storage usage and access to the local data folder."""

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ....backend.storage.stats import StorageStats, collect_storage_stats
from ....utils.path_utils import get_user_data_dir
from ...styles import Styles
from .components import SettingsForm
from .helpers import create_icon_button
from .storage_actions import format_bytes, format_count
from .storage_card import StorageCard

_STAT_ROWS = (
    ("database", "Database"),
    ("games", "Games stored"),
    ("analyses", "Cached evaluations"),
    ("explanations", "Cached explanations"),
    ("api_cache", "API cache"),
    ("explorer_cache", "Explorer cache"),
    ("openings", "Opening index"),
)


class StorageSettings(StorageCard):
    """Shows what is stored locally and opens the data folder."""

    def __init__(self, parent=None):
        super().__init__("Storage", parent)
        self.stat_labels: dict[str, QLabel] = {}
        self.setup_ui()

    def setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)

        self.form = SettingsForm(self)
        outer.addWidget(self.form)

        for key, label in _STAT_ROWS:
            value = QLabel("—")
            value.setStyleSheet(
                Styles.get_label_style(size=13) + Styles.get_transparent_label_style()
            )
            self.stat_labels[key] = value
            self.form.add_row(label, value, hint="", width=None)

        self.refresh_btn = create_icon_button(
            "Refresh", "fa5s.sync-alt", self.refresh_stats, self
        )
        self.open_folder_btn = create_icon_button(
            "Open Data Folder", "fa5s.folder-open", self.open_data_folder, self
        )
        for btn in (self.refresh_btn, self.open_folder_btn):
            btn.setMaximumWidth(180)

        folder_row = QWidget()
        folder_row.setStyleSheet(Styles.get_transparent_label_style())
        row = QHBoxLayout(folder_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(self.refresh_btn)
        row.addWidget(self.open_folder_btn)
        row.addStretch(1)
        self.form.add_row(
            "Folder",
            folder_row,
            hint="Database, logs, settings, and custom piece themes.",
            width=None,
        )

        self.register_busy_widgets(self.refresh_btn)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def refresh_stats(self) -> None:
        """Re-read sizes and row counts without blocking the UI."""
        self.run_task(collect_storage_stats, self.apply_stats)

    def apply_stats(self, stats: StorageStats) -> None:
        self.stat_labels["database"].setText(
            format_bytes(stats.db_bytes + stats.wal_bytes)
        )
        self.stat_labels["games"].setText(format_count(stats.games))
        self.stat_labels["analyses"].setText(format_count(stats.analyses))
        self.stat_labels["explanations"].setText(format_count(stats.explanations))
        self.stat_labels["api_cache"].setText(
            f"{format_count(stats.api_cached_games)} games"
        )
        self.stat_labels["explorer_cache"].setText(
            f"{format_count(stats.explorer_positions)} positions"
        )
        self.stat_labels["openings"].setText(format_bytes(stats.openings_bytes))

    def open_data_folder(self) -> None:
        folder = get_user_data_dir()
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    # ------------------------------------------------------------------
    # Lifecycle hooks used by SettingsView
    # ------------------------------------------------------------------
    def set_advanced_visible(self, visible: bool) -> None:
        # Storage usage matters in both modes.
        self.setVisible(True)

    def refresh_styles(self, *args, **kwargs) -> None:
        self.setStyleSheet(Styles.get_group_box_style())
        self.form.refresh_styles()
        for label in self.stat_labels.values():
            label.setStyleSheet(
                Styles.get_label_style(size=13) + Styles.get_transparent_label_style()
            )
        self.refresh_btn.setStyleSheet(Styles.get_settings_default_button_style())
        self.open_folder_btn.setStyleSheet(Styles.get_settings_default_button_style())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh_stats()

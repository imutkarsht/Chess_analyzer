"""Manual database backup and restore."""

import time

from PyQt6.QtWidgets import QFileDialog, QVBoxLayout

from ....backend.storage.backup import (
    BackupError,
    BackupSummary,
    create_backup,
    default_backup_path,
    inspect_backup,
    restore_backup,
)
from ...styles import Styles
from ...utils.gui_utils import confirm_dialog
from .components import SettingsForm
from .helpers import create_icon_button
from .storage_actions import (
    close_analyzer_cache,
    ensure_idle,
    format_bytes,
    refresh_after_data_change,
)
from .storage_card import StorageCard


class BackupSettings(StorageCard):
    """Write a consistent snapshot of the local database, or restore one."""

    def __init__(self, parent=None):
        super().__init__("Backup && Restore", parent)
        self.setup_ui()

    def setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)

        self.form = SettingsForm(self)
        outer.addWidget(self.form)

        self.backup_btn = create_icon_button(
            "Back Up Now...", "fa5s.save", self.backup_now, self
        )
        self.form.add_row(
            "Backup",
            self.backup_btn,
            hint="Save a copy of your games, analyses, and caches.",
            width=None,
        )

        self.restore_btn = create_icon_button(
            "Restore From Backup...", "fa5s.upload", self.restore_from_backup, self, danger=True
        )
        self.form.add_row(
            "Restore",
            self.restore_btn,
            hint=(
                "Replace local data with a backup file. A safety copy of the "
                "current database is saved first."
            ),
            width=None,
        )

        for btn in (self.backup_btn, self.restore_btn):
            btn.setMaximumWidth(220)
        self.register_busy_widgets(self.backup_btn, self.restore_btn)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def backup_now(self) -> None:
        if not ensure_idle(self.window()):
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Back Up Data",
            default_backup_path(),
            "SQLite Database (*.db);;All Files (*)",
        )
        if not path:
            return
        self.run_task(lambda: create_backup(path), self._on_backup_done)

    def _on_backup_done(self, summary: BackupSummary) -> None:
        self._toast(
            f"Backup saved: {format_bytes(summary.size_bytes)}, "
            f"{summary.games:,} games."
        )

    def restore_from_backup(self) -> None:
        if not ensure_idle(self.window()):
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Restore From Backup",
            "",
            "Chess Analyzer backup (*.db *.sqlite *.sqlite3);;All Files (*)",
        )
        if not path:
            return

        # Validation is read-only and fast enough to keep inline, so the
        # confirmation dialog can show exactly what will be restored.
        try:
            summary = inspect_backup(path)
        except BackupError as e:
            self._report_error(str(e))
            return

        created = time.strftime("%Y-%m-%d %H:%M", time.localtime(summary.created_at))
        message = (
            "Replace all local data with this backup?\n\n"
            f"{summary.games:,} games, {summary.analyses:,} cached evaluations, "
            f"{summary.explanations:,} explanations\nCreated {created}\n\n"
            "A safety copy of the current database is saved first."
        )
        if not confirm_dialog(
            self, "Restore Backup", message, confirm_label="Restore"
        ):
            return

        close_analyzer_cache(self.window())
        self.run_task(lambda: restore_backup(path), self._on_restored)

    def _on_restored(self, summary: BackupSummary) -> None:
        refresh_after_data_change(self.window())
        self.data_changed.emit()
        self._toast(f"Restored {summary.games:,} games from backup.")

    def _toast(self, message: str) -> None:
        from src.gui.main_window import MainWindow

        MainWindow.toast_from_widget(self, message, "success")

    # ------------------------------------------------------------------
    # Lifecycle hooks used by SettingsView
    # ------------------------------------------------------------------
    def set_advanced_visible(self, visible: bool) -> None:
        self.setVisible(True)

    def refresh_styles(self, *args, **kwargs) -> None:
        self.setStyleSheet(Styles.get_group_box_style())
        self.form.refresh_styles()
        self.backup_btn.setStyleSheet(Styles.get_settings_default_button_style())
        self.restore_btn.setStyleSheet(Styles.get_settings_danger_button_style())

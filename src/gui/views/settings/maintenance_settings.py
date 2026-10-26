"""Cache clearing and database maintenance actions."""

import os

from PyQt6.QtWidgets import QVBoxLayout

from ....backend.storage.cache import AnalysisCache
from ....backend.storage.game_history import GameHistoryManager
from ....utils.logger import logger
from ....utils.path_utils import get_resource_path, get_user_data_dir
from ...styles import Styles
from ...utils.gui_utils import confirm_dialog
from .components import SettingsForm
from .helpers import create_icon_button
from .storage_actions import close_analyzer_cache, ensure_idle
from .storage_card import StorageCard


def rebuild_opening_index() -> str:
    """Delete and regenerate the derived opening index from bundled data."""
    from ....backend.analysis.opening_db import OpeningDB

    db_path = os.path.join(get_user_data_dir(), "openings.db")
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(db_path + suffix)
        except FileNotFoundError:
            continue

    opening_db = OpeningDB(db_path)
    try:
        opening_db.connect()
        opening_db.initialize(get_resource_path("assets/openings"))
    finally:
        opening_db.close()
    return db_path


class MaintenanceSettings(StorageCard):
    """Reclaim space from the caches and the history database."""

    def __init__(self, parent=None):
        super().__init__("Maintenance", parent)
        self.setup_ui()

    def setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)

        self.form = SettingsForm(self)
        outer.addWidget(self.form)

        self.clear_cache_btn = create_icon_button(
            "Clear Cache", "fa5s.broom", self.clear_cache, self
        )
        self.form.add_row(
            "Analysis cache",
            self.clear_cache_btn,
            hint="Remove cached engine evaluations.",
            width=None,
        )

        self.clear_explanations_btn = create_icon_button(
            "Clear Explanations", "fa5s.comment-slash", self.clear_explanations, self
        )
        self.form.add_row(
            "Explanation cache",
            self.clear_explanations_btn,
            hint="Remove cached AI Coach move explanations.",
            width=None,
        )

        self.clear_api_cache_btn = create_icon_button(
            "Clear API Cache", "fa5s.cloud-download-alt", self.clear_api_cache, self
        )
        self.form.add_row(
            "API cache",
            self.clear_api_cache_btn,
            hint="Remove cached Chess.com and Lichess game lists.",
            width=None,
        )

        self.clear_explorer_cache_btn = create_icon_button(
            "Clear Explorer Cache", "fa5s.globe", self.clear_explorer_cache, self
        )
        self.form.add_row(
            "Explorer cache",
            self.clear_explorer_cache_btn,
            hint="Remove cached opening-explorer responses.",
            width=None,
        )

        self.optimize_db_btn = create_icon_button(
            "Optimize DB", "fa5s.tools", self.optimize_db, self
        )
        self.form.add_row(
            "Database",
            self.optimize_db_btn,
            hint="Compact the history database and checkpoint WAL files.",
            width=None,
        )

        self.rebuild_index_btn = create_icon_button(
            "Rebuild Index", "fa5s.sync-alt", self.rebuild_index, self
        )
        self.form.add_row(
            "Opening index",
            self.rebuild_index_btn,
            hint="Regenerate the opening index from the built-in opening data.",
            width=None,
            advanced=True,
        )

        for btn in (
            self.clear_cache_btn,
            self.clear_explanations_btn,
            self.clear_api_cache_btn,
            self.clear_explorer_cache_btn,
            self.optimize_db_btn,
            self.rebuild_index_btn,
        ):
            btn.setMaximumWidth(200)
        self.register_busy_widgets(
            self.clear_cache_btn,
            self.clear_explanations_btn,
            self.clear_api_cache_btn,
            self.clear_explorer_cache_btn,
            self.optimize_db_btn,
            self.rebuild_index_btn,
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def clear_cache(self) -> None:
        if not ensure_idle(self.window()):
            return
        if not confirm_dialog(
            self,
            "Clear Analysis Cache",
            "Remove all cached engine evaluations? Your game history is kept.",
            confirm_label="Clear Cache",
        ):
            return
        close_analyzer_cache(self.window())
        self.run_task(lambda: AnalysisCache().clear_cache(), self._on_analysis_cleared)

    def _on_analysis_cleared(self, removed) -> None:
        self._toast(f"Removed {int(removed):,} cached evaluations.")
        self.data_changed.emit()

    def clear_explanations(self) -> None:
        if not confirm_dialog(
            self,
            "Clear Explanation Cache",
            "Remove all cached AI Coach explanations? Game analyses are kept.",
            confirm_label="Clear Explanations",
        ):
            return
        close_analyzer_cache(self.window())
        self.run_task(
            lambda: AnalysisCache().clear_explanations(), self._on_explanations_cleared
        )

    def _on_explanations_cleared(self, removed) -> None:
        self._toast(f"Removed {int(removed):,} cached explanations.")
        self.data_changed.emit()

    def clear_api_cache(self) -> None:
        if not confirm_dialog(
            self,
            "Clear API Cache",
            "Remove cached Chess.com and Lichess game lists? They will be "
            "downloaded again the next time you browse them.",
            confirm_label="Clear API Cache",
        ):
            return
        self.run_task(
            lambda: GameHistoryManager().clear_api_cache(), self._on_api_cleared
        )

    def _on_api_cleared(self, _result) -> None:
        self._toast("API cache cleared.")
        self.data_changed.emit()

    def clear_explorer_cache(self) -> None:
        if not confirm_dialog(
            self,
            "Clear Explorer Cache",
            "Remove cached opening-explorer responses? They will be fetched "
            "again the next time you open a position.",
            confirm_label="Clear Explorer Cache",
        ):
            return
        self.run_task(
            lambda: GameHistoryManager().clear_explorer_cache(),
            self._on_explorer_cleared,
        )

    def _on_explorer_cleared(self, removed) -> None:
        self._toast(f"Removed {int(removed):,} cached explorer positions.")
        self.data_changed.emit()

    def optimize_db(self) -> None:
        if not ensure_idle(self.window()):
            return
        close_analyzer_cache(self.window())
        self.run_task(self._optimize_database, self._on_optimized)

    @staticmethod
    def _optimize_database() -> None:
        history = GameHistoryManager()
        history.vacuum()
        history.checkpoint()

    def _on_optimized(self, _result) -> None:
        self._toast("Database optimized and compacted.")
        self.data_changed.emit()

    def rebuild_index(self) -> None:
        if not confirm_dialog(
            self,
            "Rebuild Opening Index",
            "Regenerate the opening index from the built-in opening data?",
            confirm_label="Rebuild",
        ):
            return
        explorer = getattr(self.window(), "explorer_view", None)
        explorer_db = getattr(explorer, "opening_db", None)
        if explorer_db is not None:
            explorer_db.close()
        self.run_task(
            rebuild_opening_index,
            lambda _result: self._on_index_rebuilt(explorer_db),
            lambda message: self._on_index_failed(explorer_db, message),
        )

    def _on_index_rebuilt(self, explorer_db) -> None:
        if explorer_db is not None:
            explorer_db.connect()
        self._toast("Opening index rebuilt.")
        self.data_changed.emit()

    def _on_index_failed(self, explorer_db, message) -> None:
        # Restore the explorer's handle even when the rebuild failed.
        if explorer_db is not None:
            try:
                explorer_db.connect()
            except Exception as e:  # pragma: no cover - defensive
                logger.error(f"Could not reopen opening index: {e}")
        self._report_error(message)

    def _toast(self, message: str) -> None:
        from src.gui.main_window import MainWindow

        MainWindow.toast_from_widget(self, message, "success")

    # ------------------------------------------------------------------
    # Lifecycle hooks used by SettingsView
    # ------------------------------------------------------------------
    def set_advanced_visible(self, visible: bool) -> None:
        self.setVisible(True)
        self.form.set_advanced_visible(visible)

    def refresh_styles(self, *args, **kwargs) -> None:
        self.setStyleSheet(Styles.get_group_box_style())
        self.form.refresh_styles()
        for btn in (
            self.clear_cache_btn,
            self.clear_explanations_btn,
            self.clear_api_cache_btn,
            self.clear_explorer_cache_btn,
            self.optimize_db_btn,
            self.rebuild_index_btn,
        ):
            btn.refresh_styles()

"""Cache clearing and database maintenance actions."""

import os

from PyQt6.QtWidgets import QVBoxLayout

from src.backend.storage.cache import AnalysisCache
from src.backend.storage.game_history import GameHistoryManager
from src.gui.components import Button, ButtonVariant, confirm_dialog
from src.gui.styles import Styles
from src.gui.views.settings.components import SettingsForm
from src.gui.views.settings.storage_actions import close_analyzer_cache, ensure_idle
from src.gui.views.settings.storage_card import StorageCard
from src.utils.logger import logger
from src.utils.path_utils import get_resource_path, get_user_data_dir


def rebuild_opening_index() -> str:
    """Delete and regenerate the derived opening index from bundled data."""
    from src.backend.analysis.opening_db import OpeningDB

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

        self.clear_cache_btn = Button('Clear Cache', ButtonVariant.FILLED, icon='fa5s.broom', on_click=self.clear_cache, parent=self)
        self.form.add_row(
            "Analysis cache",
            self.clear_cache_btn,
            hint="Remove cached engine evaluations.",
            width=None,
        )

        self.clear_explanations_btn = Button('Clear Explanations', ButtonVariant.FILLED, icon='fa5s.comment-slash', on_click=self.clear_explanations, parent=self)
        self.form.add_row(
            "Explanation cache",
            self.clear_explanations_btn,
            hint="Remove cached AI Coach move explanations.",
            width=None,
        )

        self.clear_api_cache_btn = Button('Clear API Cache', ButtonVariant.FILLED, icon='fa5s.cloud-download-alt', on_click=self.clear_api_cache, parent=self)
        self.form.add_row(
            "API cache",
            self.clear_api_cache_btn,
            hint="Remove cached Chess.com and Lichess game lists.",
            width=None,
        )

        self.clear_explorer_cache_btn = Button('Clear Explorer Cache', ButtonVariant.FILLED, icon='fa5s.globe', on_click=self.clear_explorer_cache, parent=self)
        self.form.add_row(
            "Explorer cache",
            self.clear_explorer_cache_btn,
            hint="Remove cached opening-explorer responses.",
            width=None,
        )

        self.optimize_db_btn = Button('Optimize DB', ButtonVariant.FILLED, icon='fa5s.tools', on_click=self.optimize_db, parent=self)
        self.form.add_row(
            "Database",
            self.optimize_db_btn,
            hint="Compact the history database and checkpoint WAL files.",
            width=None,
        )

        self.rebuild_index_btn = Button('Rebuild Index', ButtonVariant.FILLED, icon='fa5s.sync-alt', on_click=self.rebuild_index, parent=self)
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
        self.run_task(
            lambda: AnalysisCache().clear_cache(),
            self._on_analysis_cleared,
            loading_message="Clearing analysis cache…",
        )

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
            lambda: AnalysisCache().clear_explanations(),
            self._on_explanations_cleared,
            loading_message="Clearing explanations…",
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
            lambda: GameHistoryManager().clear_api_cache(),
            self._on_api_cleared,
            loading_message="Clearing cached games…",
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
            loading_message="Clearing explorer cache…",
        )

    def _on_explorer_cleared(self, removed) -> None:
        self._toast(f"Removed {int(removed):,} cached explorer positions.")
        self.data_changed.emit()

    def optimize_db(self) -> None:
        if not ensure_idle(self.window()):
            return
        close_analyzer_cache(self.window())
        self.run_task(
            self._optimize_database,
            self._on_optimized,
            loading_message="Optimizing database…",
        )

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
            loading_message="Rebuilding opening index…",
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

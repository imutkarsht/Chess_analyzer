"""Irreversible local-data reset."""

from PyQt6.QtWidgets import QVBoxLayout

from ....backend.storage.game_history import GameHistoryManager
from ...styles import Styles
from ...utils.gui_utils import confirm_dialog
from .components import SettingsForm
from .helpers import create_icon_button
from .storage_actions import (
    close_analyzer_cache,
    ensure_idle,
    refresh_after_data_change,
)
from .storage_card import StorageCard


class DangerSettings(StorageCard):
    """Delete every game and cache the app has stored locally."""

    def __init__(self, parent=None):
        super().__init__("Danger Zone", parent)
        self.setup_ui()

    def setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)

        self.form = SettingsForm(self)
        outer.addWidget(self.form)

        self.clear_data_btn = create_icon_button(
            "Reset All Data", "fa5s.trash-alt", self.reset_all_data, self, danger=True
        )
        self.clear_data_btn.setMaximumWidth(200)
        self.form.add_row(
            "All local data",
            self.clear_data_btn,
            hint=(
                "Delete every game, cached evaluation, explanation, and cached "
                "web response. This cannot be undone."
            ),
            width=None,
        )
        self.register_busy_widgets(self.clear_data_btn)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def reset_all_data(self) -> None:
        if not ensure_idle(self.window()):
            return
        if not confirm_dialog(
            self,
            "Reset All Data",
            "Delete your entire game history and every cache? This cannot be "
            "undone. Back up your data first if you want to keep it.",
            confirm_label="Reset All Data",
        ):
            return
        close_analyzer_cache(self.window())
        self.run_task(
            lambda: GameHistoryManager().clear_all_data(),
            self._on_reset_done,
            loading_message="Deleting local data…",
        )

    def _on_reset_done(self, _result) -> None:
        refresh_after_data_change(self.window())
        self.data_changed.emit()
        self._toast("All local data cleared.")

    # ------------------------------------------------------------------
    # Lifecycle hooks used by SettingsView
    # ------------------------------------------------------------------
    def set_advanced_visible(self, visible: bool) -> None:
        # Data deletion must stay reachable in both modes.
        self.setVisible(True)

    def refresh_styles(self, *args, **kwargs) -> None:
        self.setStyleSheet(Styles.get_group_box_style())
        self.form.refresh_styles()
        self.clear_data_btn.refresh_styles()

"""Data management actions."""

from PyQt6.QtWidgets import QGroupBox, QVBoxLayout

from ...styles import Styles
from .components import SettingsForm
from .helpers import create_icon_button


def clear_analysis_cache(parent_widget) -> bool:
    """
    Confirm and clear the analysis + explanation caches.

    Shared by the Data Management and the Move Explanations settings blocks so
    there is a single confirmation and a single cache-clearing path.
    """
    from src.backend.storage.cache import AnalysisCache
    from src.gui.main_window import MainWindow
    from src.gui.utils.gui_utils import confirm_dialog

    if not confirm_dialog(
        parent_widget,
        "Clear Cache",
        "Clear the analysis cache? Your game history will not be deleted.",
        confirm_label="Clear Cache",
    ):
        return False

    cache = AnalysisCache()
    cache.clear_cache()
    MainWindow.toast_from_widget(parent_widget, "Analysis cache cleared.", "success")
    return True


class DataSettings(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Data Management", parent)
        self.setStyleSheet(Styles.get_group_box_style())
        self.setup_ui()

    def setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)

        self.form = SettingsForm(self)
        outer.addWidget(self.form)

        self.clear_cache_btn = create_icon_button(
            "Clear Cache", "fa5s.broom", self.clear_cache, self
        )
        self.clear_cache_btn.setMaximumWidth(160)
        self.form.add_row(
            "Analysis cache",
            self.clear_cache_btn,
            hint="Remove cached engine evaluations and AI explanations.",
            width=None,
        )

        self.optimize_db_btn = create_icon_button(
            "Optimize DB", "fa5s.tools", self.optimize_db, self
        )
        self.optimize_db_btn.setMaximumWidth(160)
        self.form.add_row(
            "Database",
            self.optimize_db_btn,
            hint="Compact the history database and checkpoint WAL files.",
            width=None,
        )

        self.clear_data_btn = create_icon_button(
            "Reset All Data", "fa5s.trash-alt", self.clear_all_data, self, danger=True
        )
        self.clear_data_btn.setMaximumWidth(160)
        self.form.add_row(
            "Danger zone",
            self.clear_data_btn,
            hint="Delete all games and caches. This cannot be undone.",
            width=None,
        )

    def optimize_db(self):
        from src.backend.storage.game_history import GameHistoryManager
        from src.gui.main_window import MainWindow

        history = GameHistoryManager()
        history.vacuum()
        history.checkpoint()
        MainWindow.toast_from_widget(self, "Database optimized and compacted.", "success")

    def clear_cache(self):
        clear_analysis_cache(self)

    def clear_all_data(self):
        from src.gui.utils.gui_utils import confirm_dialog

        if confirm_dialog(
            self,
            "Reset All Data",
            "This will delete your ENTIRE game history and analysis cache. This cannot be undone.",
            confirm_label="Reset All Data",
        ):
            from src.backend.storage.cache import AnalysisCache
            from src.backend.storage.game_history import GameHistoryManager

            cache = AnalysisCache()
            cache.clear_cache()

            history = GameHistoryManager()
            history.clear_history()

            window = self.window()
            if hasattr(window, "games"):
                window.games = []
                if hasattr(window, "history_view"):
                    window.history_view.load_history()
                if hasattr(window, "metrics_view"):
                    window.metrics_view.refresh([])

            from src.gui.main_window import MainWindow

            MainWindow.toast_from_widget(self, "All data cleared.", "success")

    def set_advanced_visible(self, visible):
        # Data management is essential in both modes.
        self.setVisible(True)

    def refresh_styles(self, *args, **kwargs):
        self.setStyleSheet(Styles.get_group_box_style())
        self.form.refresh_styles()
        if hasattr(self, "clear_cache_btn"):
            self.clear_cache_btn.setStyleSheet(Styles.get_settings_default_button_style())
        if hasattr(self, "optimize_db_btn"):
            self.optimize_db_btn.setStyleSheet(Styles.get_settings_default_button_style())
        if hasattr(self, "clear_data_btn"):
            self.clear_data_btn.setStyleSheet(Styles.get_settings_danger_button_style())

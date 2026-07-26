"""
Data Management Settings group component.
"""
from PyQt6.QtWidgets import QGroupBox, QGridLayout
from ...styles import Styles
from .helpers import create_icon_button

class DataSettings(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Data Management", parent)
        self.setStyleSheet(Styles.get_group_box_style())
        
        self.setup_ui()

    def setup_ui(self):
        data_layout = QGridLayout(self)
        data_layout.setContentsMargins(20, 25, 20, 20)
        data_layout.setSpacing(12)
        
        self.clear_cache_btn = create_icon_button("Clear Cache", "fa5s.broom", self.clear_cache, self)
        data_layout.addWidget(self.clear_cache_btn, 0, 0)
        
        self.clear_data_btn = create_icon_button("Reset All Data", "fa5s.trash-alt", self.clear_all_data, self, danger=True)
        data_layout.addWidget(self.clear_data_btn, 0, 1)

    def clear_cache(self):
        from src.gui.utils.gui_utils import confirm_dialog
        if confirm_dialog(self, "Clear Cache",
                          "Clear the analysis cache? Your game history will not be deleted.",
                          confirm_label="Clear Cache"):
            from src.backend.storage.cache import AnalysisCache
            cache = AnalysisCache()
            cache.clear_cache()
            from src.gui.main_window import MainWindow
            MainWindow.toast_from_widget(self, "Analysis cache cleared.", "success")

    def clear_all_data(self):
        from src.gui.utils.gui_utils import confirm_dialog
        if confirm_dialog(self, "Reset All Data",
                          "This will delete your ENTIRE game history and analysis cache. This cannot be undone.",
                          confirm_label="Reset All Data"):
            from src.backend.storage.cache import AnalysisCache
            from src.backend.storage.game_history import GameHistoryManager
            
            cache = AnalysisCache()
            cache.clear_cache()
            
            history = GameHistoryManager()
            history.clear_history()
            
            # Also clear current games list in MainWindow if possible
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
        self.setVisible(visible)

    def refresh_styles(self, *args, **kwargs):
        pass

"""
Settings View
Coordinates lay out of settings block sections and handles global settings saving.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame, QMessageBox
from PyQt6.QtCore import pyqtSignal

from src.gui.styles import Styles
from src.utils.path_utils import get_resource_path
from src.gui.components import MasonryLayout
from src.utils.config import ConfigManager
from src.constants import DEFAULT_MULTI_PV, DEFAULT_LIVE_ANALYSIS_TIME

from .settings import (
    EngineSettings,
    BookSettings,
    ApiSettings,
    PlayerSettings,
    AppearanceSettings,
    DataSettings,
    LinksSettings,
    test_llm_sync as _test_llm_sync
)

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False


class SettingsView(QWidget):
    engine_path_changed = pyqtSignal(str)
    engine_settings_changed = pyqtSignal()  # emitted when Threads/Hash change
    llm_config_changed = pyqtSignal()   # emitted after LLM settings are saved
    usernames_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        
        # Main layout for the widget itself (contains header and scroll area)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header Bar Container
        self.header_bar = QFrame()
        self.header_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_BACKGROUND};
                border-bottom: 1px solid {Styles.COLOR_BORDER};
            }}
        """)
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(40, 12, 40, 12)
        
        # Title
        header_lbl = QLabel("Settings")
        header_lbl.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; background: transparent; border: none;")
        header_layout.addWidget(header_lbl)
        
        header_layout.addStretch()
        
        # Mode toggle
        self._mode = self.config_manager.get("settings_mode", "basic")
        self.mode_toggle_btn = self._create_mode_toggle()
        header_layout.addWidget(self.mode_toggle_btn)
        header_layout.addSpacing(12)
        
        # Create Save settings button
        self.save_settings_btn = self._create_save_button()
        header_layout.addWidget(self.save_settings_btn)
        
        main_layout.addWidget(self.header_bar)

        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND}; border: none;")
        
        # Container for content inside scroll area
        self.content_container = QWidget()
        self.content_container.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND};")
        
        # Use MasonryLayout for 2-column/3-column dynamic design
        self.container_layout = MasonryLayout(self.content_container, margin=40, spacing=25)
        
        self.scroll_area.setWidget(self.content_container)
        main_layout.addWidget(self.scroll_area)

        # Instantiate modular components
        self.engine_settings = EngineSettings(self.config_manager, self)
        self.book_settings = BookSettings(self.config_manager, self)
        self.api_settings = ApiSettings(self.config_manager, self)
        self.player_settings = PlayerSettings(self.config_manager, self)
        self.appearance_settings = AppearanceSettings(self.config_manager, self)
        self.data_settings = DataSettings(self)
        self.links_settings = LinksSettings(self)

        # Add components to layout
        self.container_layout.addWidget(self.engine_settings)
        self.container_layout.addWidget(self.book_settings)
        self.container_layout.addWidget(self.api_settings)
        self.container_layout.addWidget(self.player_settings)
        self.container_layout.addWidget(self.appearance_settings)
        self.container_layout.addWidget(self.data_settings)
        self.container_layout.addWidget(self.links_settings)

        # Connections
        self.appearance_settings.theme_refreshed.connect(self.on_theme_refreshed)

        # Backwards compatibility aliases for tests
        self.path_input = self.engine_settings.path_input
        self.depth_combo = self.engine_settings.depth_combo
        self.multi_pv_input = self.engine_settings.multi_pv_input
        self.live_time_input = self.engine_settings.live_time_input
        self.threads_input = self.engine_settings.threads_input
        self.hash_input = self.engine_settings.hash_input

        self.llm_profile_combo = self.api_settings.llm_profile_combo
        self.llm_provider_combo = self.api_settings.llm_provider_combo
        self.llm_profile_name = self.api_settings.llm_profile_name
        self.llm_key_input = self.api_settings.llm_key_input
        self.llm_model_input = self.api_settings.llm_model_input
        self.llm_url_input = self.api_settings.llm_url_input
        self.lichess_token_input = self.api_settings.lichess_token_input
        self.llm_test_btn = self.api_settings.llm_test_btn
        self.llm_test_result = self.api_settings.llm_test_result

        self.chesscom_input = self.player_settings.chesscom_input
        self.lichess_input = self.player_settings.lichess_input
        self.games_limit_input = self.player_settings.games_limit_input

        self.theme_combo = self.appearance_settings.theme_combo
        self.piece_combo = self.appearance_settings.piece_combo
        self.sound_checkbox = self.appearance_settings.sound_checkbox
        self.color_btn = self.appearance_settings.color_btn

        self.clear_cache_btn = self.data_settings.clear_cache_btn
        self.clear_data_btn = self.data_settings.clear_data_btn

        self.website_btn = self.links_settings.website_btn
        self.feedback_btn = self.links_settings.feedback_btn
        self.update_btn = self.links_settings.update_btn

        self._apply_mode()

    def reload_from_config(self):
        self.config_manager.reload_config()
        self.engine_settings.reload_from_config()
        self.book_settings.reload_from_config()
        self.player_settings.reload_from_config()
        self.api_settings._reload_profile_combo()
        self.api_settings.lichess_token_input.setText(self.config_manager.get("lichess_token", ""))
        self.appearance_settings.theme_combo.setCurrentText(self.config_manager.get("board_theme", "Green"))
        self.api_settings._update_active_label()

    def _create_save_button(self):
        btn = QMessageBox.QPushButton(f"  Save Settings") if hasattr(QMessageBox, 'QPushButton') else None
        # fallback to standard QPushButton
        from PyQt6.QtWidgets import QPushButton
        from PyQt6.QtCore import Qt
        btn = QPushButton(f"  Save Settings")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        if HAS_QTAWESOME:
            btn.setIcon(qta.icon("fa5s.save", color="#ffffff"))
        
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_ACCENT};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_ACCENT_HOVER};
            }}
        """)
        btn.clicked.connect(self.save_all_settings)
        return btn

    def on_theme_refreshed(self):
        window = self.window()
        if hasattr(window, "refresh_theme"):
            window.refresh_theme()

    def _create_mode_toggle(self):
        from PyQt6.QtWidgets import QPushButton
        from PyQt6.QtCore import Qt
        btn = QPushButton()
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._toggle_mode)
        self._update_mode_toggle_text(btn)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_SECONDARY};
                border: 1px solid {Styles.COLOR_BORDER};
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_SURFACE};
                color: {Styles.COLOR_ACCENT};
                border-color: {Styles.COLOR_ACCENT};
            }}
        """)
        return btn

    def _update_mode_toggle_text(self, btn=None):
        b = btn or self.mode_toggle_btn
        b.setText("  Advanced Settings" if self._mode == "basic" else "  Basic Settings")
        if HAS_QTAWESOME:
            icon_name = "fa5s.cog" if self._mode == "basic" else "fa5s.chevron-left"
            b.setIcon(qta.icon(icon_name, color=Styles.COLOR_TEXT_SECONDARY))
        # Always re-apply the themed stylesheet
        b.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_SECONDARY};
                border: 1px solid {Styles.COLOR_BORDER};
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_SURFACE};
                color: {Styles.COLOR_ACCENT};
                border-color: {Styles.COLOR_ACCENT};
            }}
        """)

    def _toggle_mode(self):
        self._mode = "advanced" if self._mode == "basic" else "basic"
        self._apply_mode()
        self._update_mode_toggle_text()
        self.config_manager.config["settings_mode"] = self._mode
        self.config_manager.save_config()

    def _apply_mode(self):
        is_advanced = self._mode == "advanced"
        is_basic = not is_advanced

        self.engine_settings.set_advanced_visible(is_advanced)
        self.book_settings.set_advanced_visible(is_advanced)
        self.api_settings.set_advanced_visible(is_advanced)
        self.player_settings.set_advanced_visible(is_advanced)
        self.appearance_settings.set_advanced_visible(is_advanced)
        self.data_settings.set_advanced_visible(is_advanced)
        self.links_settings.set_advanced_visible(is_advanced)

    def save_all_settings(self):
        """Save every setting in the app at once."""
        path = self.engine_settings.path_input.text().strip()
        if not path:
            QMessageBox.warning(self, "Error", "Please enter a valid engine path.")
            return

        threads, threads_ok = self.engine_settings._validated_threads()
        hash_mb, hash_ok = self.engine_settings._validated_hash()

        if not threads_ok or not hash_ok:
            return

        chesscom = self.player_settings.chesscom_input.text().strip()
        lichess = self.player_settings.lichess_input.text().strip()

        # Read and validate the games fetch limit
        limit_text = self.player_settings.games_limit_input.text().strip()
        try:
            limit = int(limit_text)
        except ValueError:
            limit = 20
            
        if limit < 1:
            limit = 1

        # Check Lichess API Token presence
        import os
        token = self.api_settings.lichess_token_input.text().strip() or self.config_manager.get("lichess_token", "") or os.getenv("LICHESS_TOKEN")
        
        clamped = False
        warning_msg = ""
        if token:
            if limit > 30:
                limit = 30
                clamped = True
                warning_msg = "Games limit capped at 30 (the maximum allowed when a Lichess API token is configured)."
        else:
            if limit > 20:
                limit = 20
                clamped = True
                warning_msg = "Games limit capped at 20. Configure a Lichess API Token in the API Configuration section above to increase this limit to 30."

        self.player_settings.games_limit_input.setText(str(limit))

        # Save current LLM profile edits to in-memory profile list first
        profiles = self.config_manager.get_profiles()
        idx = self.api_settings.llm_profile_combo.currentIndex()
        if 0 <= idx < len(profiles):
            old_name = profiles[idx].get("name", "")
            new_profile = self.api_settings._current_profile_dict()
            new_name = new_profile["name"]
            if not new_name:
                QMessageBox.warning(self, "Validation", "Profile name cannot be empty.")
                return
            if new_name != old_name and any(p["name"] == new_name for p in profiles):
                QMessageBox.warning(self, "Validation", f"A profile named \"{new_name}\" already exists.")
                return
            profiles[idx] = new_profile
            # Set selected profile as active
            self.config_manager.config["llm_active_profile"] = new_name
            self.config_manager.config["llm_profiles"] = profiles

        path_changed = self.config_manager.get("engine_path") != path
        threads_changed = self.config_manager.get("engine_threads") != threads
        hash_changed = self.config_manager.get("engine_hash") != hash_mb

        # Update in-memory configuration
        self.config_manager.config["engine_path"] = path
        self.config_manager.config["engine_threads"] = threads
        self.config_manager.config["engine_hash"] = hash_mb
        self.config_manager.config["polyglot_book_path"] = self.book_settings.polyglot_path_input.text().strip()
        
        try:
            self.config_manager.config["multi_pv"] = int(self.engine_settings.multi_pv_input.text().strip())
        except ValueError:
            self.config_manager.config["multi_pv"] = DEFAULT_MULTI_PV
            
        try:
            self.config_manager.config["live_analysis_time"] = float(self.engine_settings.live_time_input.text().strip())
        except ValueError:
            self.config_manager.config["live_analysis_time"] = DEFAULT_LIVE_ANALYSIS_TIME

        self.config_manager.config["lichess_token"] = self.api_settings.lichess_token_input.text().strip()
        self.config_manager.config["chesscom_username"] = chesscom
        self.config_manager.config["lichess_username"] = lichess
        self.config_manager.config["api_games_limit"] = limit

        # Save to disk
        self.config_manager.save_config()

        # Emit signals for UI and engine updates
        from ...utils.logger import logger
        if path_changed:
            logger.info(f"SettingsView: Engine path changed to {path}")
            self.engine_path_changed.emit(path)
        if threads_changed or hash_changed:
            logger.info(f"SettingsView: Engine settings changed. Threads={threads} (changed: {threads_changed}), Hash={hash_mb} (changed: {hash_changed})")
            self.engine_settings_changed.emit()
        else:
            logger.info("SettingsView: Engine settings (Threads, Hash) were NOT modified during this save.")

        self.llm_config_changed.emit()
        self.usernames_changed.emit()

        self.engine_settings.validate_engine_path()
        self.book_settings.validate_polyglot_path()
        self.api_settings._reload_profile_combo()

        from src.gui.main_window import MainWindow
        if clamped:
            QMessageBox.warning(self, "Limit Capped", f"Settings saved successfully.\n\nNote: {warning_msg}")
        else:
            MainWindow.toast_from_widget(self, "All settings saved successfully.", "success")

    def save_usernames(self):
        chesscom = self.chesscom_input.text()
        lichess = self.lichess_input.text()
        limit_text = self.games_limit_input.text().strip()
        try:
            limit = int(limit_text)
        except ValueError:
            limit = 20
        if limit < 1:
            limit = 1

        import os
        token = self.lichess_token_input.text().strip() or self.config_manager.get("lichess_token", "") or os.getenv("LICHESS_TOKEN")
        clamped = False
        warning_msg = ""
        if token:
            if limit > 30:
                limit = 30
                clamped = True
                warning_msg = "Games limit capped at 30 (the maximum allowed when a Lichess API token is configured)."
        else:
            if limit > 20:
                limit = 20
                clamped = True
                warning_msg = "Games limit capped at 20. Configure a Lichess API Token in the API Configuration section above to increase this limit to 30."

        self.games_limit_input.setText(str(limit))
        self.config_manager.set("chesscom_username", chesscom)
        self.config_manager.set("lichess_username", lichess)
        self.config_manager.set("api_games_limit", limit)
        self.usernames_changed.emit()

        from src.gui.main_window import MainWindow
        if clamped:
            QMessageBox.warning(self, "Limit Capped", warning_msg)
        else:
            MainWindow.toast_from_widget(self, "Settings saved successfully.", "success")

    def refresh_styles(self):
        """Re-applies styles to all widgets."""
        if hasattr(self, 'header_bar') and self.header_bar:
            self.header_bar.setStyleSheet(f"""
                QFrame {{
                    background-color: {Styles.COLOR_BACKGROUND};
                    border-bottom: 1px solid {Styles.COLOR_BORDER};
                }}
            """)

        # Update scroll area and content container backgrounds
        if hasattr(self, 'scroll_area') and self.scroll_area:
            self.scroll_area.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND}; border: none;")
        if hasattr(self, 'content_container') and self.content_container:
            self.content_container.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND};")

        # Refresh mode toggle button
        if hasattr(self, 'mode_toggle_btn') and self.mode_toggle_btn:
            self._update_mode_toggle_text(self.mode_toggle_btn)

        primary_style = f"""
            QPushButton {{
                background-color: {Styles.COLOR_ACCENT};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_ACCENT_HOVER};
            }}
        """
        if hasattr(self, 'save_settings_btn') and self.save_settings_btn:
            self.save_settings_btn.setStyleSheet(primary_style)

        default_style = f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_SURFACE};
                border-color: {Styles.COLOR_ACCENT};
            }}
        """

        danger_style = f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_BLUNDER};
                border: 1px solid {Styles.COLOR_BORDER};
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_SURFACE};
                color: {Styles.COLOR_BLUNDER};
                border-color: {Styles.COLOR_ACCENT};
            }}
        """

        llm_add_style = f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                font-size: 16px; font-weight: bold;
                min-width: 28px; max-width: 28px;
                min-height: 28px; max-height: 28px;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_SURFACE};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border-color: {Styles.COLOR_ACCENT};
            }}
        """

        llm_del_style = f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_BLUNDER};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                font-size: 16px; font-weight: bold;
                min-width: 28px; max-width: 28px;
                min-height: 28px; max-height: 28px;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_SURFACE};
                color: {Styles.COLOR_BLUNDER};
                border-color: {Styles.COLOR_ACCENT};
            }}
        """

        combo_style = Styles.get_combobox_style()

        input_style = f"""
            QLineEdit {{
                padding: 6px 12px;
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                font-size: 13px;
                max-width: 140px;
            }}
            QLineEdit:focus {{
                border: 1px solid {Styles.COLOR_ACCENT};
            }}
        """

        full_input_style = f"""
            QLineEdit {{
                padding: 10px;
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 4px;
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
            QLineEdit:focus {{
                border: 1px solid {Styles.COLOR_ACCENT};
            }}
        """

        tick_path = get_resource_path("assets/images/tick.svg").replace("\\", "/")
        sound_cb_style = f"""
            QCheckBox {{
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 13px;
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 4px;
                background-color: {Styles.COLOR_SURFACE_LIGHT};
            }}
            QCheckBox::indicator:checked {{
                background-color: {Styles.COLOR_ACCENT};
                border-color: {Styles.COLOR_ACCENT};
                image: url('{tick_path}');
            }}
        """

        self.engine_settings.refresh_styles(combo_style, input_style, default_style)
        self.book_settings.refresh_styles(combo_style, input_style, default_style)
        self.api_settings.refresh_styles(combo_style, full_input_style, default_style, llm_add_style, llm_del_style)
        self.player_settings.refresh_styles(input_style, full_input_style)
        self.appearance_settings.refresh_styles(combo_style, default_style, sound_cb_style)
        self.data_settings.refresh_styles(default_style, danger_style)
        self.links_settings.refresh_styles(default_style)

"""
Settings View
Coordinates lay out of settings block sections and handles global settings saving.
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.config.settings_schema import SETTINGS
from src.constants import DEFAULT_ENGINE_HASH_MB, DEFAULT_ENGINE_THREADS
from src.gui.styles import Styles
from src.utils.config import ConfigManager

from .settings import (
    ApiSettings,
    BackupSettings,
    BoardPiecesSettings,
    BookSettings,
    CoachSettings,
    DangerSettings,
    EngineSettings,
    FullAnalysisSettings,
    LinksSettings,
    LiveAnalysisSettings,
    MaintenanceSettings,
    PlayerSettings,
    RetentionSettings,
    ShortcutSettings,
    SoundSettings,
    StorageSettings,
    ThemeAccentSettings,
    WindowLayoutSettings,
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
    sidebar_prefs_changed = pyqtSignal()
    analysis_prefs_changed = pyqtSignal()  # cache / engine-lines shortcuts changed

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()

        # Main layout for the widget itself (contains header and scroll area)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header Bar Container
        self.header_bar = QFrame()
        self.header_bar.setStyleSheet(Styles.get_header_bar_ext_style(Styles.COLOR_BACKGROUND))
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(40, 12, 40, 12)

        # Title
        self.header_lbl = QLabel("Settings")
        self.header_lbl.setStyleSheet(Styles.get_label_style(size=24, color=Styles.COLOR_TEXT_PRIMARY, bold=True) + " " + Styles.get_transparent_label_style())
        header_layout.addWidget(self.header_lbl)

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
        self.scroll_area.setStyleSheet(Styles.get_background_style() + " border: none;")

        # Container for content inside scroll area
        self.content_container = QWidget()
        self.content_container.setStyleSheet(Styles.get_background_style())

        content_layout = QHBoxLayout(self.content_container)
        content_layout.setContentsMargins(24, 20, 24, 24)
        content_layout.setSpacing(24)

        # Left category rail
        rail = QWidget()
        rail.setFixedWidth(220)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(0, 0, 0, 0)
        rail_layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search settings...")
        self.search_input.setStyleSheet(Styles.get_input_style())
        self.search_input.textChanged.connect(self._filter_categories)
        rail_layout.addWidget(self.search_input)

        self.category_list = QListWidget()
        self.category_list.setFrameShape(QFrame.Shape.NoFrame)
        self.category_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.category_list.setSpacing(2)
        rail_layout.addWidget(self.category_list, 1)
        content_layout.addWidget(rail)

        # Right pages inside a distinct surface panel so the options area
        # reads as a separate region from the navigation rail.
        self.settings_panel = QFrame()
        self.settings_panel.setObjectName("SettingsPanel")
        self.settings_panel.setStyleSheet(self._panel_style())
        panel_layout = QVBoxLayout(self.settings_panel)
        panel_layout.setContentsMargins(28, 24, 28, 28)
        panel_layout.setSpacing(0)

        self.pages = QStackedWidget()
        self.pages.setStyleSheet("QStackedWidget { background: transparent; }")
        panel_layout.addWidget(self.pages)
        content_layout.addWidget(self.settings_panel, 1)
        self.scroll_area.setWidget(self.content_container)
        main_layout.addWidget(self.scroll_area)

        # Instantiate modular components
        self.engine_settings = EngineSettings(self.config_manager, self)
        self.full_analysis_settings = FullAnalysisSettings(self.config_manager, self)
        self.live_analysis_settings = LiveAnalysisSettings(self.config_manager, self)
        self.book_settings = BookSettings(self.config_manager, self)
        self.api_settings = ApiSettings(self.config_manager, self)
        self.coach_settings = CoachSettings(self.config_manager, self)
        self.player_settings = PlayerSettings(self.config_manager, self)
        self.theme_accent_settings = ThemeAccentSettings(self.config_manager, self)
        self.board_pieces_settings = BoardPiecesSettings(self.config_manager, self)
        self.window_layout_settings = WindowLayoutSettings(self.config_manager, self)
        self.sound_settings = SoundSettings(self.config_manager, self)
        self.storage_settings = StorageSettings(self)
        self.retention_settings = RetentionSettings(self.config_manager, self)
        self.maintenance_settings = MaintenanceSettings(self)
        self.backup_settings = BackupSettings(self)
        self.danger_settings = DangerSettings(self)
        self.links_settings = LinksSettings(self)
        self.shortcut_settings = ShortcutSettings(self.config_manager, self)

        # Category pages. Existing cards are reused until the generic binder
        # migration lands, but the navigation and layout are now scalable.
        self._page_dividers: list[tuple[QFrame, QWidget]] = []
        self._settings_pages = {
            "Analysis": [
                self.engine_settings,
                self.full_analysis_settings,
                self.live_analysis_settings,
                self.book_settings,
            ],
            "Appearance": [
                self.theme_accent_settings,
                self.board_pieces_settings,
                self.window_layout_settings,
                self.sound_settings,
            ],
            "AI Coach": [self.api_settings, self.coach_settings],
            "Integrations": [self.player_settings],
            "Data & Storage": [
                self.storage_settings,
                self.retention_settings,
                self.maintenance_settings,
                self.backup_settings,
                self.danger_settings,
            ],
            "Keyboard": [self.shortcut_settings],
            "About & Links": [self.links_settings],
        }
        for _category, cards in self._settings_pages.items():
            page = QWidget()
            page.setObjectName("SettingsPage")
            page.setStyleSheet("#SettingsPage { background: transparent; }")
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_layout.setSpacing(18)
            for index, card in enumerate(cards):
                if index:
                    divider = self._section_divider()
                    self._page_dividers.append((divider, card))
                    page_layout.addWidget(divider)
                page_layout.addWidget(card)
            page_layout.addStretch(1)
            self.pages.addWidget(page)

        self._search_index = self._build_search_index()
        self._populate_categories()
        self.category_list.currentRowChanged.connect(self._on_category_row_changed)
        self._style_category_rail()

        # Connections
        for card in (self.theme_accent_settings, self.board_pieces_settings):
            card.theme_refreshed.connect(self.on_theme_refreshed)
        self.window_layout_settings.sidebar_prefs_changed.connect(
            self.sidebar_prefs_changed.emit
        )
        for card in (self.full_analysis_settings, self.live_analysis_settings):
            card.binder.changed.connect(self._on_analysis_binder_changed)
        for card in (
            self.storage_settings,
            self.retention_settings,
            self.maintenance_settings,
            self.backup_settings,
            self.danger_settings,
        ):
            card.data_changed.connect(self._on_storage_data_changed)

        # Backwards compatibility aliases for tests
        self.path_input = self.engine_settings.path_input
        self.depth_combo = self.full_analysis_settings.depth_combo
        self.time_cap_combo = self.full_analysis_settings.time_cap_combo
        self.multi_pv_input = self.full_analysis_settings.multi_pv_input
        self.use_cache_checkbox = self.full_analysis_settings.cache_checkbox
        self.live_time_input = self.live_analysis_settings.live_time_input
        self.live_multi_pv_input = self.live_analysis_settings.live_multi_pv_input
        self.engine_lines_checkbox = self.live_analysis_settings.engine_lines_checkbox
        self.threads_input = self.engine_settings.threads_input
        self.hash_input = self.engine_settings.hash_input

        self.llm_profile_combo = self.api_settings.llm_profile_combo
        self.llm_provider_combo = self.api_settings.llm_provider_combo
        self.llm_profile_name = self.api_settings.llm_profile_name
        self.llm_key_input = self.api_settings.llm_key_input
        self.llm_model_input = self.api_settings.llm_model_input
        self.llm_url_input = self.api_settings.llm_url_input
        self.lichess_token_input = self.player_settings.lichess_token_input
        self.llm_test_btn = self.api_settings.llm_test_btn
        self.llm_test_result = self.api_settings.llm_test_result
        self.explain_trivial_checkbox = self.coach_settings.explain_trivial_checkbox
        self.explain_ttl_combo = self.retention_settings.explain_ttl_combo
        self.clear_explanations_btn = (
            self.maintenance_settings.clear_explanations_btn
        )

        self.chesscom_input = self.player_settings.chesscom_input
        self.lichess_input = self.player_settings.lichess_input
        self.games_limit_input = self.player_settings.games_limit_input

        self.theme_combo = self.board_pieces_settings.theme_combo
        self.piece_combo = self.board_pieces_settings.piece_combo
        self.sound_checkbox = self.sound_settings.sound_checkbox
        self.sound_volume_input = self.sound_settings.volume_input
        self.coordinates_checkbox = self.board_pieces_settings.coordinates_checkbox
        self.classification_checkbox = self.board_pieces_settings.classification_checkbox
        self.best_move_arrow_checkbox = (
            self.board_pieces_settings.best_move_arrow_checkbox
        )
        self.last_move_checkbox = self.board_pieces_settings.last_move_checkbox
        self.eval_bar_checkbox = self.board_pieces_settings.eval_bar_checkbox
        self.remember_window_checkbox = (
            self.window_layout_settings.remember_window_checkbox
        )
        self.color_btn = self.theme_accent_settings.color_btn

        self.clear_cache_btn = self.maintenance_settings.clear_cache_btn
        self.clear_data_btn = self.danger_settings.clear_data_btn

        self.website_btn = self.links_settings.website_btn
        self.feedback_btn = self.links_settings.feedback_btn
        self.update_btn = self.links_settings.update_btn

        # Engine values last applied to the running analyzer. Binder-driven
        # cards persist on edit, so Save compares against what the engine
        # actually uses instead of "config vs widget".
        self._applied_engine_path = self.config_manager.get("engine_path", "")
        self._applied_engine_threads = self.config_manager.get_int(
            "engine_threads", DEFAULT_ENGINE_THREADS
        )
        self._applied_engine_hash = self.config_manager.get_int(
            "engine_hash", DEFAULT_ENGINE_HASH_MB
        )

        self._apply_mode()

    def reload_from_config(self):
        self.config_manager.reload_config()
        self.engine_settings.reload_from_config()
        self.full_analysis_settings.reload_from_config()
        self.live_analysis_settings.reload_from_config()
        self.book_settings.reload_from_config()
        self.player_settings.reload_from_config()
        self.theme_accent_settings.reload_from_config()
        self.board_pieces_settings.reload_from_config()
        self.window_layout_settings.reload_from_config()
        self.sound_settings.reload_from_config()
        self.api_settings._reload_profile_combo()
        self.coach_settings.sync_explanation_settings()
        self.api_settings._update_active_label()
        self.shortcut_settings.reload_from_config()
        self.retention_settings.reload_from_config()
        self.storage_settings.refresh_stats()

    def _panel_style(self) -> str:
        return f"""
            QFrame#SettingsPanel {{
                background-color: {Styles.COLOR_SURFACE};
                border: none;
                border-radius: 0px;
            }}
        """

    @staticmethod
    def _section_divider() -> QFrame:
        """Single separator between cards, so every page divides groups the same way."""
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(Styles.get_divider_style())
        return divider

    def _sync_section_dividers(self) -> None:
        """Hide a divider when the card it introduces is hidden (Basic mode)."""
        for divider, card in self._page_dividers:
            divider.setVisible(not card.isHidden())

    def _on_analysis_binder_changed(self, key, _value) -> None:
        """Mirror the panel shortcuts when their settings change."""
        if key in {"use_cache", "engine_lines_enabled"}:
            self.analysis_prefs_changed.emit()

    def _on_storage_data_changed(self) -> None:
        """Re-read usage numbers after any storage card mutates local data."""
        self.storage_settings.refresh_stats()

    def sync_analysis_shortcuts(self) -> None:
        """Reload analysis cards after the eval panel changed the same keys."""
        self.full_analysis_settings.binder.load()
        self.live_analysis_settings.binder.load()

    def _build_search_index(self) -> dict[int, str]:
        """Searchable keywords per category, so results stay at category level."""
        page_for_category = {
            "Analysis": "Analysis",
            "Opening Explorer": "Analysis",
            "Appearance": "Appearance",
            "General": "Appearance",
            "Integrations": "Integrations",
            "AI Coach": "AI Coach",
            "Keyboard": "Keyboard",
            "Data & Storage": "Data & Storage",
        }
        page_names = list(self._settings_pages)
        index = {
            page_index: category.lower()
            for page_index, category in enumerate(page_names)
        }
        page_extras = {
            "Analysis": "engine stockfish depth multipv opening book polyglot",
            "Appearance": "theme accent colour color board pieces sidebar sound layout",
            "AI Coach": "api key provider model llm profile coach explanation cache",
            "Integrations": (
                "chesscom lichess username token network games limit profile "
                "preview avatar cache ttl explorer opening"
            ),
            "Data & Storage": (
                "cache database reset storage optimize clear backup restore "
                "maintenance vacuum retention ttl"
            ),
            "Keyboard": "shortcuts keys bindings preset",
            "About & Links": "website feedback bug update version links about",
        }
        for page_index, category in enumerate(page_names):
            index[page_index] += " " + page_extras.get(category, "")

        for spec in SETTINGS:
            if not spec.ui or spec.tier == "internal":
                continue
            if self._mode == "basic" and spec.tier != "basic":
                continue
            category = page_for_category.get(spec.category)
            if category is None:
                continue
            page_index = page_names.index(category)
            index[page_index] += " " + " ".join(
                [
                    spec.key,
                    spec.label,
                    spec.description,
                    spec.category,
                    str(spec.default),
                ]
            ).lower()
        return index

    def _populate_categories(self, query: str = "") -> None:
        self.category_list.blockSignals(True)
        self.category_list.clear()
        query = query.strip().lower()
        visible = [
            (any(not card.isHidden() for card in cards) if cards else True)
            for cards in self._settings_pages.values()
        ]

        if not query:
            for index, (category, _cards) in enumerate(self._settings_pages.items()):
                if not visible[index]:
                    continue
                item = QListWidgetItem(category)
                item.setData(Qt.ItemDataRole.UserRole, index)
                self.category_list.addItem(item)
        else:
            for index, category in enumerate(self._settings_pages):
                if not visible[index]:
                    continue
                if query in self._search_index.get(index, ""):
                    item = QListWidgetItem(category)
                    item.setData(Qt.ItemDataRole.UserRole, index)
                    self.category_list.addItem(item)
            if self.category_list.count() == 0:
                item = QListWidgetItem("No settings found")
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                self.category_list.addItem(item)

        self.category_list.blockSignals(False)
        if self.category_list.count():
            self.category_list.setCurrentRow(0)
            self._on_category_row_changed(0)

    def _on_category_row_changed(self, row: int) -> None:
        item = self.category_list.item(row)
        if item is None:
            return
        page_index = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(page_index, int):
            self.pages.setCurrentIndex(page_index)

    def _filter_categories(self, text: str) -> None:
        self._populate_categories(text)

    def _refresh_category_visibility(self) -> None:
        if self.search_input.text().strip():
            return
        current_page = self.pages.currentIndex()
        self._populate_categories()
        for row in range(self.category_list.count()):
            item = self.category_list.item(row)
            if item and item.data(Qt.ItemDataRole.UserRole) == current_page:
                self.category_list.setCurrentRow(row)
                return

    def _style_category_rail(self) -> None:
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: transparent;
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 9px 12px;
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 14px;
            }}
            QLineEdit:hover {{
                border-color: {Styles.COLOR_TEXT_MUTED};
            }}
            QLineEdit:focus {{
                border-color: {Styles.COLOR_ACCENT};
            }}
        """)
        self.category_list.setStyleSheet(f"""
            QListWidget {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                padding: 11px 14px;
                margin: 1px 0;
                border-radius: 8px;
                color: {Styles.COLOR_TEXT_SECONDARY};
                font-size: 15px;
                font-weight: 500;
            }}
            QListWidget::item:hover {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
            QListWidget::item:selected {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_ACCENT};
                border-left: 2px solid {Styles.COLOR_ACCENT};
                font-weight: 600;
            }}
        """)

    def _create_save_button(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QPushButton
        btn = QPushButton("  Save Settings")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(Styles.get_button_style())

        if HAS_QTAWESOME:
            btn.setIcon(qta.icon("fa5s.save", color="#ffffff"))

        btn.clicked.connect(self.save_all_settings)
        return btn

    def on_theme_refreshed(self):
        window = self.window()
        if hasattr(window, "refresh_theme"):
            window.refresh_theme()

    def _create_mode_toggle(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QPushButton
        btn = QPushButton()
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._toggle_mode)
        btn.setStyleSheet(Styles.get_control_button_style())
        self._update_mode_toggle_text(btn)
        return btn

    def _update_mode_toggle_text(self, btn=None):
        b = btn or self.mode_toggle_btn
        b.setText("  Advanced Settings" if self._mode == "basic" else "  Basic Settings")
        if HAS_QTAWESOME:
            icon_name = "fa5s.cog" if self._mode == "basic" else "fa5s.chevron-left"
            b.setIcon(qta.icon(icon_name, color=Styles.COLOR_TEXT_SECONDARY))
        b.setStyleSheet(Styles.get_control_button_style())

    def _toggle_mode(self):
        self._mode = "advanced" if self._mode == "basic" else "basic"
        self._apply_mode()
        self._update_mode_toggle_text()
        self.config_manager.config["settings_mode"] = self._mode
        self.config_manager.save_config()

    def _apply_mode(self):
        is_advanced = self._mode == "advanced"

        self.engine_settings.set_advanced_visible(is_advanced)
        self.full_analysis_settings.set_advanced_visible(is_advanced)
        self.live_analysis_settings.set_advanced_visible(is_advanced)
        self.book_settings.set_advanced_visible(is_advanced)
        self.api_settings.set_advanced_visible(is_advanced)
        self.coach_settings.set_advanced_visible(is_advanced)
        self.player_settings.set_advanced_visible(is_advanced)
        self.theme_accent_settings.set_advanced_visible(is_advanced)
        self.board_pieces_settings.set_advanced_visible(is_advanced)
        self.window_layout_settings.set_advanced_visible(is_advanced)
        self.sound_settings.set_advanced_visible(is_advanced)
        self.storage_settings.set_advanced_visible(is_advanced)
        self.retention_settings.set_advanced_visible(is_advanced)
        self.maintenance_settings.set_advanced_visible(is_advanced)
        self.backup_settings.set_advanced_visible(is_advanced)
        self.danger_settings.set_advanced_visible(is_advanced)
        self.links_settings.set_advanced_visible(is_advanced)
        self.shortcut_settings.set_advanced_visible(is_advanced)
        self._sync_section_dividers()
        self._search_index = self._build_search_index()
        self._refresh_category_visibility()

    def save_all_settings(self):
        """Flush every settings card, validate the engine, and notify consumers."""
        path = self.engine_settings.path_input.text().strip()
        if not path:
            from src.gui.main_window import MainWindow
            MainWindow.toast_from_widget(self, "Please enter a valid engine path.", "warning")
            return

        threads, threads_ok = self.engine_settings._validated_threads()
        hash_mb, hash_ok = self.engine_settings._validated_hash()

        if not threads_ok or not hash_ok:
            return

        # Save current LLM profile edits to in-memory profile list first
        profiles = self.config_manager.get_profiles()
        idx = self.api_settings.llm_profile_combo.currentIndex()
        if 0 <= idx < len(profiles):
            old_name = profiles[idx].get("name", "")
            new_profile = self.api_settings._current_profile_dict()
            new_name = new_profile["name"]
            if not new_name:
                from src.gui.main_window import MainWindow
                MainWindow.toast_from_widget(self, "Profile name cannot be empty.", "warning")
                return
            if new_name != old_name and any(p["name"] == new_name for p in profiles):
                from src.gui.main_window import MainWindow
                MainWindow.toast_from_widget(self, f'A profile named "{new_name}" already exists.', "warning")
                return
            profiles[idx] = new_profile
            # Set selected profile as active
            self.config_manager.set_profiles(profiles, active_name=new_name)

        # Resolve the token-dependent games cap before flushing so the user
        # still sees the warning when the requested value was too high.
        warning_msg = self.player_settings.apply_games_limit(
            self.player_settings.games_limit_input.text().strip()
        )

        # Persist anything the binder cards have not auto-saved yet.
        self._flush_binders()

        # Save to disk
        self.config_manager.save_config()

        # Emit signals for UI and engine updates
        from ...utils.logger import logger
        path_changed = self._applied_engine_path != path
        threads_changed = self._applied_engine_threads != threads
        hash_changed = self._applied_engine_hash != hash_mb

        if path_changed:
            logger.info(f"SettingsView: Engine path changed to {path}")
            self.engine_path_changed.emit(path)
            self._applied_engine_path = path
        if threads_changed or hash_changed:
            logger.info(f"SettingsView: Engine settings changed. Threads={threads} (changed: {threads_changed}), Hash={hash_mb} (changed: {hash_changed})")
            self.engine_settings_changed.emit()
            self._applied_engine_threads = threads
            self._applied_engine_hash = hash_mb
        else:
            logger.info("SettingsView: Engine settings (Threads, Hash) were NOT modified during this save.")

        self.llm_config_changed.emit()
        self.usernames_changed.emit()

        self.engine_settings.validate_engine_path()
        self.book_settings.validate_polyglot_path()
        self.api_settings._reload_profile_combo()

        from src.gui.main_window import MainWindow
        if warning_msg:
            MainWindow.toast_from_widget(self, f"Settings saved. Note: {warning_msg}", "warning")
        else:
            MainWindow.toast_from_widget(self, "All settings saved successfully.", "success")

    def _flush_binders(self) -> None:
        """Persist widget state for every card that uses a SettingsBinder."""
        binder_cards = (
            (self.engine_settings, "binder"),
            (self.full_analysis_settings, "binder"),
            (self.live_analysis_settings, "binder"),
            (self.book_settings, "binder"),
            (self.theme_accent_settings, "binder"),
            (self.board_pieces_settings, "binder"),
            (self.window_layout_settings, "binder"),
            (self.sound_settings, "binder"),
            (self.shortcut_settings, "binder"),
            (self.coach_settings, "binder"),
            (self.retention_settings, "binder"),
        )
        for card, attr in binder_cards:
            binder = getattr(card, attr, None)
            if binder is not None:
                binder.commit_all()

        # The Integrations page is a composite of three cards, each with its
        # own binder, so it cannot be expressed as a single (card, "binder").
        self.player_settings.commit_all()

    def save_usernames(self):
        # Resolve the requested cap before flushing: the binder commit writes
        # the already-clamped value back to the slider, which would hide the
        # warning. The token provider reads the just-typed field directly.
        warning_msg = self.player_settings.apply_games_limit(
            self.games_limit_input.text().strip()
        )
        self.player_settings.commit_all()
        self.config_manager.set("chesscom_username", self.chesscom_input.text().strip())
        self.config_manager.set("lichess_username", self.lichess_input.text().strip())
        self.usernames_changed.emit()

        from src.gui.main_window import MainWindow
        if warning_msg:
            MainWindow.toast_from_widget(self, f"Settings saved. Note: {warning_msg}", "warning")
        else:
            MainWindow.toast_from_widget(self, "Settings saved successfully.", "success")

    def refresh_styles(self):
        """Re-applies styles to settings view components."""
        if hasattr(self, 'header_bar'):
            self.header_bar.setStyleSheet(Styles.get_header_bar_ext_style(Styles.COLOR_BACKGROUND))
        if hasattr(self, 'header_lbl'):
            self.header_lbl.setStyleSheet(Styles.get_label_style(size=24, color=Styles.COLOR_TEXT_PRIMARY, bold=True) + " " + Styles.get_transparent_label_style())
        if hasattr(self, 'scroll_area'):
            self.scroll_area.setStyleSheet(Styles.get_background_style() + " border: none;")
        if hasattr(self, 'content_container'):
            self.content_container.setStyleSheet(Styles.get_background_style())
        if hasattr(self, 'category_list'):
            self._style_category_rail()
        if hasattr(self, 'settings_panel'):
            self.settings_panel.setStyleSheet(self._panel_style())
        if hasattr(self, 'save_settings_btn') and self.save_settings_btn:
            self.save_settings_btn.setStyleSheet(Styles.get_button_style())
        if hasattr(self, 'mode_toggle_btn') and self.mode_toggle_btn:
            self.mode_toggle_btn.setStyleSheet(Styles.get_control_button_style())
            self._update_mode_toggle_text(self.mode_toggle_btn)

        cards = (
            getattr(self, 'engine_settings', None),
            getattr(self, 'full_analysis_settings', None),
            getattr(self, 'live_analysis_settings', None),
            getattr(self, 'book_settings', None),
            getattr(self, 'api_settings', None),
            getattr(self, 'coach_settings', None),
            getattr(self, 'player_settings', None),
            getattr(self, 'theme_accent_settings', None),
            getattr(self, 'board_pieces_settings', None),
            getattr(self, 'window_layout_settings', None),
            getattr(self, 'sound_settings', None),
            getattr(self, 'storage_settings', None),
            getattr(self, 'retention_settings', None),
            getattr(self, 'maintenance_settings', None),
            getattr(self, 'backup_settings', None),
            getattr(self, 'danger_settings', None),
            getattr(self, 'links_settings', None),
            getattr(self, 'shortcut_settings', None),
        )
        for card in cards:
            if card and hasattr(card, 'refresh_styles'):
                card.refresh_styles()

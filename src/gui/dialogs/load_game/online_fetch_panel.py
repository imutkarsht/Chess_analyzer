import datetime

from PyQt6.QtCore import QDate, QObject, Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from src.backend.api.import_limits import clamp_games_limit, current_token
from src.backend.cache.api_cache import ApiGameCache
from src.backend.models.game_info import GameInfo
from src.backend.storage.game_history import GameHistoryManager
from src.gui.components import Tabs, TabVariant
from src.gui.components.toast import Toast
from src.gui.styles import Styles
from src.gui.utils.gui_utils import create_button
from src.utils.config import ConfigManager
from src.utils.path_utils import get_resource_path

from .api_worker import ApiWorker, register_worker, remove_worker
from .inline_game_list import InlineGameList


class DateClickFilter(QObject):
    def __init__(self, date_picker, parent=None):
        super().__init__(parent)
        self.date_picker = date_picker

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QCoreApplication, QEvent, Qt
        from PyQt6.QtGui import QKeyEvent
        if event.type() == QEvent.Type.MouseButtonRelease:
            self.date_picker.setFocus()
            press_event = QKeyEvent(
                QEvent.Type.KeyPress,
                Qt.Key.Key_Down,
                Qt.KeyboardModifier.AltModifier
            )
            QCoreApplication.postEvent(self.date_picker, press_event)
            return True
        return super().eventFilter(obj, event)


class SegmentedSelector(QWidget):
    """Accent-filled segmented control backed by the shared Tabs component.

    Keeps the key/value contract the fetch panel expects while delegating all
    geometry, hover and icon-state handling to ``Tabs``.
    """

    valueChanged = pyqtSignal(str)

    def __init__(self, options: list[tuple], initial_key: str = None, parent=None):
        super().__init__(parent)
        self._keys = [opt[0] for opt in options]
        self._updating = False
        self.selected_key = initial_key or self._keys[0]

        self.tabs = Tabs(
            TabVariant.SEGMENTED,
            active_style="accent",
            expand=False,
            track_padding=2,
            spacing=2,
            padding=(4, 14, 4, 14),
            radius=6,
            font_size=13,
            icon_size=16,
        )
        for opt in options:
            label = opt[1]
            icon = self._icon_spec(opt[2]) if len(opt) > 2 else None
            self.tabs.add_tab(label, icon=icon)
        self.tabs.current_changed.connect(self._on_tab_changed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)

        self.tabs.set_current_index(self._keys.index(self.selected_key))

    @staticmethod
    def _icon_spec(icon_name: str):
        """Asset paths become QIcons; anything else is a themed icon name."""
        if icon_name.startswith("assets/") or "/" in icon_name:
            return QIcon(get_resource_path(icon_name))
        return icon_name

    def _on_tab_changed(self, index: int) -> None:
        if not 0 <= index < len(self._keys):
            return
        self.selected_key = self._keys[index]
        if not self._updating:
            self.valueChanged.emit(self.selected_key)

    def value(self) -> str:
        return self.selected_key

    def setValue(self, key: str):
        if key not in self._keys:
            return
        self._updating = True
        try:
            self.selected_key = key
            self.tabs.set_current_index(self._keys.index(key))
        finally:
            self._updating = False

    def refresh_styles(self):
        self.tabs.refresh_styles()


def fetch_job(cache: ApiGameCache, mode: str, platform: str, username: str, date: datetime.date, url: str, game_id: str, limit: int) -> list[GameInfo]:
    if mode == "recent":
        if platform == "lichess":
            from src.backend.api.lichess_api import LichessAPI

            def func_recent_li():
                return LichessAPI().get_user_games(username, limit)
            func = func_recent_li
        else:
            from src.backend.api.chess_com_api import ChessComAPI

            def func_recent_cc():
                return ChessComAPI.get_last_games(username, limit)
            func = func_recent_cc
        return cache.get_recent(platform, username, limit, func)

    elif mode == "date":
        if platform == "lichess":
            from src.backend.api.lichess_api import LichessAPI

            def func_date_li():
                return LichessAPI().get_user_games_by_date(username, date)
            func = func_date_li
        else:
            from src.backend.api.chess_com_api import ChessComAPI

            def func_date_cc():
                return ChessComAPI.get_user_games_by_date(username, date)
            func = func_date_cc
        return cache.get_by_date(platform, username, date, func)

    elif mode == "url":
        if platform == "lichess":
            from src.backend.api.lichess_api import LichessAPI

            def func_url_li():
                return LichessAPI().get_game_by_id(game_id)
            func = func_url_li
        else:
            from src.backend.api.chess_com_api import ChessComAPI

            def func_url_cc():
                return ChessComAPI.get_game_by_id(game_id, url, username)
            func = func_url_cc
        res = cache.get_by_id(platform, game_id, func)
        return [res] if res else []
    return []


class OnlineFetchPanel(QWidget):
    pgn_ready = pyqtSignal(str, object)
    pending_cleared = pyqtSignal()
    navigate_to_settings = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.history_manager = GameHistoryManager()
        self.cache = ApiGameCache(self.history_manager)
        self._parsed_games: list[GameInfo] = []
        self._worker = None
        self.setup_ui()

    def setup_ui(self):
        from PyQt6.QtWidgets import QSizePolicy
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        # Container for controls
        self.controls_widget = QWidget()
        layout = QVBoxLayout(self.controls_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Styled Form Card Container
        self.form_card = QWidget()
        self.form_card.setObjectName("FormCard")
        self.form_card.setStyleSheet(f"""
            #FormCard {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 12px;
            }}
        """)

        card_layout = QVBoxLayout(self.form_card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        # Dynamic inputs using FormLayout
        self.form_layout = QFormLayout()
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setSpacing(14)
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Platform selector row
        lbl_platform = QLabel("Platform:")
        lbl_platform.setStyleSheet(Styles.get_form_label_style())
        self.platform_selector = SegmentedSelector([
            ("chesscom", "Chess.com", "assets/icons/chesscom.png"),
            ("lichess", "Lichess", "assets/icons/lichess.png")
        ], "chesscom")
        self.platform_selector.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.platform_selector.valueChanged.connect(self._on_platform_changed)
        self.form_layout.addRow(lbl_platform, self.platform_selector)

        # Mode selector row
        lbl_mode = QLabel("Mode:")
        lbl_mode.setStyleSheet(Styles.get_form_label_style())
        self.mode_selector = SegmentedSelector([
            ("recent", "Recent", "fa5s.history"),
            ("date", "By Date", "fa5s.calendar-alt"),
            ("url", "By URL", "fa5s.link")
        ], "recent")
        self.mode_selector.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.mode_selector.valueChanged.connect(self._on_mode_changed)
        self.form_layout.addRow(lbl_mode, self.mode_selector)

        # Form Field 1: Username
        self.username_label = QLabel("Username:")
        self.username_label.setStyleSheet(f"font-size: 13px; color: {Styles.COLOR_TEXT_PRIMARY};")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter username")
        self.username_input.setStyleSheet(self._input_style())
        self.username_input.returnPressed.connect(self._fetch)

        import qtawesome as qta
        user_icon = qta.icon("fa5s.user", color=Styles.COLOR_TEXT_SECONDARY)
        self.username_input.addAction(user_icon, QLineEdit.ActionPosition.LeadingPosition)

        self.form_layout.addRow(self.username_label, self.username_input)

        # Form Field 2: Modern Date Picker
        from src.gui.components.modern_date_picker import ModernDatePicker
        self.date_label = QLabel("Date:")
        self.date_label.setStyleSheet(f"font-size: 13px; color: {Styles.COLOR_TEXT_PRIMARY};")
        self.date_picker = ModernDatePicker(self, initial_date=QDate.currentDate())
        self.form_layout.addRow(self.date_label, self.date_picker)

        # Form Field 3: URL Input
        self.url_label = QLabel("Game URL:")
        self.url_label.setStyleSheet(f"font-size: 13px; color: {Styles.COLOR_TEXT_PRIMARY};")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste chess.com or lichess.org game link")
        self.url_input.setStyleSheet(self._input_style())
        self.url_input.returnPressed.connect(self._fetch)

        link_icon = qta.icon("fa5s.link", color=Styles.COLOR_TEXT_SECONDARY)
        self.url_input.addAction(link_icon, QLineEdit.ActionPosition.LeadingPosition)

        self.form_layout.addRow(self.url_label, self.url_input)

        # Centered action button
        self.fetch_btn = create_button("Fetch Games", style="primary", on_click=self._fetch, icon_name="fa5s.cloud-download-alt")
        self.fetch_btn.setFixedHeight(38)
        self.fetch_btn.setMinimumWidth(200)
        self.fetch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fetch_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_ACCENT};
                color: #FFFFFF !important;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 700;
                padding: 0 24px;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_ACCENT_HOVER};
            }}
            QPushButton:disabled {{
                background-color: {Styles.COLOR_BORDER};
                color: {Styles.COLOR_TEXT_MUTED};
            }}
        """)

        btn_box = QHBoxLayout()
        btn_box.setContentsMargins(0, 8, 0, 0)
        btn_box.addStretch()
        btn_box.addWidget(self.fetch_btn)
        btn_box.addStretch()

        self.form_layout.addRow("", btn_box)

        card_layout.addLayout(self.form_layout)
        layout.addWidget(self.form_card)

        layout.addStretch()
        root.addWidget(self.controls_widget, stretch=1)

        # Results InlineGameList
        self.game_list = InlineGameList()
        self.game_list.setVisible(False)
        self.game_list.game_chosen.connect(self._on_game_chosen)
        self.game_list.cleared.connect(self._clear)
        root.addWidget(self.game_list, stretch=1)

        # Initial view config
        self._on_platform_changed("chesscom")
        self._on_mode_changed("recent")

    def _input_style(self):
        return f"""
            QLineEdit {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 0 12px;
                padding-left: 32px;
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 13px;
                height: 38px;
            }}
            QLineEdit:focus {{
                border: 1px solid {Styles.COLOR_ACCENT};
            }}
        """

    def _on_platform_changed(self, platform: str):
        # Prefill username
        if platform == "chesscom":
            username = self.config_manager.get("chesscom_username", "")
        else:
            username = self.config_manager.get("lichess_username", "")
        self.username_input.setText(username)
        self._update_fields_visibility()

    def _on_mode_changed(self, mode: str):
        self._update_fields_visibility()

    def _update_fields_visibility(self):
        platform = self.platform_selector.value()
        mode = self.mode_selector.value()

        recent_mode = (mode == "recent")
        date_mode = (mode == "date")
        url_mode = (mode == "url")

        show_username = recent_mode or date_mode or (url_mode and platform == "chesscom")

        self.username_label.setVisible(show_username)
        self.username_input.setVisible(show_username)
        self.date_label.setVisible(date_mode)
        self.date_picker.setVisible(date_mode)
        self.url_label.setVisible(url_mode)
        self.url_input.setVisible(url_mode)

        if url_mode:
            self.fetch_btn.setText("Fetch Game")
        else:
            self.fetch_btn.setText("Fetch Games")

    def _fetch(self):
        platform = self.platform_selector.value()
        mode = self.mode_selector.value()

        username = self.username_input.text().strip()
        url = self.url_input.text().strip()
        qdate = self.date_picker.date()
        date = datetime.date(qdate.year(), qdate.month(), qdate.day())

        game_id = ""

        username_required = (mode in ["recent", "date"]) or (mode == "url" and platform == "chesscom")
        if username_required and not username:
            Toast.show_message(self.window(), "Please enter a username.", "warning")
            return
        if mode == "url":
            if not url:
                Toast.show_message(self.window(), "Please enter a game URL.", "warning")
                return

            # Extract game ID
            if platform == "lichess":
                from src.backend.api.lichess_api import LichessAPI
                game_id = LichessAPI().extract_game_id(url)
            else:
                from src.backend.api.chess_com_api import ChessComAPI
                game_id = ChessComAPI.extract_game_id(url)

            if not game_id:
                Toast.show_message(self.window(), f"Could not extract a valid game ID from the URL for {platform}.", "error")
                return

        # Prepare UI for loading
        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("Fetching...")
        self.username_input.setEnabled(False)
        self.url_input.setEnabled(False)
        self.date_picker.setEnabled(False)
        self.platform_selector.setEnabled(False)
        self.mode_selector.setEnabled(False)

        # Cleanup active worker
        if self._worker is not None and self._worker.isRunning():
            try:
                self._worker.finished.disconnect()
                self._worker.error.disconnect()
            except (TypeError, RuntimeError):
                pass

        limit = clamp_games_limit(
            self.config_manager.get("api_games_limit", 20),
            current_token(self.config_manager),
        )

        # Start ApiWorker with fetch_job helper
        self._worker = ApiWorker(
            fetch_job,
            self.cache,
            mode,
            platform,
            username,
            date,
            url,
            game_id,
            limit,
            parent=self
        )

        register_worker(self._worker)
        self._worker.finished.connect(lambda: remove_worker(self._worker))
        self._worker.error.connect(lambda: remove_worker(self._worker))

        self._worker.finished.connect(self._on_fetch_finished)
        self._worker.error.connect(self._on_fetch_error)
        self._worker.start()

    def _on_fetch_error(self, err_msg: str):
        self._reset_input_ui()
        Toast.show_message(self.window(), f"Fetch failed: {err_msg}", "error")

    def _on_fetch_finished(self, game_infos: list[GameInfo]):
        self._reset_input_ui()

        if not game_infos:
            Toast.show_message(self.window(), "No games found matching the query.", "warning")
            return

        self._parsed_games = game_infos
        rows = []
        for info in game_infos:
            white = info.white or "?"
            black = info.black or "?"
            w_elo = info.white_elo or "?"
            b_elo = info.black_elo or "?"
            result = info.result or "?"
            date = info.date or "?"
            tc_label = info.time_class or "standard"
            move_count = info.move_count or "?"
            opening = info.opening

            line1 = f"{date}  ·  {tc_label.upper()}  ·  {result}  ·  {move_count} moves"
            line2 = f"{white} ({w_elo})  vs  {black} ({b_elo})"
            if opening:
                line2 += f"  ·  {opening}"
            rows.append((line1, line2))

        n = len(self._parsed_games)
        header_text = "1 game ready to load:" if n == 1 else f"Select a game ({n} found):"

        self.controls_widget.setVisible(False)
        self.game_list.populate(rows, header_text)
        self.game_list.setVisible(True)

    def _reset_input_ui(self):
        self.fetch_btn.setEnabled(True)
        self._on_mode_changed(self.mode_selector.value())
        self.username_input.setEnabled(True)
        self.url_input.setEnabled(True)
        self.date_picker.setEnabled(True)
        self.platform_selector.setEnabled(True)
        self.mode_selector.setEnabled(True)

    def _on_game_chosen(self, index: int):
        if 0 <= index < len(self._parsed_games):
            info = self._parsed_games[index]
            # Emit standard contract (pgn, raw_game_dict/metadata)
            self.pgn_ready.emit(info.pgn, info.to_dict())

    def _clear(self):
        self._parsed_games = []
        self.game_list.setVisible(False)
        self.game_list.clear()
        self.controls_widget.setVisible(True)
        self.url_input.clear()
        self._on_platform_changed(self.platform_selector.value())
        self.pending_cleared.emit()

    def reset(self):
        self._clear()

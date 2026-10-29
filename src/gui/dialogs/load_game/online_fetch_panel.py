import datetime

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.backend.api.import_limits import clamp_games_limit, current_token
from src.backend.cache.api_cache import ApiGameCache
from src.backend.models.game_info import GameInfo
from src.backend.storage.game_history import GameHistoryManager
from src.gui.components import (
    Button,
    ButtonSize,
    ButtonVariant,
    DatePicker,
    FormField,
    Input,
    InputSize,
    PulsingSkeleton,
    StatusBadge,
    Tabs,
    TabVariant,
)
from src.gui.components.toast import ToastHandle, ToastManager
from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.utils.config import ConfigManager
from src.utils.path_utils import get_resource_path

from .api_worker import ApiWorker, register_worker, remove_worker
from .helpers import game_row
from .inline_game_list import InlineGameList

try:
    import qtawesome as qta
except ImportError:  # pragma: no cover - QtAwesome ships with the app
    qta = None


class SegmentedSelector(QWidget):
    """Segmented source/mode control backed by the shared Tabs component."""

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

    if mode == "date":
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

    if mode == "url":
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
        result = cache.get_by_id(platform, game_id, func)
        return [result] if result else []
    return []


_STATE_FORM = 0
_STATE_LOADING = 1
_STATE_ERROR = 2
_STATE_EMPTY = 3
_STATE_RESULTS = 4


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
        self._worker: ApiWorker | None = None
        self._fetch_toast: ToastHandle | None = None
        self._last_query: dict = {}
        self._setup_ui()

        manager = ThemeManager.instance()
        manager.theme_changed.connect(self._on_theme_changed)
        manager.accent_changed.connect(self._on_theme_changed)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(20)

        self.controls_widget = QWidget()
        controls = QVBoxLayout(self.controls_widget)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(16)

        # Source / mode toolbar — no form labels.
        self.platform_selector = SegmentedSelector(
            [
                ("chesscom", "Chess.com", "assets/icons/chesscom.png"),
                ("lichess", "Lichess", "assets/icons/lichess.png"),
            ],
            "chesscom",
        )
        self.mode_selector = SegmentedSelector(
            [
                ("recent", "Recent", "fa5s.history"),
                ("date", "By Date", "fa5s.calendar-alt"),
                ("url", "By URL", "fa5s.link"),
            ],
            "recent",
        )
        self.platform_selector.valueChanged.connect(self._on_platform_changed)
        self.mode_selector.valueChanged.connect(self._on_mode_changed)
        for selector in (self.platform_selector, self.mode_selector):
            selector.setSizePolicy(
                QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
            )

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(12)
        toolbar.addWidget(self.platform_selector)
        toolbar.addWidget(self.mode_selector)
        toolbar.addStretch(1)
        controls.addLayout(toolbar)

        # Form card, capped and centered.
        self.form_card = QFrame()
        self.form_card.setObjectName("FetchCard")
        self.form_card.setFixedWidth(520)
        self.form_card.setStyleSheet(
            f"""
            QFrame#FetchCard {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 12px;
            }}
            """
        )
        card = QVBoxLayout(self.form_card)
        card.setContentsMargins(20, 20, 20, 20)
        card.setSpacing(16)

        self.username_input = Input(
            placeholder="Username",
            size=InputSize.LG,
            on_submit=self._fetch,
        )
        self.username_field = FormField("Username", self.username_input)
        card.addWidget(self.username_field)

        self.date_picker = DatePicker(
            self,
            label="",
            initial_date=QDate.currentDate(),
            maximum=QDate.currentDate(),
            compact=True,
        )
        self.date_field = FormField(
            "Date",
            self.date_picker,
            "Fetches games played on this calendar day.",
        )
        card.addWidget(self.date_field)

        self.url_input = Input(
            placeholder="https://www.chess.com/game/…",
            size=InputSize.LG,
            on_submit=self._fetch,
        )
        self.url_field = FormField(
            "Game URL",
            self.url_input,
            "Paste a Chess.com or Lichess game link.",
        )
        card.addWidget(self.url_field)

        self.fetch_btn = Button(
            "Fetch games",
            ButtonVariant.PRIMARY,
            ButtonSize.MD,
            icon="fa5s.cloud-download-alt",
            full_width=True,
            on_click=self._fetch,
        )
        self.fetch_btn.setMinimumHeight(40)
        self.cancel_btn = Button(
            "Cancel",
            ButtonVariant.GHOST,
            ButtonSize.MD,
            on_click=self._cancel_fetch,
        )
        self.cancel_btn.setVisible(False)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 4, 0, 0)
        actions.setSpacing(8)
        actions.addWidget(self.fetch_btn, 1)
        actions.addWidget(self.cancel_btn)
        card.addLayout(actions)

        card_row = QHBoxLayout()
        card_row.setContentsMargins(0, 0, 0, 0)
        card_row.addStretch(1)
        card_row.addWidget(self.form_card)
        card_row.addStretch(1)
        controls.addLayout(card_row)
        controls.addStretch(1)

        # One page at a time: form, loading, error, empty, or results.
        self.state_stack = QStackedWidget()
        self.state_stack.addWidget(self.controls_widget)
        self.state_stack.addWidget(self._build_loading_state())
        self.state_stack.addWidget(self._build_error_state())
        self.state_stack.addWidget(self._build_empty_state())
        self.state_stack.addWidget(self._build_results_state())
        self.state_stack.setCurrentIndex(_STATE_FORM)
        root.addWidget(self.state_stack, 1)

        self._on_platform_changed("chesscom")
        self._on_mode_changed("recent")
        self.refresh_styles()

    def _build_loading_state(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        self._skeleton = PulsingSkeleton("Fetching games…", " ")
        layout.addWidget(self._skeleton)
        layout.addStretch(1)
        return page

    def _build_error_state(self) -> QWidget:
        page = QFrame()
        page.setObjectName("InlineState")
        page.setStyleSheet(self._inline_state_qss())
        self._error_page = page
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        self._error_icon = QLabel()
        self._error_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._error_icon, 0, Qt.AlignmentFlag.AlignHCenter)

        self._error_title = QLabel("Couldn't fetch games")
        self._error_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_title.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY};"
            " background: transparent;"
        )
        self._error_message = QLabel("")
        self._error_message.setWordWrap(True)
        self._error_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_message.setStyleSheet(
            f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY};"
            " background: transparent;"
        )
        retry = Button(
            "Try again",
            ButtonVariant.TONAL,
            ButtonSize.SM,
            on_click=self._fetch,
        )
        retry.setMaximumWidth(120)

        layout.addStretch(1)
        layout.addWidget(self._error_title)
        layout.addWidget(self._error_message)
        layout.addWidget(retry, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)
        return page

    def _build_empty_state(self) -> QWidget:
        page = QFrame()
        page.setObjectName("InlineState")
        page.setStyleSheet(self._inline_state_qss())
        self._empty_page = page
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)

        self._empty_icon = QLabel()
        self._empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("No games found")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_title = title
        title.setStyleSheet(
            f"font-size: 15px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY};"
            " background: transparent;"
        )
        description = QLabel(
            "Try another username, date, or check that the profile is public."
        )
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setWordWrap(True)
        self._empty_description = description
        description.setStyleSheet(
            f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY};"
            " background: transparent;"
        )

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addStretch(1)
        change = Button(
            "Change filters",
            ButtonVariant.HOLLOW,
            ButtonSize.SM,
            on_click=self._show_filters,
        )
        settings = Button(
            "Open settings",
            ButtonVariant.LINK,
            ButtonSize.SM,
            on_click=self.navigate_to_settings.emit,
        )
        actions.addWidget(change)
        actions.addWidget(settings)
        actions.addStretch(1)

        layout.addStretch(1)
        layout.addWidget(self._empty_icon, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(6)
        layout.addLayout(actions)
        layout.addStretch(1)
        return page

    def _build_results_state(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        bar = QHBoxLayout()
        bar.setContentsMargins(2, 0, 2, 0)
        bar.setSpacing(10)
        self._summary_label = QLabel("")
        self._summary_label.setStyleSheet(
            f"font-size: 12px; font-weight: 500; color: {Styles.COLOR_TEXT_SECONDARY};"
            " background: transparent;"
        )
        self._count_badge = StatusBadge("", "neutral", font_size=10)
        change = Button(
            "Change filters",
            ButtonVariant.GHOST,
            ButtonSize.SM,
            on_click=self._show_filters,
        )
        bar.addWidget(self._summary_label)
        bar.addWidget(self._count_badge)
        bar.addStretch(1)
        bar.addWidget(change)
        layout.addLayout(bar)

        self.game_list = InlineGameList()
        self.game_list.setVisible(False)
        self.game_list.game_chosen.connect(self._on_game_chosen)
        self.game_list.cleared.connect(self._clear)
        layout.addWidget(self.game_list, 1)
        return page

    @staticmethod
    def _inline_state_qss() -> str:
        return "QFrame#InlineState { background: transparent; border: none; }"

    def _on_theme_changed(self, *_args) -> None:
        self.refresh_styles()

    def refresh_styles(self) -> None:
        self.form_card.setStyleSheet(
            f"""
            QFrame#FetchCard {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 12px;
            }}
            """
        )
        for page in (self._error_page, self._empty_page):
            page.setStyleSheet(self._inline_state_qss())
        self._error_title.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY};"
            " background: transparent;"
        )
        self._error_message.setStyleSheet(
            f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY};"
            " background: transparent;"
        )
        self._empty_title.setStyleSheet(
            f"font-size: 15px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY};"
            " background: transparent;"
        )
        self._empty_description.setStyleSheet(
            f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY};"
            " background: transparent;"
        )
        self._summary_label.setStyleSheet(
            f"font-size: 12px; font-weight: 500; color: {Styles.COLOR_TEXT_SECONDARY};"
            " background: transparent;"
        )
        if qta is not None:
            self._error_icon.setPixmap(
                qta.icon(
                    "fa5s.exclamation-circle", color=Styles.COLOR_BLUNDER
                ).pixmap(28, 28)
            )
            self._empty_icon.setPixmap(
                qta.icon(
                    "fa5s.search", color=Styles.COLOR_TEXT_MUTED
                ).pixmap(28, 28)
            )
        self.platform_selector.refresh_styles()
        self.mode_selector.refresh_styles()

    # ------------------------------------------------------------------
    # Form state
    # ------------------------------------------------------------------
    def _on_platform_changed(self, platform: str) -> None:
        key = "chesscom_username" if platform == "chesscom" else "lichess_username"
        self.username_input.setText(self.config_manager.get(key, ""))
        self._update_fields_visibility()

    def _on_mode_changed(self, mode: str) -> None:
        self._update_fields_visibility()

    def _update_fields_visibility(self) -> None:
        platform = self.platform_selector.value()
        mode = self.mode_selector.value()

        recent_mode = mode == "recent"
        date_mode = mode == "date"
        url_mode = mode == "url"

        show_username = recent_mode or date_mode
        self.username_field.setVisible(show_username)
        self.date_field.setVisible(date_mode)
        self.url_field.setVisible(url_mode)

        if url_mode:
            self.url_input.setPlaceholderText(
                "https://lichess.org/…"
                if platform == "lichess"
                else "https://www.chess.com/game/…"
            )
            self.fetch_btn.setText("Fetch game")
        else:
            self.fetch_btn.setText("Fetch games")
        self._refresh_username_hint()

    def _refresh_username_hint(self) -> None:
        mode = self.mode_selector.value()
        platform = self.platform_selector.value()
        if mode == "recent":
            limit = clamp_games_limit(
                self.config_manager.get("api_games_limit", 20),
                current_token(self.config_manager),
            )
            self.username_field.set_description(
                f"Fetches the last {limit} games from "
                f"{'Chess.com' if platform == 'chesscom' else 'Lichess'}."
            )
        elif mode == "date":
            self.username_field.set_description(
                "Fetches every game played on the selected day."
            )
        else:
            self.username_field.set_description(
                "Used to find the game in this player's archive."
            )

    def _show_filters(self) -> None:
        self._show_state(_STATE_FORM)

    def _show_state(self, index: int) -> None:
        self.state_stack.setCurrentIndex(index)

    # ------------------------------------------------------------------
    # Fetching
    # ------------------------------------------------------------------
    def _fetch(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return

        platform = self.platform_selector.value()
        mode = self.mode_selector.value()
        username = self.username_input.text().strip()
        url = self.url_input.text().strip()
        qdate = self.date_picker.date()

        if mode == "date" and (qdate is None or not qdate.isValid()):
            ToastManager.warning(self, "Please pick a date.")
            return
        date = (
            datetime.date(qdate.year(), qdate.month(), qdate.day())
            if qdate is not None and qdate.isValid()
            else datetime.date.today()
        )

        username_required = mode in ("recent", "date")
        if username_required and not username:
            ToastManager.warning(self, "Please enter a username.")
            self.username_input.setFocus()
            return

        game_id = ""
        if mode == "url":
            if not url:
                ToastManager.warning(self, "Please paste a game URL.")
                self.url_input.setFocus()
                return
            detected = self._platform_for_url(url)
            if detected is None:
                ToastManager.error(
                    self, "That link is not a Chess.com or Lichess game URL."
                )
                return
            if detected != platform:
                typed_username = username
                self.platform_selector.setValue(detected)
                self._on_platform_changed(detected)
                if typed_username:
                    self.username_input.setText(typed_username)
                platform = detected
                username = self.username_input.text().strip()

            if platform == "lichess":
                from src.backend.api.lichess_api import LichessAPI

                game_id = LichessAPI().extract_game_id(url)
            else:
                from src.backend.api.chess_com_api import ChessComAPI

                game_id = ChessComAPI.extract_game_id(url)

            if not game_id:
                ToastManager.error(self, "Could not read a game ID from that URL.")
                return

        self._last_query = {
            "platform": platform,
            "mode": mode,
            "username": username,
            "date": date,
            "url": url,
        }

        self._set_busy(True)
        self._skeleton._subtitle.setText(self._query_summary())
        self._skeleton.start()
        self._show_state(_STATE_LOADING)

        platform_label = "Lichess" if platform == "lichess" else "Chess.com"
        action = "game" if mode == "url" else "games"
        self._fetch_toast = ToastManager.loading(
            self, f"Fetching {action} from {platform_label}…"
        )

        limit = clamp_games_limit(
            self.config_manager.get("api_games_limit", 20),
            current_token(self.config_manager),
        )

        worker = ApiWorker(
            fetch_job,
            self.cache,
            mode,
            platform,
            username,
            date,
            url,
            game_id,
            limit,
        )
        self._worker = worker
        worker.completed.connect(
            lambda result, w=worker: self._on_fetch_completed(result, w)
        )
        worker.error.connect(
            lambda message, w=worker: self._on_fetch_error(message, w)
        )
        worker.finished.connect(lambda w=worker: remove_worker(w))
        register_worker(worker)
        worker.start()

    @staticmethod
    def _platform_for_url(url: str) -> str | None:
        lowered = url.lower()
        if "lichess.org" in lowered:
            return "lichess"
        if "chess.com" in lowered:
            return "chesscom"
        return None

    def _set_busy(self, busy: bool) -> None:
        self.fetch_btn.set_loading(busy)
        self.cancel_btn.setVisible(busy)
        self.username_input.setEnabled(not busy)
        self.url_input.setEnabled(not busy)
        self.date_picker.setEnabled(not busy)
        self.platform_selector.setEnabled(not busy)
        self.mode_selector.setEnabled(not busy)
        self.cancel_btn.setEnabled(busy)

    def _finish_loading(self) -> None:
        self._skeleton.stop()
        self._set_busy(False)
        self._worker = None

    def _on_fetch_completed(self, game_infos: list[GameInfo], worker: ApiWorker) -> None:
        if worker is not self._worker:
            return
        self._finish_loading()

        if not game_infos:
            self._show_state(_STATE_EMPTY)
            self._finish_fetch_toast(
                "No games found for that search.", "warning"
            )
            return

        self._parsed_games = game_infos
        rows = [self._game_row(info) for info in game_infos]
        count = len(game_infos)
        self._summary_label.setText(self._query_summary())
        self._count_badge.setText(f"{count} game" if count == 1 else f"{count} games")
        self._count_badge.set_tone("accent")
        self.game_list.populate(
            rows,
            "1 game ready to load:" if count == 1 else f"Select a game ({count} found):",
        )
        self.game_list.setVisible(True)
        self._show_state(_STATE_RESULTS)
        self._finish_fetch_toast(
            "1 game ready to load." if count == 1 else f"Found {count} games.",
            "success",
        )

    def _on_fetch_error(self, err_msg: str, worker: ApiWorker) -> None:
        if worker is not self._worker:
            return
        self._finish_loading()
        message = str(err_msg or "The request failed.")
        self._error_message.setText(message)
        self._show_state(_STATE_ERROR)
        self._finish_fetch_toast(f"Fetch failed: {message}", "error")

    def _finish_fetch_toast(self, message: str, variant: str) -> None:
        if self._fetch_toast is not None and self._fetch_toast.active:
            self._fetch_toast.update(message, variant=variant)
        else:
            ToastManager.show(self, message, variant)
        self._fetch_toast = None

    def _cancel_fetch(self, *, silent: bool = False, restore_form: bool = True) -> None:
        was_loading = self.state_stack.currentIndex() == _STATE_LOADING
        worker = self._worker
        if worker is not None:
            worker.cancel()
        self._worker = None
        self._finish_loading()
        if self._fetch_toast is not None:
            self._fetch_toast.dismiss()
            self._fetch_toast = None
        if restore_form or was_loading:
            self._show_state(_STATE_FORM)
        if not silent:
            ToastManager.info(self, "Fetch cancelled.")

    def _game_row(self, info: GameInfo) -> tuple[str, str]:
        return game_row(
            date=info.date,
            time_class=info.time_class,
            result=info.result,
            moves=info.move_count,
            white=info.white,
            black=info.black,
            white_elo=info.white_elo,
            black_elo=info.black_elo,
            opening=info.opening,
        )

    def _query_summary(self) -> str:
        query = self._last_query
        if not query:
            return ""
        platform = "Lichess" if query.get("platform") == "lichess" else "Chess.com"
        mode = query.get("mode")
        if mode == "url":
            return f"{platform} · game link"
        username = query.get("username") or "saved username"
        if mode == "date":
            date = query.get("date")
            return (
                f"{platform} · {username} · "
                f"{date.strftime('%b %d, %Y') if date else 'selected date'}"
            )
        return f"{platform} · {username} · recent games"

    def _on_game_chosen(self, index: int) -> None:
        if 0 <= index < len(self._parsed_games):
            info = self._parsed_games[index]
            self.pgn_ready.emit(info.pgn, info.to_dict())

    def _clear(self) -> None:
        self._cancel_fetch(silent=True)
        self._parsed_games = []
        self.game_list.setVisible(False)
        self.game_list.clear()
        self.url_input.clear()
        self._show_state(_STATE_FORM)
        self._on_platform_changed(self.platform_selector.value())
        self.pending_cleared.emit()

    def deactivate(self) -> None:
        """Called when another dialog tab becomes active; keep entered values."""
        self._cancel_fetch(silent=True, restore_form=False)

    def reset(self) -> None:
        self._clear()

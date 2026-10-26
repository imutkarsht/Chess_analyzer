"""
Unified Load Game Dialog
Replaces the fragmented dropdown menu + multiple OS dialogs with a single,
fully-styled modal that handles all load sources inline.
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.constants import SRC_CHESSCOM, SRC_LICHESS, SRC_PGN_FILE, SRC_PGN_TEXT
from src.gui.components import Tabs, TabVariant
from src.gui.styles import Styles
from src.gui.utils.gui_utils import create_button
from src.utils.path_utils import get_resource_path

from .load_game import (
    OnlineFetchPanel,
    PgnFilePanel,
    PgnTextPanel,
)

__all__ = [
    "LoadGameDialog",
    "SRC_CHESSCOM",
    "SRC_LICHESS",
    "SRC_PGN_FILE",
    "SRC_PGN_TEXT",
]


class LoadGameDialog(QDialog):
    """
    Unified dialog for loading games from all sources.
    Emits game_ready(pgn_text, source_data) when the user confirms a selection;
    the caller is responsible for parsing and loading the game.
    """
    # pgn_text: str, source_data: dict | None
    game_ready = pyqtSignal(str, object)

    def __init__(self, parent=None, initial_source: int = SRC_PGN_FILE):
        super().__init__(parent)
        self.setWindowTitle("Load Game")
        self.setModal(True)
        self.resize(680, 580)
        self.setMinimumSize(600, 480)

        self._already_accepted = False
        self._navigate_to_settings = False
        self._setup_ui()
        self._switch_source(initial_source)

    # ── UI construction ─────────────────────────────────────────────────────
    def _setup_ui(self):
        from PyQt6.QtCore import Qt as _Qt
        # Force Qt to honour the background-color on the dialog window itself
        self.setAttribute(_Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Styles.COLOR_BACKGROUND};
                border-radius: 12px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Title bar ───────────────────────────────────────────────────────
        title_bar = QWidget()
        title_bar.setFixedHeight(54)
        title_bar.setStyleSheet(
            f"background-color: {Styles.COLOR_SURFACE};"
            f"border-bottom: 1px solid {Styles.COLOR_BORDER};"
        )
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(20, 0, 16, 0)

        chess_icon = QLabel("♜")
        chess_icon.setStyleSheet(
            f"font-size: 20px; color: {Styles.COLOR_ACCENT}; background: transparent; border: none;"
        )
        tb_layout.addWidget(chess_icon)

        title_lbl = QLabel("Load Game")
        title_lbl.setStyleSheet(
            f"font-size: 17px; font-weight: 700; color: {Styles.COLOR_TEXT_PRIMARY};"
            " background: transparent; border: none;"
        )
        tb_layout.addWidget(title_lbl)
        tb_layout.addStretch()

        root.addWidget(title_bar)

        # ── Navigation bar ──────────────────────────────────────────────────
        nav_bar = QWidget()
        nav_bar.setFixedHeight(48)
        nav_bar.setStyleSheet(f"""
            QWidget {{
                background-color: {Styles.COLOR_SURFACE};
                border-bottom: 1px solid {Styles.COLOR_BORDER};
            }}
        """)
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(20, 0, 20, 0)
        nav_layout.setSpacing(12)

        # Tabs sit flush against the nav bar's bottom border, so the accent
        # underline reads as part of the divider.
        self.tabs = Tabs(
            TabVariant.UNDERLINE,
            active_style="accent",
            spacing=16,
            padding=(0, 16, 0, 16),
            font_size=14,
            icon_size=18,
        )
        self.tabs.add_tab("Online Fetch", icon="fa5s.globe")
        self.tabs.add_tab(
            "PGN Text / File",
            icon=QIcon(get_resource_path("assets/icons/file.png")),
        )
        self.tabs.current_changed.connect(self._on_tab_index_changed)
        self.tabs.setFixedHeight(48)
        nav_layout.addWidget(self.tabs, 1)

        root.addWidget(nav_bar)

        # ── Pages Stack ─────────────────────────────────────────────────────
        self.pages = QStackedWidget()
        self.pages.setStyleSheet("background-color: transparent;")

        # Page 1: Online Fetch
        self._online_fetch_panel = OnlineFetchPanel(self)
        self._online_fetch_panel.pgn_ready.connect(self._set_pending)
        self._online_fetch_panel.pending_cleared.connect(lambda: self._set_pending(None, None))
        self._online_fetch_panel.navigate_to_settings.connect(self._on_navigate_to_settings)
        self.pages.addWidget(self._online_fetch_panel)

        # Page 2: PGN Text / File (split side-by-side)
        tab2_widget = QWidget()
        tab2_layout = QHBoxLayout(tab2_widget)
        tab2_layout.setContentsMargins(16, 16, 16, 16)
        tab2_layout.setSpacing(16)

        self._pgn_file_panel = PgnFilePanel(self)
        self._pgn_file_panel.pgn_ready.connect(self._set_pending)
        self._pgn_file_panel.pending_cleared.connect(lambda: self._set_pending(None, None))
        tab2_layout.addWidget(self._pgn_file_panel, stretch=1)

        self._pgn_text_panel = PgnTextPanel(self)
        self._pgn_text_panel.pgn_ready.connect(self._set_pending)
        self._pgn_text_panel.pending_cleared.connect(lambda: self._set_pending(None, None))
        tab2_layout.addWidget(self._pgn_text_panel, stretch=1)

        self.pages.addWidget(tab2_widget)

        root.addWidget(self.pages, stretch=1)

        # ── Footer ──────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(64)
        footer.setStyleSheet(
            f"background-color: {Styles.COLOR_SURFACE};"
            f"border-top: 1px solid {Styles.COLOR_BORDER};"
        )
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 0, 20, 0)
        footer_layout.setSpacing(10)
        footer_layout.addStretch()

        btn_cancel = create_button("Cancel", style="secondary", on_click=self.reject)
        btn_cancel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        footer_layout.addWidget(btn_cancel)

        self.btn_load = create_button("Load Game", style="primary")
        self.btn_load.setEnabled(False)
        self.btn_load.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_load.clicked.connect(self._on_load_clicked)
        footer_layout.addWidget(self.btn_load)

        root.addWidget(footer)

        # Internal state
        self._pending_pgn = None
        self._pending_source_data = None

    # ── Tab switching ───────────────────────────────────────────────────────
    _TAB_KEYS = ("online", "pgn")

    def _on_tab_index_changed(self, index: int) -> None:
        if 0 <= index < len(self._TAB_KEYS):
            self._on_tab_changed(self._TAB_KEYS[index])

    def _on_tab_changed(self, tab_key: str):
        self._set_pending(None, None)
        if tab_key == "online":
            self.pages.setCurrentIndex(0)
            self._online_fetch_panel.reset()
        else:
            self.pages.setCurrentIndex(1)
            self._pgn_file_panel.reset()
            self._pgn_text_panel.reset()

    # ── Source switching ────────────────────────────────────────────────────
    def _switch_source(self, src_id: int):
        self._set_pending(None, None)
        if src_id in [SRC_CHESSCOM, SRC_LICHESS]:
            self.tabs.set_current_index(0)
            platform = "chesscom" if src_id == SRC_CHESSCOM else "lichess"
            self._online_fetch_panel.platform_selector.setValue(platform)
            self._online_fetch_panel._on_platform_changed(platform)
            self._online_fetch_panel.reset()
        else:
            self.tabs.set_current_index(1)
            self._pgn_file_panel.reset()
            self._pgn_text_panel.reset()

    # ── Load button state ───────────────────────────────────────────────────
    def _set_pending(self, pgn: str | None, source_data: dict | None):
        self._pending_pgn = pgn
        self._pending_source_data = source_data
        self.btn_load.setEnabled(pgn is not None and pgn.strip() != "")

    def _on_load_clicked(self):
        if self._already_accepted:
            return
        if self._pending_pgn:
            self._already_accepted = True
            self.game_ready.emit(self._pending_pgn, self._pending_source_data)
            self.accept()

    # ── Keyboard shortcuts ──────────────────────────────────────────────────
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() == Qt.Key.Key_Return and self.btn_load.isEnabled():
            self._on_load_clicked()
        else:
            super().keyPressEvent(event)

    def _on_navigate_to_settings(self):
        self._navigate_to_settings = True
        self.accept()

    def accept(self):
        if not self._already_accepted:
            self._already_accepted = True
        self._cleanup_workers()
        super().accept()

    def reject(self):
        self._cleanup_workers()
        super().reject()

    def _cleanup_workers(self):
        if hasattr(self, '_online_fetch_panel') and self._online_fetch_panel._worker is not None:
            try:
                self._online_fetch_panel._worker.cancel()
                self._online_fetch_panel._worker.finished.disconnect()
                self._online_fetch_panel._worker.error.disconnect()
            except (TypeError, RuntimeError):
                pass

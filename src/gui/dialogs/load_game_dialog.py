"""
Unified Load Game dialog.

One modal for online fetches and local PGN files, with a shadcn-style shell:
title + description, source tabs, content, and a sticky footer.
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
from src.gui.components import (
    Button,
    ButtonSize,
    ButtonVariant,
    SegmentedControl,
    Tabs,
    TabVariant,
)
from src.gui.styles import Styles
from src.utils.path_utils import get_resource_path

from .load_game import OnlineFetchPanel, PgnFilePanel, PgnTextPanel

__all__ = [
    "LoadGameDialog",
    "SRC_CHESSCOM",
    "SRC_LICHESS",
    "SRC_PGN_FILE",
    "SRC_PGN_TEXT",
]


class LoadGameDialog(QDialog):
    """Load a game from Chess.com, Lichess, a PGN file, or pasted PGN text."""

    # pgn_text: str, source_data: dict | None
    game_ready = pyqtSignal(str, object)

    def __init__(self, parent=None, initial_source: int = SRC_PGN_FILE):
        super().__init__(parent)
        self.setWindowTitle("Load Game")
        self.setModal(True)
        self.resize(640, 560)
        self.setMinimumSize(640, 560)

        self._already_accepted = False
        self._navigate_to_settings = False
        self._setup_ui()
        self._switch_source(initial_source)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {Styles.COLOR_BACKGROUND};
            }}
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_tabs())

        self.pages = QStackedWidget()
        self.pages.setStyleSheet("background-color: transparent;")

        self._online_fetch_panel = OnlineFetchPanel(self)
        self._online_fetch_panel.pgn_ready.connect(self._set_pending)
        self._online_fetch_panel.pending_cleared.connect(
            lambda: self._set_pending(None, None)
        )
        self._online_fetch_panel.navigate_to_settings.connect(
            self._on_navigate_to_settings
        )
        self.pages.addWidget(self._online_fetch_panel)
        self.pages.addWidget(self._build_pgn_page())

        root.addWidget(self.pages, 1)
        root.addWidget(self._build_footer())

        self._pending_pgn = None
        self._pending_source_data = None

    def _build_header(self) -> QWidget:
        header = QWidget()
        layout = QVBoxLayout(header)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(4)

        title = QLabel("Import game")
        title.setStyleSheet(
            f"font-size: 20px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY};"
            " background: transparent;"
        )
        description = QLabel(
            "Fetch a game from Chess.com or Lichess, or load a PGN file."
        )
        description.setStyleSheet(
            f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY};"
            " background: transparent;"
        )
        layout.addWidget(title)
        layout.addWidget(description)
        return header

    def _build_tabs(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(
            f"border-bottom: 1px solid {Styles.COLOR_BORDER}; background: transparent;"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(12)

        self.tabs = Tabs(
            TabVariant.UNDERLINE,
            active_style="accent",
            spacing=16,
            padding=(0, 12, 0, 12),
            font_size=13,
            icon_size=16,
        )
        self.tabs.add_tab("Online", icon="fa5s.globe")
        self.tabs.add_tab(
            "PGN",
            icon=QIcon(get_resource_path("assets/icons/file.png")),
        )
        self.tabs.current_changed.connect(self._on_tab_index_changed)
        self.tabs.setFixedHeight(44)
        layout.addWidget(self.tabs, 1)
        return bar

    def _build_pgn_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 12, 24, 16)
        layout.setSpacing(12)

        self.pgn_mode = SegmentedControl(
            [("File", "file"), ("Text", "text")], value="file"
        )
        self.pgn_mode.valueChanged.connect(self._on_pgn_mode_changed)
        mode_row = QHBoxLayout()
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.addWidget(self.pgn_mode)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        self.pgn_stack = QStackedWidget()
        self._pgn_file_panel = PgnFilePanel(self)
        self._pgn_file_panel.pgn_ready.connect(self._set_pending)
        self._pgn_file_panel.pending_cleared.connect(
            lambda: self._set_pending(None, None)
        )
        self._pgn_text_panel = PgnTextPanel(self)
        self._pgn_text_panel.pgn_ready.connect(self._set_pending)
        self._pgn_text_panel.pending_cleared.connect(
            lambda: self._set_pending(None, None)
        )
        self.pgn_stack.addWidget(self._pgn_file_panel)
        self.pgn_stack.addWidget(self._pgn_text_panel)
        layout.addWidget(self.pgn_stack, 1)
        return page

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setFixedHeight(64)
        footer.setStyleSheet(
            f"background-color: {Styles.COLOR_SURFACE};"
            f"border-top: 1px solid {Styles.COLOR_BORDER};"
        )
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(8)
        layout.addStretch(1)

        cancel = Button(
            "Cancel",
            ButtonVariant.HOLLOW,
            ButtonSize.MD,
            on_click=self.reject,
        )
        cancel.setMinimumWidth(92)
        layout.addWidget(cancel)

        self.btn_load = Button(
            "Load game",
            ButtonVariant.PRIMARY,
            ButtonSize.MD,
            on_click=self._on_load_clicked,
        )
        self.btn_load.setEnabled(False)
        self.btn_load.setMinimumWidth(110)
        layout.addWidget(self.btn_load)
        return footer

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    _TAB_KEYS = ("online", "pgn")

    def _on_tab_index_changed(self, index: int) -> None:
        if 0 <= index < len(self._TAB_KEYS):
            self._on_tab_changed(self._TAB_KEYS[index])

    def _on_tab_changed(self, tab_key: str) -> None:
        if tab_key == "online":
            self.pages.setCurrentIndex(0)
        else:
            self._online_fetch_panel.deactivate()
            self.pages.setCurrentIndex(1)

    def _on_pgn_mode_changed(self, mode: str) -> None:
        self.pgn_stack.setCurrentIndex(0 if mode == "file" else 1)

    def _switch_source(self, src_id: int) -> None:
        self._set_pending(None, None)
        if src_id in (SRC_CHESSCOM, SRC_LICHESS):
            self.tabs.set_current_index(0)
            platform = "chesscom" if src_id == SRC_CHESSCOM else "lichess"
            self._online_fetch_panel.platform_selector.setValue(platform)
            self._online_fetch_panel._on_platform_changed(platform)
        else:
            self.tabs.set_current_index(1)
            mode = "text" if src_id == SRC_PGN_TEXT else "file"
            self.pgn_mode.set_value(mode)
            self._on_pgn_mode_changed(mode)

    # ------------------------------------------------------------------
    # Pending selection
    # ------------------------------------------------------------------
    def _set_pending(self, pgn: str | None, source_data: dict | None) -> None:
        self._pending_pgn = pgn
        self._pending_source_data = source_data
        self.btn_load.setEnabled(pgn is not None and pgn.strip() != "")

    def _on_load_clicked(self) -> None:
        if self._already_accepted:
            return
        if self._pending_pgn:
            self._already_accepted = True
            self.game_ready.emit(self._pending_pgn, self._pending_source_data)
            self.accept()

    # ------------------------------------------------------------------
    # Keyboard / lifecycle
    # ------------------------------------------------------------------
    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() == Qt.Key.Key_Return and self.btn_load.isEnabled():
            self._on_load_clicked()
        else:
            super().keyPressEvent(event)

    def _on_navigate_to_settings(self) -> None:
        self._navigate_to_settings = True
        self.accept()

    def accept(self) -> None:
        self._already_accepted = True
        self._cleanup_workers()
        super().accept()

    def reject(self) -> None:
        self._cleanup_workers()
        super().reject()

    def _cleanup_workers(self) -> None:
        if hasattr(self, "_online_fetch_panel"):
            self._online_fetch_panel.deactivate()

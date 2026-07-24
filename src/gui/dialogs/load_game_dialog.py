"""
Unified Load Game Dialog
Replaces the fragmented dropdown menu + multiple OS dialogs with a single,
fully-styled modal that handles all load sources inline.
"""
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QStackedWidget, QLabel, QWidget
from PyQt6.QtCore import Qt, pyqtSignal

from src.gui.styles import Styles
from src.gui.utils.gui_utils import create_button

from src.constants import SRC_PGN_FILE, SRC_PGN_TEXT, SRC_CHESSCOM, SRC_LICHESS

from .load_game import (
    SourceBtn,
    PgnFilePanel,
    PgnTextPanel,
    ChessComPanel,
    LichessPanel,
    icon_path,
)

_SOURCES = [
    (SRC_PGN_FILE,  "📂",  "PGN File",   None),
    (SRC_PGN_TEXT,  "📋",  "PGN Text",   None),
    (SRC_CHESSCOM,  None,  "Chess.com",  icon_path("chesscom.png")),
    (SRC_LICHESS,   None,  "Lichess",    icon_path("lichess.png")),
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
        self.resize(760, 560)
        self.setMinimumSize(680, 480)

        self._already_accepted = False
        self._navigate_to_settings = False
        self._source_btns: list[SourceBtn] = []
        self._setup_ui()
        self._switch_source(initial_source)

    # ── UI construction ─────────────────────────────────────────────────────
    def _setup_ui(self):
        from PyQt6.QtCore import Qt as _Qt
        from src.gui.styles import Styles
        # Force Qt to honour the background-color on the dialog window itself
        # (macOS ignores it without this attribute)
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
            f"font-size: 20px; color: {Styles.COLOR_ACCENT}; background: transparent;"
        )
        tb_layout.addWidget(chess_icon)

        title_lbl = QLabel("Load Game")
        title_lbl.setStyleSheet(
            f"font-size: 17px; font-weight: 700; color: {Styles.COLOR_TEXT_PRIMARY};"
            " background: transparent;"
        )
        tb_layout.addWidget(title_lbl)
        tb_layout.addStretch()

        root.addWidget(title_bar)

        # ── Body (left source list + right stacked panel) ───────────────────
        body = QWidget()
        body.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND};")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Left source selector
        left_panel = QWidget()
        left_panel.setFixedWidth(190)
        left_panel.setStyleSheet(
            f"background-color: {Styles.COLOR_SURFACE};"
            f"border-right: 1px solid {Styles.COLOR_BORDER};"
        )
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 18, 10, 18)
        left_layout.setSpacing(4)

        src_header = QLabel("SOURCE")
        src_header.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 1.2px;"
            f"color: {Styles.COLOR_TEXT_MUTED}; background: transparent;"
            " padding-left: 6px; margin-bottom: 6px;"
        )
        left_layout.addWidget(src_header)

        for src_id, emoji, label, icon_path_val in _SOURCES:
            btn = SourceBtn(emoji, label, icon_path=icon_path_val)
            btn.clicked.connect(lambda checked, sid=src_id: self._switch_source(sid))
            self._source_btns.append(btn)
            left_layout.addWidget(btn)

        left_layout.addStretch()
        body_layout.addWidget(left_panel)

        # Right stacked panel
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background-color: transparent;")
        self._build_panels()
        body_layout.addWidget(self.stack, stretch=1)

        root.addWidget(body, stretch=1)

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
        self._pending_pgn: str | None = None
        self._pending_source_data: dict | None = None

    # ── Panel construction ──────────────────────────────────────────────────
    def _build_panels(self):
        # PGN File
        self._pgn_file_panel = PgnFilePanel()
        self._pgn_file_panel.pgn_ready.connect(
            lambda pgn, sd: self._set_pending(pgn, sd)
        )
        self._pgn_file_panel.pending_cleared.connect(
            lambda: self._set_pending(None, None)
        )
        self.stack.addWidget(self._pgn_file_panel)   # index 0

        # PGN Text
        self._pgn_text_panel = PgnTextPanel()
        self._pgn_text_panel.pgn_ready.connect(
            lambda pgn, sd: self._set_pending(pgn, sd)
        )
        self._pgn_text_panel.pending_cleared.connect(
            lambda: self._set_pending(None, None)
        )
        self.stack.addWidget(self._pgn_text_panel)   # index 1

        # Chess.com
        self._chesscom_panel = ChessComPanel()
        self._chesscom_panel.pgn_ready.connect(
            lambda pgn, sd: self._set_pending(pgn, sd)
        )
        self._chesscom_panel.pending_cleared.connect(
            lambda: self._set_pending(None, None)
        )
        self._chesscom_panel.navigate_to_settings.connect(self._on_navigate_to_settings)
        self.stack.addWidget(self._chesscom_panel)   # index 2

        # Lichess
        self._lichess_panel = LichessPanel()
        self._lichess_panel.pgn_ready.connect(
            lambda pgn, sd: self._set_pending(pgn, sd)
        )
        self._lichess_panel.pending_cleared.connect(
            lambda: self._set_pending(None, None)
        )
        self._lichess_panel.navigate_to_settings.connect(self._on_navigate_to_settings)
        self.stack.addWidget(self._lichess_panel)    # index 3

    # ── Source switching ────────────────────────────────────────────────────
    def _switch_source(self, src_id: int):
        for i, btn in enumerate(self._source_btns):
            btn.setChecked(i == src_id)
        self.stack.setCurrentIndex(src_id)
        self._set_pending(None, None)

        # Reset panels when leaving them
        if src_id != SRC_PGN_FILE:
            self._pgn_file_panel.reset()
        if src_id != SRC_PGN_TEXT:
            self._pgn_text_panel.reset()
        if src_id != SRC_CHESSCOM:
            self._chesscom_panel.reset()
        if src_id != SRC_LICHESS:
            self._lichess_panel.reset()

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
        for panel in [self._chesscom_panel, self._lichess_panel]:
            if hasattr(panel, '_worker') and panel._worker is not None:
                try:
                    panel._worker.finished.disconnect()
                    panel._worker.error.disconnect()
                except (TypeError, RuntimeError):
                    pass

"""
PGN File panel for the Load Game dialog.
"""
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget

from src.gui.components import Button, ButtonSize, ButtonVariant
from src.gui.components.toast import ToastManager

from .drop_zone import DropZone
from .helpers import classify_time_control, game_row
from .inline_game_list import InlineGameList


class PgnFilePanel(QWidget):
    """
    Right-panel page for 'PGN File' source.
    Handles drag & drop and browse. For multi-game files shows an inline
    game picker; for single-game files sets the game ready immediately.
    """
    pgn_ready     = pyqtSignal(str, object)   # (pgn_text, None)
    pending_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parsed_games: list = []          # GameAnalysis objects
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # ── Drop zone ───────────────────────────────────────────────────────
        self._drop_zone = DropZone()
        self._drop_zone.setMinimumHeight(190)
        self._drop_zone.setMaximumHeight(240)
        self._drop_zone.file_dropped.connect(self._load_file)
        self._drop_zone.clicked.connect(self._browse)
        root.addWidget(self._drop_zone)

        # ── Browse button ────────────────────────────────────────────────────
        self._browse_btn = Button(
            "Browse files",
            ButtonVariant.HOLLOW,
            ButtonSize.MD,
            icon="fa5s.folder-open",
            on_click=self._browse,
        )
        self._browse_btn.setMaximumWidth(180)
        browse_row = QHBoxLayout()
        browse_row.setContentsMargins(0, 0, 0, 0)
        browse_row.addStretch(1)
        browse_row.addWidget(self._browse_btn)
        browse_row.addStretch(1)
        root.addLayout(browse_row)

        # ── Inline game list (shown after load) ───────────────
        self._game_list = InlineGameList()
        self._game_list.setVisible(False)
        self._game_list.game_chosen.connect(self._on_game_chosen)
        self._game_list.cleared.connect(self._clear)
        root.addWidget(self._game_list, stretch=1)

    # ── File loading ────────────────────────────────────────────────────────
    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PGN File", "", "PGN Files (*.pgn);;All Files (*)"
        )
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        from src.backend.storage.pgn_parser import PGNParser
        try:
            games = PGNParser.parse_pgn_file(path)
        except Exception:
            ToastManager.error(
                self, "Could not read this PGN. It may be empty or corrupted."
            )
            return

        if not games:
            ToastManager.warning(self, "No valid games found in this file.")
            return

        self._parsed_games = games
        n = len(games)

        self._drop_zone.setVisible(False)
        self._browse_btn.setVisible(False)

        rows = []
        for g in games:
            md = g.metadata
            rows.append(
                game_row(
                    date=md.date or md.headers.get("Date"),
                    time_class=classify_time_control(
                        md.headers.get("TimeControl", "")
                    ),
                    result=md.result,
                    moves=(len(g.moves) + 1) // 2,
                    white=md.white,
                    black=md.black,
                    white_elo=md.white_elo or md.headers.get("WhiteElo"),
                    black_elo=md.black_elo or md.headers.get("BlackElo"),
                    opening=getattr(md, "opening", None)
                    or md.headers.get("Opening"),
                )
            )

        header_text = "1 game ready to load:" if n == 1 else f"Select a game ({n} found):"
        self._game_list.populate(rows, header_text)
        self._game_list.setVisible(True)

    def _on_game_chosen(self, index: int):
        if 0 <= index < len(self._parsed_games):
            game = self._parsed_games[index]
            self.pgn_ready.emit(game.pgn_content or "", None)

    def _clear(self):
        self._parsed_games = []
        self._game_list.setVisible(False)
        self._game_list.clear()
        self._drop_zone.setVisible(True)
        self._browse_btn.setVisible(True)
        self._drop_zone._set_idle()
        self.pending_cleared.emit()

    def reset(self):
        """Called when the user switches away from this source tab."""
        self._clear()

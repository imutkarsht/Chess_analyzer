"""
PGN File panel for the Load Game dialog.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QFileDialog, QMessageBox
from PyQt6.QtCore import pyqtSignal, Qt
from .drop_zone import DropZone
from .inline_game_list import InlineGameList
from .helpers import classify_time_control
from src.gui.utils.gui_utils import create_button

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
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        # ── Drop zone ───────────────────────────────────────────────────────
        self._drop_zone = DropZone()
        self._drop_zone.file_dropped.connect(self._load_file)
        self._drop_zone.clicked.connect(self._browse)
        root.addWidget(self._drop_zone)

        # ── Browse button ────────────────────────────────────────────────────
        browse_btn = create_button("Browse for .pgn file…", style="secondary",
                                   on_click=self._browse)
        browse_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        browse_btn.setFixedHeight(36)
        root.addWidget(browse_btn)

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
        except Exception as e:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Could Not Read PGN")
            msg.setText("Could not read this PGN.\nIt may be empty or corrupted.")
            try_again = msg.addButton("Try Another File", QMessageBox.ButtonRole.ActionRole)
            msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            if msg.clickedButton() == try_again:
                self._browse()
            return

        if not games:
            QMessageBox.warning(self, "No Games", "No valid games found in this file.")
            return

        self._parsed_games = games
        n = len(games)
        
        self._drop_zone.setVisible(False)

        rows = []
        for g in games:
            md = g.metadata
            white = md.white or "?"
            black = md.black or "?"
            w_elo = md.white_elo or md.headers.get("WhiteElo", "?")
            b_elo = md.black_elo or md.headers.get("BlackElo", "?")
            result = md.result or "?"
            date = md.date or md.headers.get("Date", "?")
            time_ctrl = md.headers.get("TimeControl", "")
            tc_label = classify_time_control(time_ctrl)
            move_count = (len(g.moves) + 1) // 2

            line1 = f"{date}  ·  {tc_label}  ·  {result}  ·  {move_count} moves"
            line2 = f"{white} ({w_elo})  vs  {black} ({b_elo})"
            rows.append((line1, line2))

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
        self._drop_zone._set_idle()
        self.pending_cleared.emit()

    def reset(self):
        """Called when the user switches away from this source tab."""
        self._clear()

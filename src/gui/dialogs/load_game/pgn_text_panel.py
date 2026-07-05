"""
PGN Text panel for the Load Game dialog.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QMessageBox
from PyQt6.QtCore import pyqtSignal, Qt
from src.gui.styles import Styles
from src.gui.utils.gui_utils import create_button
from .inline_game_list import InlineGameList
from .helpers import classify_time_control

class PgnTextPanel(QWidget):
    """
    Right-panel page for 'PGN Text' source.
    Handles pasting PGN text and parsing it. Like the file panel,
    single games load immediately, multiple games show a picker.
    """
    pgn_ready     = pyqtSignal(str, object)   # (pgn_text, None)
    pending_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parsed_games: list = []
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        # ── Input Area ──────────────────────────────────────────────────────
        self._input_widget = QWidget()
        input_layout = QVBoxLayout(self._input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(12)

        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText("Paste your PGN text here...")
        self._text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 12px;
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-family: monospace;
                font-size: 13px;
            }}
            QTextEdit:focus {{
                border: 1px solid {Styles.COLOR_ACCENT};
            }}
        """)
        input_layout.addWidget(self._text_edit)

        parse_btn = create_button("Parse PGN", style="secondary", on_click=self._parse)
        parse_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        parse_btn.setFixedHeight(36)
        input_layout.addWidget(parse_btn)

        root.addWidget(self._input_widget, stretch=1)

        # ── Inline game list (shown after load) ────────────────
        self._game_list = InlineGameList()
        self._game_list.setVisible(False)
        self._game_list.game_chosen.connect(self._on_game_chosen)
        self._game_list.cleared.connect(self._clear)
        root.addWidget(self._game_list, stretch=1)

    # ── Text parsing ────────────────────────────────────────────────────────
    def _parse(self):
        text = self._text_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Empty", "Please paste some PGN text first.")
            return

        from src.backend.storage.pgn_parser import PGNParser
        try:
            games = PGNParser.parse_pgn_text(text)
        except Exception as e:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Could Not Read PGN")
            msg.setText("Could not read this PGN.\nIt may be empty or corrupted.")
            try_again = msg.addButton("Try Again", QMessageBox.ButtonRole.ActionRole)
            msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            if msg.clickedButton() == try_again:
                self._text_edit.clear()
                self._text_edit.setFocus()
            return

        if not games:
            QMessageBox.warning(self, "No Games", "No valid games found in this text.")
            return

        self._parsed_games = games
        n = len(games)

        self._input_widget.setVisible(False)

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
            self.pgn_ready.emit(game.pgn_content or self._text_edit.toPlainText(), None)

    def _clear(self):
        self._parsed_games = []
        self._text_edit.clear()
        self._game_list.setVisible(False)
        self._game_list.clear()
        self._input_widget.setVisible(True)
        self.pending_cleared.emit()

    def reset(self):
        """Called when the user switches away from this source tab."""
        self._clear()

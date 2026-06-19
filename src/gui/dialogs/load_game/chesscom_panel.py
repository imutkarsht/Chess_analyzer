"""
Chess.com API Panel for the Load Game dialog.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox
from PyQt6.QtCore import pyqtSignal, Qt
from src.gui.styles import Styles
from src.gui.utils.gui_utils import create_button
from ....utils.config import ConfigManager
from .inline_game_list import InlineGameList
from .helpers import classify_time_control
from .api_worker import ApiWorker, register_worker, remove_worker

def fetch_and_parse_chesscom(username: str, limit: int) -> list:
    from src.backend.api.chess_com_api import ChessComAPI
    from src.backend.storage.pgn_parser import PGNParser
    
    raw_games = ChessComAPI.get_last_games(username, limit)
    parsed_games = []
    for g_data in raw_games:
        pgn = g_data.get("pgn", "")
        if not pgn:
            continue
        try:
            parsed_list = PGNParser.parse_pgn_text(pgn)
            if parsed_list:
                parsed_games.append((parsed_list[0], g_data))
        except Exception:
            continue
    return parsed_games


def fetch_single_chesscom(game_id: str, url: str) -> list:
    from src.backend.api.chess_com_api import ChessComAPI
    from src.backend.storage.pgn_parser import PGNParser
    
    result = ChessComAPI.get_game_by_id(game_id, url)
    if not result:
        return []
        
    pgn = result.get("pgn", "")
    if pgn:
        try:
            parsed_list = PGNParser.parse_pgn_text(pgn)
            if parsed_list:
                return [(parsed_list[0], result)]
        except Exception:
            pass
    return []


class ChessComPanel(QWidget):
    """
    Right-panel page for 'Chess.com' source.
    Fetches games by username or game URL asynchronously.
    """
    pgn_ready     = pyqtSignal(str, object)
    pending_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parsed_games: list = []  # List of (GameAnalysis, source_dict)
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        # ── Input Area ──────────────────────────────────────────────────────
        self._input_widget = QWidget()
        input_layout = QVBoxLayout(self._input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)

        lbl = QLabel("Enter Username or Game URL:")
        lbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY};")
        input_layout.addWidget(lbl)

        # HBox for LineEdit + Fetch Button
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self._input_edit = QLineEdit()
        self._input_edit.setPlaceholderText("e.g. Hikaru  or  https://www.chess.com/game/...")
        
        saved_username = ConfigManager().get("chesscom_username", "")
        if saved_username:
            self._input_edit.setText(saved_username)

        self._input_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 0 12px;
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 13px;
                height: 36px;
            }}
            QLineEdit:focus {{
                border: 1px solid {Styles.COLOR_ACCENT};
            }}
        """)
        self._input_edit.returnPressed.connect(self._fetch)
        input_row.addWidget(self._input_edit, stretch=1)

        self._fetch_btn = create_button("Fetch", style="secondary", on_click=self._fetch)
        self._fetch_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._fetch_btn.setFixedWidth(80)
        self._fetch_btn.setFixedHeight(36)
        input_row.addWidget(self._fetch_btn)

        input_layout.addLayout(input_row)

        # Helper text
        self._help_lbl = QLabel()
        self._help_lbl.setStyleSheet(f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY};")
        self.update_help_label()
        input_layout.addWidget(self._help_lbl)
        
        input_layout.addStretch()
        root.addWidget(self._input_widget, stretch=1)

        # ── Inline game list (shown after load) ──────────────────────────────
        self._game_list = InlineGameList()
        self._game_list.setVisible(False)
        self._game_list.game_chosen.connect(self._on_game_chosen)
        self._game_list.cleared.connect(self._clear)
        root.addWidget(self._game_list, stretch=1)

    def update_help_label(self):
        limit = ConfigManager().get("api_games_limit", 20)
        self._help_lbl.setText(f"Fetches the last {limit} games for a username.")

    # ── Fetching ─────────────────────────────────────────────────────────────
    def _fetch(self):
        text = self._input_edit.text().strip()
        if not text:
            return

        self._fetch_btn.setEnabled(False)
        self._fetch_btn.setText("...")
        self._input_edit.setEnabled(False)

        # Disconnect any previously running worker
        if self._worker is not None and self._worker.isRunning():
            try:
                self._worker.finished.disconnect()
                self._worker.error.disconnect()
            except (TypeError, RuntimeError):
                pass

        from src.backend.api.chess_com_api import ChessComAPI
        
        game_id = ChessComAPI.extract_game_id(text)
        if game_id:
            # It's a URL
            self._worker = ApiWorker(fetch_single_chesscom, game_id, text, parent=self)
        else:
            # It's a username
            limit = ConfigManager().get("api_games_limit", 20)
            self._worker = ApiWorker(fetch_and_parse_chesscom, text, limit, parent=self)

        register_worker(self._worker)
        self._worker.finished.connect(lambda: remove_worker(self._worker))
        self._worker.error.connect(lambda: remove_worker(self._worker))

        self._worker.finished.connect(self._on_fetch_finished)
        self._worker.error.connect(self._on_fetch_error)
        self._worker.start()

    def _on_fetch_error(self, err_msg: str):
        self._reset_input_ui()
        QMessageBox.critical(self, "API Error", f"Failed to fetch from Chess.com:\n{err_msg}")

    def _on_fetch_finished(self, parsed_games):
        self._reset_input_ui()

        if not parsed_games:
            QMessageBox.warning(self, "No Games", "No games found.")
            return

        self._parsed_games = parsed_games
        rows = []
        
        for game_obj, g_data in parsed_games:
            # Build display row from PGN metadata
            md = game_obj.metadata
            white = md.white or "?"
            black = md.black or "?"
            w_elo = md.white_elo or md.headers.get("WhiteElo", "?")
            b_elo = md.black_elo or md.headers.get("BlackElo", "?")
            result = md.result or "?"
            date = md.date or md.headers.get("Date", "?")
            time_ctrl = md.headers.get("TimeControl", "")
            tc_label = classify_time_control(time_ctrl)
            move_count = (len(game_obj.moves) + 1) // 2

            line1 = f"{date}  ·  {tc_label}  ·  {result}  ·  {move_count} moves"
            line2 = f"{white} ({w_elo})  vs  {black} ({b_elo})"
            rows.append((line1, line2))

        n = len(self._parsed_games)
        if n == 0:
            QMessageBox.warning(self, "Parse Error", "Failed to parse fetched games.")
            return

        self._input_widget.setVisible(False)
        header_text = "1 game ready to load:" if n == 1 else f"Select a game ({n} found):"
        self._game_list.populate(rows, header_text)
        self._game_list.setVisible(True)

    def _reset_input_ui(self):
        self._fetch_btn.setEnabled(True)
        self._fetch_btn.setText("Fetch")
        self._input_edit.setEnabled(True)

    def _on_game_chosen(self, index: int):
        if 0 <= index < len(self._parsed_games):
            game_obj, source_data = self._parsed_games[index]
            self.pgn_ready.emit(game_obj.pgn_content, source_data)

    def _clear(self):
        self._parsed_games = []
        self._game_list.setVisible(False)
        self._game_list.clear()
        self._input_widget.setVisible(True)
        self.update_help_label()
        
        saved_username = ConfigManager().get("chesscom_username", "")
        self._input_edit.setText(saved_username)
        
        self._input_edit.setFocus()
        self.pending_cleared.emit()

    def reset(self):
        self._clear()

"""
PGN Text panel for the Load Game dialog.
"""
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.gui.components import Button, ButtonSize, ButtonVariant, TextArea
from src.gui.components.feedback.toast import ToastManager
from src.gui.styles import Styles

from .helpers import classify_time_control, game_row
from .inline_game_list import InlineGameList


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
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # ── Input Area ──────────────────────────────────────────────────────
        self._input_widget = QWidget()
        input_layout = QVBoxLayout(self._input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        label = QLabel("PGN text")
        label.setStyleSheet(
            f"font-size: 12px; font-weight: 500; color: {Styles.COLOR_TEXT_PRIMARY};"
            " background: transparent;"
        )
        self._paste_btn = Button(
            "Paste from clipboard",
            ButtonVariant.GHOST,
            ButtonSize.XS,
            icon="fa5s.paste",
            on_click=self._paste_clipboard,
        )
        header.addWidget(label)
        header.addStretch(1)
        header.addWidget(self._paste_btn)
        input_layout.addLayout(header)

        self._text_edit = TextArea(
            placeholder="Paste a game's PGN here — headers and moves are both fine.",
            variant="code",
        )
        input_layout.addWidget(self._text_edit, 1)

        parse_btn = Button(
            "Parse PGN",
            ButtonVariant.PRIMARY,
            ButtonSize.MD,
            icon="fa5s.check",
            on_click=self._parse,
        )
        parse_row = QHBoxLayout()
        parse_row.addStretch(1)
        parse_row.addWidget(parse_btn)
        input_layout.addLayout(parse_row)

        root.addWidget(self._input_widget, stretch=1)

        # ── Inline game list (shown after load) ────────────────
        self._game_list = InlineGameList()
        self._game_list.setVisible(False)
        self._game_list.game_chosen.connect(self._on_game_chosen)
        self._game_list.cleared.connect(self._clear)
        root.addWidget(self._game_list, stretch=1)

    def _paste_clipboard(self) -> None:
        text = QApplication.clipboard().text().strip()
        if text:
            self._text_edit.setPlainText(text)

    # ── Text parsing ────────────────────────────────────────────────────────
    def _parse(self):
        text = self._text_edit.toPlainText().strip()
        if not text:
            ToastManager.warning(self, "Please paste some PGN text first.")
            return

        from src.backend.storage.pgn_parser import PGNParser
        try:
            games = PGNParser.parse_pgn_text(text)
        except Exception:
            ToastManager.error(
                self, "Could not parse this PGN. It may be empty or corrupted."
            )
            return

        if not games:
            ToastManager.warning(self, "No valid games found in this text.")
            return

        self._parsed_games = games
        n = len(games)

        self._input_widget.setVisible(False)

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
        self._text_edit.clear()
        self._game_list.setVisible(False)
        self._game_list.clear()
        self._input_widget.setVisible(True)
        self.pending_cleared.emit()

    def reset(self):
        """Called when the user switches away from this source tab."""
        self._clear()

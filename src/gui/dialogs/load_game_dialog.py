"""
Unified Load Game Dialog
Replaces the fragmented dropdown menu + multiple OS dialogs with a single,
fully-styled modal that handles all load sources inline.
"""
import os
import os
import os
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QLabel, QPushButton, QWidget, QFrame, QSizePolicy,
    QScrollArea, QFileDialog, QMessageBox, QTextEdit, QLineEdit,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QMimeData, QThread
from PyQt6.QtGui import QFont, QColor, QPixmap, QDragEnterEvent, QDropEvent

from ..styles import Styles
from ..gui_utils import create_button
from ...utils.path_utils import get_resource_path
from ...utils.config import ConfigManager


# ── Source IDs ─────────────────────────────────────────────────────────────────
SRC_PGN_FILE  = 0
SRC_PGN_TEXT  = 1
SRC_CHESSCOM  = 2
SRC_LICHESS   = 3

def _icon_path(filename: str) -> str:
    return get_resource_path(os.path.join("assets", "icons", filename))

_SOURCES = [
    (SRC_PGN_FILE,  "📂",  "PGN File",   None),
    (SRC_PGN_TEXT,  "📋",  "PGN Text",   None),
    (SRC_CHESSCOM,  None,  "Chess.com",  _icon_path("chesscom.png")),
    (SRC_LICHESS,   None,  "Lichess",    _icon_path("lichess.png")),
]


# ── Source selector button ──────────────────────────────────────────────────────
class _SourceBtn(QPushButton):
    def __init__(self, emoji: str | None, label: str,
                 icon_path: str | None = None, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(54)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(10)

        # Icon: prefer brand image, fall back to emoji
        if icon_path and os.path.exists(icon_path):
            lbl_icon = QLabel()
            pix = QPixmap(icon_path).scaled(
                22, 22,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            lbl_icon.setPixmap(pix)
            lbl_icon.setFixedSize(22, 22)
        else:
            lbl_icon = QLabel(emoji or "")
            lbl_icon.setStyleSheet("font-size: 18px; background: transparent; border: none;")

        lbl_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(lbl_icon)

        lbl_text = QLabel(label)
        lbl_text.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY};"
            " background: transparent; border: none;"
        )
        lbl_text.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(lbl_text)
        layout.addStretch()

        self._apply_style(False)

    def _apply_style(self, checked: bool):
        if checked:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Styles.COLOR_ACCENT_SUBTLE};
                    border: none;
                    border-left: 3px solid {Styles.COLOR_ACCENT};
                    border-radius: 8px;
                    text-align: left;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    border-left: 3px solid transparent;
                    border-radius: 8px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                }}
            """)

    def setChecked(self, checked: bool):
        super().setChecked(checked)
        self._apply_style(checked)


# ── API Worker for background fetching ──────────────────────────────────────────
class _ApiWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, api_func, *args, **kwargs):
        super().__init__()
        self.api_func = api_func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            res = self.api_func(*self.args, **self.kwargs)
            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))


# ── Drag & Drop zone ────────────────────────────────────────────────────────────
class _DropZone(QLabel):
    """Dashed-border drop target for .pgn files. Emits file_dropped(path)."""
    file_dropped = pyqtSignal(str)
    clicked       = pyqtSignal()      # for keyboard / click-to-browse

    _STYLE_IDLE = f"""
        QLabel {{
            background-color: {Styles.COLOR_SURFACE};
            border: 2px dashed {Styles.COLOR_BORDER};
            border-radius: 12px;
            color: {Styles.COLOR_TEXT_SECONDARY};
        }}
    """
    _STYLE_HOVER = f"""
        QLabel {{
            background-color: {Styles.COLOR_ACCENT_SUBTLE};
            border: 2px dashed {Styles.COLOR_ACCENT};
            border-radius: 12px;
            color: {Styles.COLOR_TEXT_PRIMARY};
        }}
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(160)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._set_idle()

    def _set_idle(self):
        self.setStyleSheet(self._STYLE_IDLE)
        self.setText(
            "<div style='text-align:center; line-height:2'>"
            "<span style='font-size:36px'>📂</span><br>"
            "<span style='font-size:14px; font-weight:600'>Drop a .pgn file here</span><br>"
            "<span style='font-size:12px'>or click to browse</span>"
            "</div>"
        )
        self.setTextFormat(Qt.TextFormat.RichText)

    def _set_hovering(self):
        self.setStyleSheet(self._STYLE_HOVER)
        self.setText(
            "<div style='text-align:center; line-height:2'>"
            "<span style='font-size:36px'>⬇️</span><br>"
            "<span style='font-size:14px; font-weight:600'>Release to load</span>"
            "</div>"
        )

    # ── Mouse click → open browse ───────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    # ── Drag & drop events ──────────────────────────────────────────────────
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(u.toLocalFile().lower().endswith(".pgn") for u in urls):
                event.acceptProposedAction()
                self._set_hovering()
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._set_idle()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        self._set_idle()
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".pgn"):
                self.file_dropped.emit(path)
                break


# ── Inline game card ────────────────────────────────────────────────────────────
class _GameCard(QFrame):
    """Single selectable game row inside the inline game list."""
    selected = pyqtSignal(int)   # emits its own index

    def __init__(self, index: int, line1: str, line2: str, parent=None):
        super().__init__(parent)
        self._index = index
        self._is_selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(62)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(3)

        self._lbl1 = QLabel(line1)
        self._lbl1.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY};"
            " background: transparent; border: none;"
        )
        layout.addWidget(self._lbl1)

        self._lbl2 = QLabel(line2)
        self._lbl2.setStyleSheet(
            f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY};"
            " background: transparent; border: none;"
        )
        layout.addWidget(self._lbl2)

        self._apply_style(False)

    def _apply_style(self, selected: bool):
        if selected:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {Styles.COLOR_ACCENT_SUBTLE};
                    border: 1px solid {Styles.COLOR_ACCENT};
                    border-radius: 8px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {Styles.COLOR_SURFACE};
                    border: 1px solid {Styles.COLOR_BORDER};
                    border-radius: 8px;
                }}
                QFrame:hover {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    border: 1px solid {Styles.COLOR_BORDER_LIGHT};
                }}
            """)

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self._apply_style(selected)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self._index)


# ── Inline game list (scrollable) ───────────────────────────────────────────────
class _InlineGameList(QWidget):
    """
    Scrollable list of _GameCard rows.
    Emits game_chosen(index) when a card is clicked.
    Emits cleared() when the Clear button is clicked.
    Also supports pre-selecting the first item.
    """
    game_chosen = pyqtSignal(int)
    cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        header_widget = QWidget()
        h_layout = QHBoxLayout(header_widget)
        h_layout.setContentsMargins(2, 0, 2, 0)

        self._header = QLabel("")
        self._header.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {Styles.COLOR_TEXT_SECONDARY};"
            " padding: 4px 0px;"
        )
        h_layout.addWidget(self._header)
        h_layout.addStretch()

        self.btn_clear = QPushButton("✕ Clear")
        self.btn_clear.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                color: {Styles.COLOR_TEXT_SECONDARY};
                font-size: 12px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                border-color: {Styles.COLOR_ACCENT};
                color: {Styles.COLOR_ACCENT};
                background-color: {Styles.COLOR_ACCENT_SUBTLE};
            }}
        """)
        self.btn_clear.clicked.connect(self.cleared.emit)
        h_layout.addWidget(self.btn_clear)

        root.addWidget(header_widget)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: {Styles.COLOR_BACKGROUND};
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {Styles.COLOR_BORDER};
                border-radius: 3px;
                min-height: 20px;
            }}
        """)

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._content)
        self._cards_layout.setContentsMargins(2, 2, 8, 2)
        self._cards_layout.setSpacing(6)
        self._cards_layout.addStretch()

        scroll.setWidget(self._content)
        root.addWidget(scroll, stretch=1)

        self._cards: list[_GameCard] = []
        self._selected_index: int = -1

    def populate(self, rows: list[tuple[str, str]], header: str = ""):
        """
        rows: list of (line1, line2) strings for each card.
        header: optional label above the list e.g. "5 games found"
        """
        # Clear old cards
        for card in self._cards:
            self._cards_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        self._selected_index = -1

        self._header.setText(header)
        self._header.setVisible(bool(header))

        for i, (line1, line2) in enumerate(rows):
            card = _GameCard(i, line1, line2)
            card.selected.connect(self._on_card_selected)
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)
            self._cards.append(card)

        # Pre-select first card
        if self._cards:
            self._on_card_selected(0)

    def _on_card_selected(self, index: int):
        if 0 <= self._selected_index < len(self._cards):
            self._cards[self._selected_index].set_selected(False)
        self._selected_index = index
        if 0 <= index < len(self._cards):
            self._cards[index].set_selected(True)
        self.game_chosen.emit(index)

    def clear(self):
        self.populate([], "")


# ── PGN File panel ──────────────────────────────────────────────────────────────
class _PgnFilePanel(QWidget):
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
        self._drop_zone = _DropZone()
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
        self._game_list = _InlineGameList()
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
        from ...backend.pgn_parser import PGNParser
        try:
            games = PGNParser.parse_pgn_file(path)
        except Exception as e:
            QMessageBox.critical(self, "Parse Error", f"Failed to read PGN file:\n{e}")
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
            tc_label = _classify_time_control(time_ctrl)
            move_count = len(g.moves)

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


# ── PGN Text panel ──────────────────────────────────────────────────────────────
class _PgnTextPanel(QWidget):
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
        self._game_list = _InlineGameList()
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

        from ...backend.pgn_parser import PGNParser
        try:
            games = PGNParser.parse_pgn_text(text)
        except Exception as e:
            QMessageBox.critical(self, "Parse Error", f"Failed to parse PGN text:\n{e}")
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
            tc_label = _classify_time_control(time_ctrl)
            move_count = len(g.moves)

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


# ── Chess.com Panel ────────────────────────────────────────────────────────────
class _ChessComPanel(QWidget):
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
        help_lbl = QLabel("Fetches the last 5 games for a username.")
        help_lbl.setStyleSheet(f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY};")
        input_layout.addWidget(help_lbl)
        
        input_layout.addStretch()
        root.addWidget(self._input_widget, stretch=1)

        # ── Inline game list (shown after load) ──────────────────────────────
        self._game_list = _InlineGameList()
        self._game_list.setVisible(False)
        self._game_list.game_chosen.connect(self._on_game_chosen)
        self._game_list.cleared.connect(self._clear)
        root.addWidget(self._game_list, stretch=1)

    # ── Fetching ─────────────────────────────────────────────────────────────
    def _fetch(self):
        text = self._input_edit.text().strip()
        if not text:
            return

        self._fetch_btn.setEnabled(False)
        self._fetch_btn.setText("...")
        self._input_edit.setEnabled(False)

        from ...backend.chess_com_api import ChessComAPI
        
        game_id = ChessComAPI.extract_game_id(text)
        if game_id:
            # It's a URL
            self._worker = _ApiWorker(ChessComAPI.get_game_by_id, game_id, text)
        else:
            # It's a username
            self._worker = _ApiWorker(ChessComAPI.get_last_games, text, 5)

        self._worker.finished.connect(self._on_fetch_finished)
        self._worker.error.connect(self._on_fetch_error)
        self._worker.start()

    def _on_fetch_error(self, err_msg: str):
        self._reset_input_ui()
        QMessageBox.critical(self, "API Error", f"Failed to fetch from Chess.com:\n{err_msg}")

    def _on_fetch_finished(self, result):
        self._reset_input_ui()

        if not result:
            QMessageBox.warning(self, "No Games", "No games found.")
            return

        # result is either a single dict or a list of dicts
        games_data = [result] if isinstance(result, dict) else result

        from ...backend.pgn_parser import PGNParser
        import datetime

        self._parsed_games = []
        rows = []
        
        for g_data in games_data:
            pgn = g_data.get("pgn", "")
            if not pgn:
                continue

            try:
                parsed_list = PGNParser.parse_pgn_text(pgn)
                if not parsed_list:
                    continue
                game_obj = parsed_list[0]
                self._parsed_games.append((game_obj, g_data))

                # Build display row from PGN metadata
                md = game_obj.metadata
                white = md.white or "?"
                black = md.black or "?"
                w_elo = md.white_elo or md.headers.get("WhiteElo", "?")
                b_elo = md.black_elo or md.headers.get("BlackElo", "?")
                result = md.result or "?"
                date = md.date or md.headers.get("Date", "?")
                time_ctrl = md.headers.get("TimeControl", "")
                tc_label = _classify_time_control(time_ctrl)
                move_count = len(game_obj.moves)

                line1 = f"{date}  ·  {tc_label}  ·  {result}  ·  {move_count} moves"
                line2 = f"{white} ({w_elo})  vs  {black} ({b_elo})"
                rows.append((line1, line2))
            except Exception:
                continue

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
        
        from ...utils.config import ConfigManager
        saved_username = ConfigManager().get("chesscom_username", "")
        self._input_edit.setText(saved_username)
        
        self._input_edit.setFocus()
        self.pending_cleared.emit()

    def reset(self):
        self._clear()


# ── Lichess Panel ────────────────────────────────────────────────────────────
class _LichessPanel(QWidget):
    """
    Right-panel page for 'Lichess' source.
    Fetches games by username or game URL asynchronously.
    """
    pgn_ready     = pyqtSignal(str, object)
    pending_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parsed_games: list = []
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        self._input_widget = QWidget()
        input_layout = QVBoxLayout(self._input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)

        lbl = QLabel("Enter Username or Game URL:")
        lbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY};")
        input_layout.addWidget(lbl)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self._input_edit = QLineEdit()
        self._input_edit.setPlaceholderText("e.g. DrNykterstein  or  https://lichess.org/...")
        
        saved_username = ConfigManager().get("lichess_username", "")
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

        help_lbl = QLabel("Fetches the last 5 games for a username.")
        help_lbl.setStyleSheet(f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY};")
        input_layout.addWidget(help_lbl)
        
        input_layout.addStretch()
        root.addWidget(self._input_widget, stretch=1)

        self._game_list = _InlineGameList()
        self._game_list.setVisible(False)
        self._game_list.game_chosen.connect(self._on_game_chosen)
        self._game_list.cleared.connect(self._clear)
        root.addWidget(self._game_list, stretch=1)

    def _fetch(self):
        text = self._input_edit.text().strip()
        if not text:
            return

        self._fetch_btn.setEnabled(False)
        self._fetch_btn.setText("...")
        self._input_edit.setEnabled(False)

        from ...backend.lichess_api import LichessAPI
        api = LichessAPI()
        
        game_id = api.extract_game_id(text)
        if game_id:
            self._worker = _ApiWorker(api.get_game_by_id, game_id)
        else:
            self._worker = _ApiWorker(api.get_user_games, text, 5)

        self._worker.finished.connect(self._on_fetch_finished)
        self._worker.error.connect(self._on_fetch_error)
        self._worker.start()

    def _on_fetch_error(self, err_msg: str):
        self._reset_input_ui()
        QMessageBox.critical(self, "API Error", f"Failed to fetch from Lichess:\n{err_msg}")

    def _on_fetch_finished(self, result):
        self._reset_input_ui()

        if not result:
            QMessageBox.warning(self, "No Games", "No games found.")
            return

        games_data = [result] if isinstance(result, dict) else result

        from ...backend.pgn_parser import PGNParser
        
        self._parsed_games = []
        rows = []
        
        for g_data in games_data:
            pgn = g_data.get("pgn", "")
            if not pgn:
                continue

            try:
                parsed_list = PGNParser.parse_pgn_text(pgn)
                if not parsed_list:
                    continue
                game_obj = parsed_list[0]
                self._parsed_games.append((game_obj, g_data))

                md = game_obj.metadata
                white = md.white or "?"
                black = md.black or "?"
                w_elo = md.white_elo or md.headers.get("WhiteElo", "?")
                b_elo = md.black_elo or md.headers.get("BlackElo", "?")
                result = md.result or "?"
                date = md.date or md.headers.get("Date", "?")
                time_ctrl = md.headers.get("TimeControl", "")
                tc_label = _classify_time_control(time_ctrl)
                move_count = len(game_obj.moves)

                line1 = f"{date}  ·  {tc_label}  ·  {result}  ·  {move_count} moves"
                line2 = f"{white} ({w_elo})  vs  {black} ({b_elo})"
                rows.append((line1, line2))
            except Exception:
                continue

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

        from ...utils.config import ConfigManager
        saved_username = ConfigManager().get("lichess_username", "")
        self._input_edit.setText(saved_username)

        self._input_edit.setFocus()
        self.pending_cleared.emit()

    def reset(self):
        self._clear()


# ── Time control classifier helper ─────────────────────────────────────────────
def _classify_time_control(tc: str) -> str:
    """Return Bullet/Blitz/Rapid/Classical/Correspondence from a TimeControl string."""
    if not tc or tc in ("-", "?", ""):
        return "Unknown"
    try:
        # Formats: "600" or "600+5"
        base = int(tc.split("+")[0])
        if base < 180:   return "Bullet"
        if base < 600:   return "Blitz"
        if base < 1800:  return "Rapid"
        return "Classical"
    except ValueError:
        return tc


# ── Main dialog ────────────────────────────────────────────────────────────────
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

        self._source_btns: list[_SourceBtn] = []
        self._setup_ui()
        self._switch_source(initial_source)

    # ── UI construction ─────────────────────────────────────────────────────
    def _setup_ui(self):
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

        for src_id, emoji, label, icon_path in _SOURCES:
            btn = _SourceBtn(emoji, label, icon_path=icon_path)
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
        # PGN File — fully implemented (Task 2)
        self._pgn_file_panel = _PgnFilePanel()
        self._pgn_file_panel.pgn_ready.connect(
            lambda pgn, sd: self._set_pending(pgn, sd)
        )
        self._pgn_file_panel.pending_cleared.connect(
            lambda: self._set_pending(None, None)
        )
        self.stack.addWidget(self._pgn_file_panel)   # index 0

        # PGN Text — fully implemented (Task 3)
        self._pgn_text_panel = _PgnTextPanel()
        self._pgn_text_panel.pgn_ready.connect(
            lambda pgn, sd: self._set_pending(pgn, sd)
        )
        self._pgn_text_panel.pending_cleared.connect(
            lambda: self._set_pending(None, None)
        )
        self.stack.addWidget(self._pgn_text_panel)   # index 1

        # Chess.com — fully implemented (Task 4)
        self._chesscom_panel = _ChessComPanel()
        self._chesscom_panel.pgn_ready.connect(
            lambda pgn, sd: self._set_pending(pgn, sd)
        )
        self._chesscom_panel.pending_cleared.connect(
            lambda: self._set_pending(None, None)
        )
        self.stack.addWidget(self._chesscom_panel)   # index 2

        # Lichess — fully implemented (Task 5)
        self._lichess_panel = _LichessPanel()
        self._lichess_panel.pgn_ready.connect(
            lambda pgn, sd: self._set_pending(pgn, sd)
        )
        self._lichess_panel.pending_cleared.connect(
            lambda: self._set_pending(None, None)
        )
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
        if self._pending_pgn:
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

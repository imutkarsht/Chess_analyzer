"""
Explorer View - The main container for the Opening Explorer.
"""
import json
import os
import time

import chess
from PyQt6.QtCore import QByteArray, Qt, QTimer
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.backend.analysis.engine import resolve_engine_path
from src.backend.analysis.math_utils import get_win_probability
from src.backend.analysis.move_classifier import classify_move
from src.backend.analysis.opening_db import OpeningDB, _normalize_fen
from src.backend.analysis.polyglot_book import PolyglotBookManager
from src.backend.api.import_limits import current_token
from src.backend.storage.game_history import GameHistoryManager
from src.gui.analysis.captured import CapturedPiecesWidget
from src.gui.analysis.explorer_move_list import ExplorerMoveListWidget
from src.gui.board import Board, BoardConfig
from src.gui.components import (
    Button,
    ButtonSize,
    ButtonVariant,
    Input,
    InputSize,
    InputVariant,
)
from src.gui.components.feedback.loading_widget import LoadingOverlay
from src.gui.engine_lines import (
    EngineLinesConfig,
    EngineLinesWidget,
    LiveEngineSession,
)
from src.gui.styles import Styles
from src.gui.views.explorer_book_row import BookRowWidget
from src.gui.views.explorer_lichess_worker import LichessExplorerWorker
from src.gui.views.explorer_ratio_bar import RatioBar
from src.gui.views.explorer_types import ClassificationContext
from src.utils.logger import logger
from src.utils.path_utils import get_resource_path, get_user_data_dir


class ExplorerView(QWidget):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        resolved = resolve_engine_path(self.config_manager)
        self.engine_path = resolved or self.config_manager.get("engine_path", "stockfish")
        self.session = LiveEngineSession(
            self.engine_path,
            config_manager=self.config_manager,
            parent=self,
        )
        self.session.lines_changed.connect(self._on_lines_changed)
        self.session.state_changed.connect(self._on_engine_state)
        self.session.error.connect(self._on_engine_error)

        # State tracking
        self.is_chess960 = False
        self.starting_fen = chess.STARTING_FEN
        self.board = chess.Board()
        self.move_history = [] # list of (Move object, FEN before, FEN after, SAN)

        # Classification State
        self.last_eval = None
        self.pending_classification_index = -1
        self.pending_before_eval = None
        self._classify_queue: list[int] = []  # backlog indices to classify sequentially
        self._classify_before_eval: dict | None = None  # cached before-eval for backlog step

        # Toggles
        self.classify_enabled = False

        # Init Opening DB
        tsv_dir = get_resource_path("assets/openings")
        db_path = os.path.join(get_user_data_dir(), "openings.db")
        self.opening_db = OpeningDB(db_path)
        try:
            self.opening_db.initialize(tsv_dir)
        except Exception as e:
            logger.warning(f"Failed to initialize opening DB: {e}")
        self.opening_db.connect()

        # Polyglot Book (loaded from config, optional — opened lazily)
        polyglot_path = self.config_manager.get("polyglot_book_path", "")
        self.polyglot_manager = PolyglotBookManager(polyglot_path if polyglot_path else None)

        self.setup_ui()

        # Online explorer: Lichess requires a token for explorer requests.
        # Debounce move stepping, coalesce to the latest FEN, rate-limit to the
        # account's 20 req/min budget, and stop retrying for a while after
        # repeated failures.
        self._book_row_widgets: list[QWidget] = []
        self._explorer_workers: set[LichessExplorerWorker] = set()
        self._explorer_worker: LichessExplorerWorker | None = None
        self._explorer_pending_fen: str | None = None
        self._explorer_failures = 0
        self._explorer_offline_until = 0.0
        # 20 requests/minute = one every 3s. Cheap local cache hits bypass this.
        self._explorer_min_interval = 3.0
        self._explorer_last_request = 0.0
        self._explorer_debounce = QTimer(self)
        self._explorer_debounce.setSingleShot(True)
        self._explorer_debounce.setInterval(180)
        self._explorer_debounce.timeout.connect(self._start_lichess_explorer)

        # Loading overlay for background tasks
        self.loading_overlay = LoadingOverlay(self)

        # Show loading while opening DB initializes (first launch imports TSV)
        if not self.opening_db.is_populated():
            QTimer.singleShot(50, lambda: self.loading_overlay.start(
                "Loading Opening Book...",
                "Importing Lichess ECO database (first launch only)"
            ))

        # The worker is started lazily on the first engine-lines request:
        # the toggle is off by default, so an eager search here would heat
        # the machine on every launch.
        self.update_opening_db(self.board.fen())
        self.loading_overlay.stop()

    def showEvent(self, event):
        super().showEvent(event)
        # Resume only when the user has engine lines enabled; cached lines
        # stay visible otherwise.
        if self.chk_engine.isChecked():
            self.session.resume()

    def hideEvent(self, event):
        # Leaving the Explorer (or minimising the window) must not leave a
        # Stockfish search running out of sight.  Lines stay on screen.
        self.session.pause()
        super().hideEvent(event)

    def setup_ui(self):
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header Bar Container
        self.header_bar = QFrame()
        self.header_bar.setStyleSheet(Styles.get_header_bar_ext_style(bg_color=Styles.COLOR_BACKGROUND))
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(20, 6, 20, 6)

        # Title
        self.title_lbl = QLabel("Opening Explorer")
        self.title_lbl.setStyleSheet(Styles.get_label_style(size=16, color=Styles.COLOR_TEXT_PRIMARY, bold=True) + " " + Styles.get_transparent_label_style())
        header_layout.addWidget(self.title_lbl)

        # Opening badge (inline after title)
        self.opening_badge = QLabel("Opening: -")
        self.opening_badge.setStyleSheet(Styles.get_label_style(size=13, color=Styles.COLOR_TEXT_SECONDARY) + "; padding: 0px 0px 0px 12px; " + Styles.get_transparent_label_style())
        header_layout.addWidget(self.opening_badge)

        header_layout.addStretch()

        # Action buttons header style
        self.btn_flip = Button(
            "Flip Board", ButtonVariant.HOLLOW, ButtonSize.SM, on_click=self._flip_board
        )
        header_layout.addWidget(self.btn_flip)

        self.btn_copy_fen = Button(
            "Copy FEN", ButtonVariant.HOLLOW, ButtonSize.SM, on_click=self._copy_fen
        )
        header_layout.addWidget(self.btn_copy_fen)

        self.btn_copy_pgn = Button(
            "Copy PGN", ButtonVariant.HOLLOW, ButtonSize.SM, on_click=self._copy_pgn
        )
        header_layout.addWidget(self.btn_copy_pgn)

        main_layout.addWidget(self.header_bar)

        # Content Area - Splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(2)
        self.splitter.setStyleSheet(Styles.get_splitter_style())

        # ==========================================
        # LEFT PANEL (Board & Eval)
        # ==========================================
        self.left_panel = QWidget()
        self.left_panel.setStyleSheet(Styles.get_background_style())
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(8, 8, 8, 8)
        self.left_layout.setSpacing(6)

        # Opponent Label (Top)
        self.black_header_widget = QWidget()
        black_header = QHBoxLayout(self.black_header_widget)
        black_header.setContentsMargins(0, 0, 0, 0)
        self.lbl_black = QLabel("Black")
        self.lbl_black.setStyleSheet(Styles.get_label_style(size=16, bold=True))
        self.captured_black = CapturedPiecesWidget(side="black")
        black_header.addWidget(self.lbl_black)
        black_header.addWidget(self.captured_black)
        black_header.addStretch()
        self.left_layout.addWidget(self.black_header_widget)

        # Board (contains its own eval bar internally laid out)
        self.board_widget = Board(BoardConfig(classification_overlay="last_move"))
        self.board_widget.move_made.connect(self.on_move_made)
        self.left_layout.addWidget(self.board_widget, stretch=1)

        # Player Label (Bottom)
        self.white_header_widget = QWidget()
        white_header = QHBoxLayout(self.white_header_widget)
        white_header.setContentsMargins(0, 0, 0, 0)
        self.lbl_white = QLabel("White")
        self.lbl_white.setStyleSheet(Styles.get_label_style(size=16, bold=True))
        self.captured_white = CapturedPiecesWidget(side="white")
        white_header.addWidget(self.lbl_white)
        white_header.addWidget(self.captured_white)
        white_header.addStretch()
        self.left_layout.addWidget(self.white_header_widget)

        self.splitter.addWidget(self.left_panel)

        # ==========================================
        # RIGHT PANEL (Controls & Analysis)
        # ==========================================
        self.right_panel = QWidget()
        self.right_panel.setStyleSheet(Styles.get_background_style())
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(8, 8, 12, 8)
        right_layout.setSpacing(6)

        # Toggles Bar
        toggles_layout = QHBoxLayout()
        toggles_layout.setContentsMargins(0, 0, 0, 4)
        toggles_layout.setSpacing(8)

        self.chk_classify = QCheckBox("Classify Moves")
        self.chk_classify.setChecked(self.classify_enabled)
        self.chk_classify.toggled.connect(self.on_classify_toggled)

        self.chk_legal = QCheckBox("Legal Moves")
        self.chk_legal.setChecked(True)
        self.chk_legal.toggled.connect(self.on_legal_moves_toggled)

        self.chk_engine = QCheckBox("Engine Lines")
        self.chk_engine.setChecked(False)
        self.chk_engine.toggled.connect(self.on_engine_toggled)

        self.chk_cache = QCheckBox("Use Cache")
        self.chk_cache.setChecked(True)

        for chk in (self.chk_classify, self.chk_legal, self.chk_engine, self.chk_cache):
            chk.setStyleSheet(Styles.get_label_style(size=12, color=Styles.COLOR_TEXT_SECONDARY, weight=500))
            chk.setCursor(Qt.CursorShape.PointingHandCursor)
            toggles_layout.addWidget(chk)

        right_layout.addLayout(toggles_layout)

        # Engine Lines
        self.lines_widget = EngineLinesWidget(
            EngineLinesConfig(empty_text="Enable Engine Lines to see analysis")
        )
        self.lines_widget.line_clicked.connect(self.on_engine_line_clicked)
        right_layout.addWidget(self.lines_widget, stretch=0)

        self.lines_widget.setVisible(False)

        # Book Moves Toggle + Table
        self._current_book_count = 0
        self.book_toggle = Button(
            "▶  Book Moves",
            ButtonVariant.GHOST,
            checkable=True,
            align="left",
            on_click=None,
        )
        self.book_toggle.setChecked(True)
        self.book_toggle.toggled.connect(self._toggle_book)
        right_layout.addWidget(self.book_toggle)

        self.explorer_hint = QLabel()
        self.explorer_hint.setWordWrap(True)
        self.explorer_hint.setOpenExternalLinks(False)
        self.explorer_hint.setStyleSheet(
            Styles.get_label_style(size=11, color=Styles.COLOR_TEXT_MUTED)
            + "; padding: 2px 14px; "
            + Styles.get_transparent_label_style()
        )
        self.explorer_hint.hide()
        right_layout.addWidget(self.explorer_hint)

        self.book_scroll = QScrollArea()
        self.book_scroll.setWidgetResizable(True)
        self.book_scroll.setStyleSheet(Styles.get_scroll_area_style())

        self.book_container = QWidget()
        self.book_container.setStyleSheet(Styles.get_surface_style())
        self.book_layout = QVBoxLayout(self.book_container)
        self.book_layout.setContentsMargins(0, 0, 0, 0)
        self.book_layout.setSpacing(0)
        self.book_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.book_scroll.setWidget(self.book_container)

        right_layout.addWidget(self.book_scroll, stretch=1)

        # Lichess Attribution footer
        self.lichess_attribution = QLabel()
        self.lichess_attribution.setStyleSheet(Styles.get_label_style(size=11, color=Styles.COLOR_TEXT_MUTED) + "; padding: 4px 14px; " + Styles.get_transparent_label_style())
        self.lichess_attribution.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lichess_attribution.setOpenExternalLinks(True)
        self.lichess_attribution.setText(f'powered by <a href="https://lichess.org" style="color: {Styles.COLOR_ACCENT}; text-decoration: none;">lichess.org</a>')
        self.lichess_attribution.setVisible(False)
        right_layout.addWidget(self.lichess_attribution)

        # Move List Header (inline with move input)
        moves_header = QHBoxLayout()
        moves_header.setContentsMargins(0, 0, 0, 0)
        moves_header.setSpacing(8)
        self.move_list_label = QLabel("Moves")
        self.move_list_label.setStyleSheet(Styles.get_label_style(size=14, bold=True))
        moves_header.addWidget(self.move_list_label)
        self.move_input = Input(
            placeholder="type SAN move...",
            variant=InputVariant.INLINE,
            size=InputSize.SM,
            on_submit=self._on_move_text_entered,
        )
        self.move_input.setToolTip("Enter a move in standard algebraic notation (e.g. e4, Nf3, O-O)")
        self.move_input.setMinimumWidth(120)
        moves_header.addWidget(self.move_input)
        moves_header.addStretch()
        right_layout.addLayout(moves_header)

        self.move_list_widget = ExplorerMoveListWidget()
        self.move_list_widget.move_selected.connect(self.on_move_list_clicked)
        self.move_list_widget.nav_first.connect(lambda: self.on_move_list_clicked(-1))
        self.move_list_widget.nav_prev.connect(lambda: self.on_move_list_clicked(self.move_list_widget.current_index - 1))
        self.move_list_widget.nav_next.connect(lambda: self.on_move_list_clicked(self.move_list_widget.current_index + 1))
        self.move_list_widget.nav_last.connect(lambda: self.on_move_list_clicked(len(self.move_history) - 1))

        right_layout.addWidget(self.move_list_widget, stretch=1)

        # Engine Status
        self.engine_status_label = QLabel("")
        self.engine_status_label.setStyleSheet(Styles.get_engine_status_style(Styles.COLOR_TEXT_MUTED))
        right_layout.addWidget(self.engine_status_label)

        self.splitter.addWidget(self.right_panel)
        self.splitter.setSizes([700, 450])
        main_layout.addWidget(self.splitter, 1)

    def load_fen(self, fen):
        """Loads a starting position into the explorer."""
        castling = fen.split()[2]
        self.is_chess960 = castling != '-' and any(c not in 'KQkq' for c in castling)
        self.starting_fen = fen
        try:
            test_board = chess.Board(fen, chess960=self.is_chess960)
        except ValueError as e:
            logger.error(f"Invalid FEN: {fen} — {e}")
            return

        self.board = test_board
        self.move_history = []
        self.move_list_widget.clear()
        self.pending_classification_index = -1
        self.last_eval = None
        self.pending_before_eval = None

        self.board_widget.load_fen(fen, chess960=self.is_chess960)
        self.update_opening_db(fen)

        self._refresh_engine(fen)
        # Trigger initial material update
        self._update_material()

    def _refresh_engine(self, fen):
        """Request live lines for ``fen``, or clear the panel when disabled.

        The shared session owns the sequence counter, so any result that
        arrives for a position we already left is discarded for us.
        """
        if self.chk_engine.isChecked():
            self.lines_widget.set_empty_text("Analysing position…")
            self.session.request(
                fen, chess960=self.is_chess960, emit_empty=True
            )
        else:
            self.lines_widget.set_empty_text("Enable Engine Lines to see analysis")
            self.session.clear(emit=False)
            self.lines_widget.clear()
            self.board_widget.set_best_move(None)
            self.board_widget.eval_bar.set_eval(0.0, None)

    def _is_book_move(self, node_id, uci, fen_before):
        """Check if a move (by UCI) is a book move at the given node.
        Checks both the SQLite opening DB and the Polyglot book."""
        try:
            board = chess.Board(fen_before, chess960=self.is_chess960)
            candidates = self.opening_db.get_children(node_id)
            for candidate_san in candidates:
                candidate_move = board.parse_san(candidate_san)
                if candidate_move.uci() == uci:
                    return True
        except Exception as e:
            logger.warning(f"Error checking SQLite book move: {e}")

        if self.polyglot_manager.is_available():
            try:
                board = chess.Board(fen_before, chess960=self.is_chess960)
                for entry in self.polyglot_manager.reader.find_all(board):
                    if entry.move.uci() == uci:
                        return True
            except Exception as e:
                logger.warning(f"Error checking polyglot book move: {e}")

        return False

    def _update_material(self):
        """Update captured pieces and material advantage."""
        fen = self.board_widget.board.fen()
        self.captured_white.update_captured(fen)
        self.captured_black.update_captured(fen)

    def _start_backlog_classification(self):
        """Queue all unclassified moves for sequential classification.
        Moves are classified one at a time: for each move, we first get
        the engine eval for the position BEFORE the move, then step
        forward to the position AFTER the move and run classification."""
        self._classify_queue = []
        for i, _m in enumerate(self.move_history):
            if not self.move_list_widget.moves[i].get('classification'):
                self._classify_queue.append(i)
        if not self._classify_queue:
            return
        if not self.classify_enabled or not self.chk_engine.isChecked():
            return
        # Navigate to position before the first queued move
        self._classify_before_eval = None
        target_idx = self._classify_queue[0] - 1
        self.on_move_list_clicked(target_idx)

    def _process_backlog_step(self):
        """Called after classification completes — advance to next backlog move."""
        if not self._classify_queue or self.pending_classification_index >= 0:
            return
        if not self.classify_enabled or not self.chk_engine.isChecked():
            self._classify_queue = []
            return
        # We're at the after-position of the classified move = before-position of next
        # Wait for engine eval, then use it in _on_lines_changed
        self._classify_before_eval = None
        self._refresh_engine(self.board.fen())

    def load_board_state(self, source_board, source_moves=None, *, chess960=None, starting_fen=None):
        """Loads a full board state including its move stack history and optional existing classifications.

        Parameters
        ----------
        source_board : chess.Board
            Board at the displayed position (move_stack is replayed from scratch).
        source_moves : list[MoveAnalysis] | None
            Move-level metadata with classifications.
        chess960 : bool | None
            Authoritative chess960 flag from game metadata.
            When ``True``, the starting FEN and UCI strings from
            ``source_moves`` are used for replay so that board states
            are correct regardless of what mode the main widget used.
        starting_fen : str | None
            Authoritative starting FEN from game metadata.
        """
        # Phase 1: detect Chess960 mode — trust metadata (passed via kwargs)
        # over source_board, since the main widget may have lost the flag.
        self.is_chess960 = chess960 if chess960 is not None else getattr(source_board, 'chess960', False)
        # Starting FEN: use metadata value when available, else fall back to
        # source_board (which is chess.STARTING_FEN for Chess960 boards).
        # When the metadata value is None but Chess960 is True, try to recover
        # the actual starting FEN from the first move's fen_before.
        if starting_fen:
            self.starting_fen = starting_fen
        elif source_moves and source_moves[0].fen_before:
            self.starting_fen = source_moves[0].fen_before
        else:
            self.starting_fen = source_board.starting_fen

        # Phase 2: determine which move list to replay from.
        # source_board.move_stack may have been generated on a standard board
        # even for Chess960 games.  When Chess960 IS detected and source_moves
        # has enough entries, use the authoritative UCI strings from game
        # metadata so board states are correct.
        num_moves = len(source_board.move_stack)
        if self.is_chess960 and source_moves and len(source_moves) >= num_moves:
            replay_moves = [chess.Move.from_uci(source_moves[i].uci) for i in range(num_moves)]
        else:
            replay_moves = list(source_board.move_stack)

        self.board = chess.Board(self.starting_fen, chess960=self.is_chess960)
        self.move_history = []
        self.move_list_widget.clear()
        self.pending_classification_index = -1
        self.last_eval = None

        # We need to rebuild the visual state as if moves were played
        # We temporarily disconnect move_made to prevent triggering classifications
        try:
            self.board_widget.move_made.disconnect(self.on_move_made)
        except TypeError:
            pass
        self.board_widget.load_fen(fen=self.starting_fen, chess960=self.is_chess960)

        # Play out the move stack
        for i, move in enumerate(replay_moves):
            fen_before = self.board.fen()
            try:
                san = self.board.san(move)
            except (AssertionError, ValueError):
                san = move.uci()
            self.board.push(move)
            fen_after = self.board.fen()

            # Sync to board widget
            self.board_widget.board.push(move)

            # Add to history
            self.move_history.append((move, fen_before, fen_after, san))
            self.move_list_widget.add_move(san)

            if source_moves and i < len(source_moves) and source_moves[i].classification:
                self.move_list_widget.update_classification(i, source_moves[i].classification)

        self.board_widget.set_best_move(None)
        self.board_widget.set_last_move_classification(None)
        self.board_widget.move_made.connect(self.on_move_made)

        fen = self.board.fen()
        self.update_opening_db(fen)
        self._update_material()

        self._refresh_engine(fen)

        # Start backlog classification for any unclassified moves
        if self.classify_enabled and self.chk_engine.isChecked():
            self._start_backlog_classification()

    def on_move_made(self, fen):
        # Clear backlog classification when user makes a manual move
        self._classify_queue = []
        self._classify_before_eval = None

        self._update_material()
        if not self.board_widget.board.move_stack:
            return

        # We pushed a move to self.board_widget.board.
        # Find out what move it was.
        move = self.board_widget.board.peek()
        try:
            san = self.board.san(move)
        except (AssertionError, ValueError):
            san = move.uci()

        # Update local board state
        fen_before = self.board.fen()
        self.board.push(move)
        fen_after = self.board.fen()

        # Truncate history if we navigated back
        if self.move_list_widget.current_index < len(self.move_history) - 1:
            self.move_history = self.move_history[:self.move_list_widget.current_index + 1]

        self.move_history.append((move, fen_before, fen_after, san))
        self.move_list_widget.add_move(san)

        # Setup pending classification
        self.pending_classification_index = len(self.move_history) - 1
        self.pending_before_eval = dict(self.last_eval) if self.last_eval else None

        # Show pending indicator if classification is enabled
        if self.classify_enabled:
            self.move_list_widget.set_pending_classification(self.pending_classification_index, True)

        # Check if it's a book move instantly (compare by UCI to avoid SAN ambiguity)
        norm_fen = _normalize_fen(fen_before)
        node_id = self.opening_db.get_node_by_fen(norm_fen)
        if self._is_book_move(node_id, move.uci(), fen_before) and self.classify_enabled:
            self.move_list_widget.update_classification(self.pending_classification_index, "Book")
            self.pending_classification_index = -1
            self.board_widget.last_move_classification = "Book"

        # Update engine and opening db
        self._refresh_engine(fen_after)

        self.update_opening_db(fen_after)

    def _get_piece_pixmap(self, symbol, size=18):
        cache_key = (symbol, size)
        if not hasattr(self, '_piece_pixmap_cache'):
            self._piece_pixmap_cache = {}
        if cache_key not in self._piece_pixmap_cache:
            from src.gui.board.piece_themes import _load_theme_cached, get_current_theme_name
            pieces_svg = _load_theme_cached(get_current_theme_name())
            g_content = pieces_svg.get(symbol, "")
            if g_content:
                svg_str = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 45">{g_content}</svg>'
                renderer = QSvgRenderer(QByteArray(svg_str.encode('utf-8')))
                pixmap = QPixmap(size, size)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                self._piece_pixmap_cache[cache_key] = pixmap
            else:
                self._piece_pixmap_cache[cache_key] = None
        return self._piece_pixmap_cache[cache_key]




    def _create_book_row_widget(self, san, info_text, piece_symbol=None, stats=None):
        row_widget = BookRowWidget(san, on_click=self.on_book_move_clicked, parent=self)
        row_widget.setStyleSheet(Styles.get_book_row_style())
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(14, 8, 14, 8)
        row_layout.setSpacing(8)

        # Left part
        left_layout = QHBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        if piece_symbol:
            pixmap = self._get_piece_pixmap(piece_symbol)
            if pixmap:
                icon_label = QLabel()
                icon_label.setPixmap(pixmap)
                icon_label.setFixedSize(18, 18)
                icon_label.setStyleSheet(Styles.get_transparent_label_style())
                left_layout.addWidget(icon_label)

        lbl_san = QLabel(san)
        lbl_san.setStyleSheet(Styles.get_label_style(size=15, color=Styles.COLOR_TEXT_PRIMARY, bold=True) + " " + Styles.get_transparent_label_style())
        left_layout.addWidget(lbl_san)

        row_layout.addLayout(left_layout)
        row_layout.addStretch()

        # Right part
        if stats:
            w_pct, d_pct, b_pct, count_str = stats

            right_layout = QHBoxLayout()
            right_layout.setContentsMargins(0, 0, 0, 0)
            right_layout.setSpacing(12)

            lbl_count = QLabel(count_str)
            lbl_count.setStyleSheet(Styles.get_label_style(size=13, color=Styles.COLOR_TEXT_MUTED, weight=500) + " " + Styles.get_transparent_label_style())
            right_layout.addWidget(lbl_count)

            ratio_bar = RatioBar(w_pct, d_pct, b_pct, self)
            right_layout.addWidget(ratio_bar)

            row_layout.addLayout(right_layout)
        elif info_text:
            lbl_info = QLabel(info_text)
            lbl_info.setStyleSheet(Styles.get_label_style(size=13, color=Styles.COLOR_TEXT_SECONDARY) + "; font-style: italic; " + Styles.get_transparent_label_style())
            lbl_info.setMinimumWidth(0)
            row_layout.addWidget(lbl_info)

        return row_widget

    def _history(self) -> GameHistoryManager:
        """Lazily share one history/cache manager across workers."""
        if not hasattr(self, "_history_manager"):
            self._history_manager = GameHistoryManager()
        return self._history_manager

    def _explorer_enabled(self) -> bool:
        try:
            return bool(self.config_manager.get("lichess_explorer_enabled", True))
        except Exception:
            return True

    def _online_explorer_allowed(self) -> bool:
        """Whether the online explorer is enabled, authorised, and not cooling down."""
        return (
            bool(current_token(self.config_manager))
            and self._explorer_enabled()
            and time.time() >= self._explorer_offline_until
        )

    def _explorer_disabled_reason(self) -> str:
        """Human-readable reason the online explorer is not being used."""
        if not current_token(self.config_manager):
            return "Add a Lichess token in Settings → Integrations to load online explorer data."
        if not self._explorer_enabled():
            return "Online explorer is disabled in Settings → Integrations."
        return ""

    def _render_cached_explorer(self, fen: str) -> bool:
        """Render a cached explorer response so offline use needs no token."""
        if not self.chk_cache.isChecked():
            return False
        try:
            raw = self._history().get_explorer_cache(_normalize_fen(fen))
            data = json.loads(raw) if raw else None
        except Exception:
            return False
        if not isinstance(data, dict) or not data.get("moves"):
            return False
        self.on_lichess_explorer_finished(data)
        return True

    def _update_explorer_hint(self, message: str | None = None) -> None:
        """Show the token/settings hint when online data is unavailable."""
        text = message if message is not None else self._explorer_disabled_reason()
        if text:
            self.explorer_hint.setText(text)
            self.explorer_hint.show()
        else:
            self.explorer_hint.clear()
            self.explorer_hint.hide()

    def _clear_book_rows(self) -> None:
        for widget in self._book_row_widgets:
            self.book_layout.removeWidget(widget)
            widget.deleteLater()
        self._book_row_widgets = []
        self.board_widget.book_destinations = []
        self._current_book_count = 0

    def _update_book_toggle(self, suffix: str = "") -> None:
        arrow = "▼" if self.book_toggle.isChecked() else "▶"
        self.book_toggle.setText(
            f"{arrow}  Book Moves  ({self._current_book_count}){suffix}"
        )
        if self._current_book_count > 0:
            self.book_toggle.show()
            self.book_scroll.setVisible(self.book_toggle.isChecked())
        else:
            self.book_toggle.hide()
            self.book_scroll.hide()

    def _draw_local_book(self, node_id) -> int:
        """Render the offline Polyglot/SQLite book; return the row count."""
        self._clear_book_rows()

        # --- Try Polyglot book first (higher priority) ---
        polyglot_used = False
        current_path = self.config_manager.get("polyglot_book_path", "")
        if current_path != (self.polyglot_manager.book_path or ""):
            self.polyglot_manager.set_book_path(current_path if current_path else None)
        if self.polyglot_manager.is_available():
            try:
                board = self.board_widget.board
                entries = list(self.polyglot_manager.reader.find_all(board))
                if entries:
                    polyglot_used = True
                    entries.sort(key=lambda e: e.weight, reverse=True)
                    for entry in entries:
                        ply_move = entry.move
                        try:
                            san = board.san(ply_move)
                        except Exception:
                            san = ply_move.uci()
                        self.board_widget.book_destinations.append(ply_move.to_square)
                        weight_str = str(entry.weight)
                        piece = board.piece_at(ply_move.from_square)
                        piece_symbol = piece.symbol() if piece else None
                        row_widget = self._create_book_row_widget(
                            san, weight_str, piece_symbol
                        )
                        self.book_layout.addWidget(row_widget)
                        self._book_row_widgets.append(row_widget)
            except Exception as e:
                logger.warning(f"Polyglot query failed: {e}", exc_info=True)

        # --- Fall back to SQLite Opening DB ---
        if not polyglot_used and node_id is not None:
            candidates = self.opening_db.get_children(node_id)
            if candidates:
                for san in candidates:
                    move_name = ""
                    push_done = False
                    try:
                        move = self.board_widget.board.parse_san(san)
                        self.board_widget.board.push(move)
                        push_done = True
                        child_fen = _normalize_fen(self.board_widget.board.fen())
                        self.board_widget.board.pop()
                        push_done = False

                        child_node_id = self.opening_db.get_node_by_fen(child_fen)
                        if child_node_id is not None:
                            child_openings = self.opening_db.get_openings_at_node(
                                child_node_id
                            )
                            if child_openings:
                                best_name = max(
                                    child_openings, key=lambda x: len(x[1])
                                )[1]
                                move_name = best_name

                        self.board_widget.book_destinations.append(move.to_square)
                    except Exception as e:
                        logger.warning(f"Error processing SQLite book move {san}: {e}")
                        if push_done:
                            try:
                                self.board_widget.board.pop()
                            except Exception:
                                pass
                        continue

                    piece = self.board_widget.board.piece_at(move.from_square)
                    piece_symbol = piece.symbol() if piece else None
                    row_widget = self._create_book_row_widget(
                        san, move_name, piece_symbol
                    )
                    self.book_layout.addWidget(row_widget)
                    self._book_row_widgets.append(row_widget)

        self._current_book_count = len(self._book_row_widgets)
        self._update_book_toggle()
        return self._current_book_count

    def _draw_local_book_fallback(self) -> None:
        """Show the local book after the online request failed."""
        node_id = self.opening_db.get_node_by_fen(
            _normalize_fen(self.board_widget.board.fen())
        )
        self._draw_local_book(node_id)
        if self._current_book_count:
            self._update_book_toggle("  · local book")
        self.lichess_attribution.setVisible(False)
        self.board_widget.draw_interactive_overlays()

    def update_opening_db(self, fen):
        norm_fen = _normalize_fen(fen)
        node_id = self.opening_db.get_node_by_fen(norm_fen)

        if not self.board_widget.board.move_stack:
            self.opening_badge.setText("Opening: -")

        # --- Update opening badge from SQLite (always) ---
        if node_id is not None:
            openings = self.opening_db.get_openings_at_node(node_id)
            if openings:
                best_name = max(openings, key=lambda x: len(x[1]))[1]
                best_eco = max(openings, key=lambda x: len(x[1]))[0]
                self.opening_badge.setText(f"Opening: {best_eco} - {best_name}")

        # Offline book renders immediately; online data replaces it when ready.
        self._draw_local_book(node_id)

        if not self._online_explorer_allowed():
            self._explorer_pending_fen = None
            self._explorer_debounce.stop()
            hint = ""
            cached_shown = self._explorer_enabled() and self._render_cached_explorer(
                self.board_widget.board.fen()
            )
            if cached_shown:
                if not current_token(self.config_manager):
                    hint = (
                        "Showing cached explorer data. Add a Lichess token in "
                        "Settings → Integrations for live updates."
                    )
            else:
                if self._current_book_count:
                    self._update_book_toggle("  · local book")
                self.lichess_attribution.setVisible(False)
            self._update_explorer_hint(hint or None)
            self.board_widget.draw_interactive_overlays()
            return

        self._update_explorer_hint("")
        # Explorer requests need the user's Lichess token; debounce rapid moves.
        self._explorer_pending_fen = self.board_widget.board.fen()
        arrow = "▼" if self.book_toggle.isChecked() else "▶"
        if self._current_book_count:
            self.book_toggle.setText(
                f"{arrow}  Book Moves  ({self._current_book_count})  · loading…"
            )
            self.book_toggle.show()
            self.book_scroll.setVisible(self.book_toggle.isChecked())
        else:
            self.book_toggle.setText("▶  Book Moves  (loading...)")
            self.book_toggle.show()
            self.book_scroll.hide()
        self._explorer_debounce.start()
        self.board_widget.draw_interactive_overlays()

    def _start_lichess_explorer(self) -> None:
        fen = self._explorer_pending_fen
        if not fen or not self._online_explorer_allowed():
            return
        if self._explorer_worker is not None and self._explorer_worker.isRunning():
            # The pending FEN is picked up when the active request retires.
            return

        # Stay inside the 20 requests/minute account budget. If we are early,
        # keep only the latest FEN and retry once the interval has elapsed.
        elapsed = time.time() - self._explorer_last_request
        remaining = self._explorer_min_interval - elapsed
        if remaining > 0:
            self._explorer_debounce.start(int(remaining * 1000) + 1)
            return

        self._explorer_pending_fen = None
        self._explorer_last_request = time.time()
        worker = LichessExplorerWorker(
            fen,
            self.chk_cache.isChecked(),
            self._history(),
            current_token(self.config_manager),
        )
        self._explorer_workers.add(worker)
        self._explorer_worker = worker
        worker.loaded.connect(
            lambda data, w=worker: self._on_explorer_data(w, data)
        )
        worker.error.connect(
            lambda message, w=worker: self._on_explorer_error(w, message)
        )
        worker.finished.connect(
            lambda w=worker: self._retire_explorer_worker(w)
        )
        worker.start()

    def _retire_explorer_worker(self, worker: LichessExplorerWorker) -> None:
        self._explorer_workers.discard(worker)
        worker.deleteLater()
        if worker is self._explorer_worker:
            self._explorer_worker = None
        if self._explorer_pending_fen and self._online_explorer_allowed():
            QTimer.singleShot(0, self._start_lichess_explorer)

    def _on_explorer_data(self, worker: LichessExplorerWorker, data) -> None:
        if worker is not self._explorer_worker:
            return
        self._explorer_failures = 0
        if not isinstance(data, dict):
            self._on_explorer_error(worker, "invalid_response")
            return
        if not data.get("moves") and self._current_book_count:
            # A valid but empty response should not hide the local book.
            self._update_book_toggle("  · local book")
            self.lichess_attribution.setVisible(False)
            return
        self._update_explorer_hint("")
        self.on_lichess_explorer_finished(data)

    def _on_explorer_error(
        self, worker: LichessExplorerWorker, message: str
    ) -> None:
        if worker is not self._explorer_worker:
            return
        logger.warning(f"Lichess explorer fetch failed: {message}")
        self._explorer_failures += 1
        if message == "unauthorized":
            self._update_explorer_hint(
                "Lichess rejected the explorer token. Update it in "
                "Settings → Integrations."
            )
        elif message in {"offline", "rate_limited"} or self._explorer_failures >= 3:
            cooldown = 300 if message == "offline" else 120
            self._explorer_offline_until = time.time() + cooldown
            logger.info(
                "Lichess explorer paused for %ss after: %s", cooldown, message
            )
        self._draw_local_book_fallback()

    def on_book_move_clicked(self, san):
        if not san:
            return
        try:
            move = self.board_widget.board.parse_san(san)
            self.board_widget.attempt_move(move.from_square, move.to_square, promotion=move.promotion)
        except Exception as e:
            logger.warning(f"Failed to play book move {san}: {e}")

    def on_engine_line_clicked(self, uci_move):
        try:
            move = chess.Move.from_uci(uci_move)
            self.board_widget.attempt_move(move.from_square, move.to_square, promotion=move.promotion)
        except Exception as e:
            logger.warning(f"Failed to play engine line move {uci_move}: {e}")

    def _normalize_san(self, text):
        """Try case-insensitive parsing: if text starts with a lowercase piece
        letter (k,q,r,b,n), uppercase it for standard SAN."""
        if not text:
            return text
        if text[0] in 'kqrbn' and text[0].islower():
            text = text[0].upper() + text[1:]
        return text

    def _on_move_text_entered(self):
        """Play a move typed as SAN text (e.g. 'e4', 'Nf3', 'O-O')."""
        text = self.move_input.text().strip()
        if not text:
            return
        fen_before = self.board_widget.board.fen()
        try:
            text = self._normalize_san(text)
            move = self.board_widget.board.parse_san(text)
            self.board_widget.attempt_move(move.from_square, move.to_square, promotion=move.promotion)
            if self.board_widget.board.fen() == fen_before:
                raise ValueError(f"Illegal move: {text}")
            self.move_input.clear()
        except Exception as e:
            if not isinstance(e, ValueError) or str(e) != f"Illegal move: {text}":
                pass
            self.move_input.set_invalid()
            QTimer.singleShot(1000, self._reset_move_input_style)

    def _reset_move_input_style(self):
        self.move_input.clear_invalid()

    def _toggle_book(self, checked):
        self.book_scroll.setVisible(checked)
        arrow = "▼" if checked else "▶"
        self.book_toggle.setText(f"{arrow}  Book Moves  ({self._current_book_count})")

    def _flip_board(self):
        self.board_widget.flip_board()
        self.board_widget.draw_interactive_overlays()
        # Swap captured pieces headers around the board
        self.left_layout.removeWidget(self.white_header_widget)
        self.left_layout.removeWidget(self.black_header_widget)
        # After removal, only board_widget remains at index 0
        if self.board_widget.is_flipped:
            self.left_layout.insertWidget(0, self.white_header_widget)  # white above
            self.left_layout.insertWidget(2, self.black_header_widget)  # black below
        else:
            self.left_layout.insertWidget(0, self.black_header_widget)   # black above
            self.left_layout.insertWidget(2, self.white_header_widget)   # white below

    def _copy_fen(self):
        fen = self.board_widget.board.fen()
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(fen)
        self.engine_status_label.setText("✓ FEN copied")
        self.engine_status_label.setStyleSheet(Styles.get_engine_status_style(Styles.COLOR_ENGINE_READY))
        QTimer.singleShot(2000, self._reset_status)

    def _copy_pgn(self):
        from datetime import date

        import chess.pgn
        game = chess.pgn.Game()
        game.headers["Event"] = "Chess Analyzer Pro"
        game.headers["Site"] = "Opening Explorer"
        game.headers["Date"] = date.today().strftime("%Y.%m.%d")
        game.headers["Round"] = "-"
        game.headers["White"] = "-"
        game.headers["Black"] = "-"
        game.headers["Result"] = "*"
        if self.starting_fen != chess.STARTING_FEN:
            game.headers["FEN"] = self.starting_fen
            game.headers["SetUp"] = "1"
        node = game
        for m, _, _, _ in self.move_history:
            node = node.add_variation(m)
        exporter = chess.pgn.StringExporter(headers=True, comments=False, variations=False)
        pgn_text = game.accept(exporter)
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(pgn_text)
        self.engine_status_label.setText("✓ PGN copied")
        self.engine_status_label.setStyleSheet(Styles.get_engine_status_style(Styles.COLOR_ENGINE_READY))
        QTimer.singleShot(2000, self._reset_status)

    def _reset_status(self):
        self.engine_status_label.setText("⬤ Ready")
        self.engine_status_label.setStyleSheet(Styles.get_engine_status_style(Styles.COLOR_ENGINE_READY))

    def on_move_list_clicked(self, index):
        # Prevent out-of-bounds
        if index < -1 or index >= len(self.move_history):
            return

        current_idx = self.move_list_widget.current_index
        is_step_forward = (index == current_idx + 1)
        is_step_back = (index == current_idx - 1)

        # Optimize: step forward/back by 1 move instead of full replay
        if is_step_forward and current_idx >= -1 and index < len(self.move_history):
            self.board.push(self.move_history[index][0])
        elif is_step_back and current_idx >= 0:
            self.board.pop()
        else:
            # Full replay for larger jumps
            self.board = chess.Board(self.starting_fen, chess960=self.is_chess960)
            for i in range(index + 1):
                self.board.push(self.move_history[i][0])

        # Sync board widget
        self.board_widget.set_board(self.board.copy())

        # Sync move list
        self.move_list_widget.set_index(index)

        # Sync engine & DB
        fen = self.board.fen()
        self._refresh_engine(fen)

        self.update_opening_db(fen)

        if is_step_forward:
            # Only set pending if the move isn't already classified
            if not self.move_list_widget.moves[index].get('classification'):
                self.pending_classification_index = index
                self.pending_before_eval = dict(self.last_eval) if self.last_eval else None
            else:
                self.pending_classification_index = -1
                self.pending_before_eval = None
        else:
            # Reset classification tracker because we jumped around
            self.pending_classification_index = -1
            self.pending_before_eval = None

    def _on_engine_state(self, state):
        """Map the shared session's lifecycle to the status pill."""
        if state == "thinking":
            self.engine_status_label.setText("⬤ Analyzing...")
            color = Styles.COLOR_ENGINE_BUSY
        elif state == "error":
            self.engine_status_label.setText("⬤ Engine error")
            color = Styles.COLOR_ENGINE_BUSY
        else:
            self.engine_status_label.setText("⬤ Ready")
            color = Styles.COLOR_ENGINE_READY
        self.engine_status_label.setStyleSheet(Styles.get_engine_status_style(color))

    def _on_engine_error(self, message):
        logger.warning("Explorer live engine error: %s", message)

    def update_engine_path(self, path):
        """Swap the engine binary without restarting the application."""
        self.engine_path = path
        self.session.set_engine_path(path)

    def on_classify_toggled(self, checked):
        self.classify_enabled = checked
        if not checked:
            # Clear pending classifications and backlog
            if self.pending_classification_index >= 0:
                self.move_list_widget.set_pending_classification(self.pending_classification_index, False)
            self.pending_classification_index = -1
            self.pending_before_eval = None
            self._classify_queue = []
            self._classify_before_eval = None
        else:
            # Auto-enable engine if off (required for classification)
            if not self.chk_engine.isChecked():
                self.chk_engine.setChecked(True)
            self._start_backlog_classification()

    def on_legal_moves_toggled(self, checked):
        self.board_widget.set_show_legal_moves(checked)

    def on_engine_toggled(self, enabled):
        self.lines_widget.setVisible(enabled)
        self.session.set_enabled(enabled)
        if enabled:
            self._refresh_engine(self.board_widget.board.fen())
            return
        self.lines_widget.set_empty_text("Enable Engine Lines to see analysis")
        self.lines_widget.clear()
        self.board_widget.set_best_move(None)
        self.board_widget.eval_bar.set_eval(0.0, None)

    def _on_lines_changed(self, lines):
        """Render White-perspective lines and drive eval + classification.

        ``EngineLine`` scores are already White perspective, so no
        side-to-move conversion happens here (doing it twice was what made
        the eval bar flip when Black was to move).
        """
        self.lines_widget.set_lines(lines)
        if not lines:
            self.board_widget.set_best_move(None)
            return

        best = lines[0]
        if best.first_move:
            self.board_widget.set_best_move(best.first_move)

        if best.cp is None and best.mate is None:
            return

        self.board_widget.eval_bar.set_eval(best.cp, best.mate)
        depth = best.depth or 0
        if depth < 10:
            return

        # Cache the eval for the next move (White perspective, centipawns).
        self.last_eval = {
            "cp": best.cp,
            "mate": best.mate,
            "best_move": best.first_move,
        }

        # Backlog classification: step forward once the before-eval is ready.
        if (
            self._classify_queue
            and self.pending_classification_index < 0
            and self._classify_before_eval is None
        ):
            idx = self._classify_queue.pop(0)
            before_eval = dict(self.last_eval)
            self._classify_before_eval = before_eval  # mark as captured
            # Push the move to advance to after-position
            move = self.move_history[idx][0]
            self.board.push(move)
            self.board_widget.board.push(move)
            self.board_widget.update_board()
            self.board_widget.draw_interactive_overlays()
            self.move_list_widget.set_index(idx)
            self.pending_classification_index = idx
            self.pending_before_eval = before_eval
            self._refresh_engine(self.board.fen())
            return

        # Instant classification logic
        if (
            self.classify_enabled
            and self.pending_classification_index >= 0
            and depth >= 12
            and self.pending_before_eval is not None
        ):
            self._run_classification(best.cp, best.mate)
            # After classifying, process the next backlog item
            if self._classify_queue:
                self._process_backlog_step()

    def _run_classification(self, after_cp, after_mate):
        if self.pending_classification_index < 0:
            return

        move_obj, fen_before, fen_after, san = self.move_history[self.pending_classification_index]

        # Check if it is a book move first (compare by UCI to avoid SAN ambiguity)
        norm_fen = _normalize_fen(fen_before)
        node_id = self.opening_db.get_node_by_fen(norm_fen)
        is_book = self._is_book_move(node_id, move_obj.uci(), fen_before)

        if is_book:
            self.move_list_widget.update_classification(self.pending_classification_index, "Book")
            self.board_widget.set_last_move_classification("Book")
            self.pending_classification_index = -1
            return

        turn_color = chess.Board(fen_before).turn
        side_str = "white" if turn_color == chess.WHITE else "black"

        # Build classification context
        before_eval = self.pending_before_eval or {}
        ctx = ClassificationContext(
            san=san,
            uci=move_obj.uci(),
            best_move=before_eval.get('best_move'),
            eval_before_cp=before_eval.get('cp'),
            eval_before_mate=before_eval.get('mate'),
            eval_after_cp=after_cp,
            eval_after_mate=after_mate,
        )
        ctx.win_chance_before = get_win_probability(ctx.eval_before_cp, ctx.eval_before_mate)
        ctx.win_chance_after = get_win_probability(ctx.eval_after_cp, ctx.eval_after_mate)

        wpl = abs(ctx.win_chance_before - ctx.win_chance_after)

        classify_move(ctx, wpl, side_str)

        if ctx.classification:
            self.move_list_widget.update_classification(self.pending_classification_index, ctx.classification)
            self.board_widget.set_last_move_classification(ctx.classification)

        self.pending_classification_index = -1

    def closeEvent(self, event):
        self.session.shutdown()
        self._explorer_debounce.stop()
        for worker in list(self._explorer_workers):
            try:
                worker.wait(1500)
            except RuntimeError:
                pass
        if hasattr(self, 'opening_db') and self.opening_db:
            try:
                self.opening_db.close()
            except Exception:
                pass
        if hasattr(self, 'polyglot_manager') and self.polyglot_manager:
            try:
                self.polyglot_manager.close()
            except Exception:
                pass
        super().closeEvent(event)

    def refresh_styles(self):
        """Re-applies styles to explorer view components."""
        if hasattr(self, 'header_bar'):
            self.header_bar.setStyleSheet(Styles.get_header_bar_ext_style(bg_color=Styles.COLOR_BACKGROUND))
        if hasattr(self, 'title_lbl'):
            self.title_lbl.setStyleSheet(Styles.get_label_style(size=16, color=Styles.COLOR_TEXT_PRIMARY, bold=True) + " " + Styles.get_transparent_label_style())
        if hasattr(self, 'opening_badge'):
            self.opening_badge.setStyleSheet(Styles.get_label_style(size=13, color=Styles.COLOR_TEXT_SECONDARY) + "; padding: 0px 0px 0px 12px; " + Styles.get_transparent_label_style())
        if hasattr(self, 'btn_flip'):
            self.btn_flip.refresh_styles()
        if hasattr(self, 'btn_copy_fen'):
            self.btn_copy_fen.refresh_styles()
        if hasattr(self, 'btn_copy_pgn'):
            self.btn_copy_pgn.refresh_styles()
        if hasattr(self, 'splitter'):
            self.splitter.setStyleSheet(Styles.get_splitter_style())
        if hasattr(self, 'left_panel'):
            self.left_panel.setStyleSheet(Styles.get_background_style())
        if hasattr(self, 'lbl_black'):
            self.lbl_black.setStyleSheet(Styles.get_label_style(size=16, bold=True))
        if hasattr(self, 'lbl_white'):
            self.lbl_white.setStyleSheet(Styles.get_label_style(size=16, bold=True))
        if hasattr(self, 'right_panel'):
            self.right_panel.setStyleSheet(Styles.get_background_style())
        if hasattr(self, 'book_toggle'):
            self.book_toggle.refresh_styles()
        if hasattr(self, 'explorer_hint'):
            self.explorer_hint.setStyleSheet(
                Styles.get_label_style(size=11, color=Styles.COLOR_TEXT_MUTED)
                + "; padding: 2px 14px; "
                + Styles.get_transparent_label_style()
            )
        if hasattr(self, 'book_scroll'):
            self.book_scroll.setStyleSheet(Styles.get_scroll_area_style())
        if hasattr(self, 'book_container'):
            self.book_container.setStyleSheet(Styles.get_surface_style())
        if hasattr(self, 'lichess_attribution'):
            self.lichess_attribution.setStyleSheet(Styles.get_label_style(size=11, color=Styles.COLOR_TEXT_MUTED) + "; padding: 4px 14px; " + Styles.get_transparent_label_style())
            self.lichess_attribution.setText(f'powered by <a href="https://lichess.org" style="color: {Styles.COLOR_ACCENT}; text-decoration: none;">lichess.org</a>')
        if hasattr(self, 'move_list_label'):
            self.move_list_label.setStyleSheet(Styles.get_label_style(size=14, bold=True))
        if hasattr(self, 'move_input'):
            self.move_input.refresh_styles()
        if hasattr(self, 'engine_status_label'):
            self.engine_status_label.setStyleSheet(Styles.get_engine_status_style(Styles.COLOR_TEXT_MUTED))
        if hasattr(self, 'lines_widget'):
            self.lines_widget.refresh_styles()
        if hasattr(self, 'captured_white'):
            self.captured_white.refresh_styles()
        if hasattr(self, 'captured_black'):
            self.captured_black.refresh_styles()
        for child in self.findChildren(QWidget):
            child.style().unpolish(child)
            child.style().polish(child)

    def on_lichess_explorer_finished(self, data):
        self._clear_book_rows()

        moves = data.get("moves", [])
        for m in moves:
            san = m.get("san")
            white_wins = m.get("white", 0)
            draws = m.get("draws", 0)
            black_wins = m.get("black", 0)
            total = white_wins + draws + black_wins

            if total == 0:
                continue

            if total >= 1000000:
                count_str = f"{total / 1000000:.1f}M"
            elif total >= 1000:
                count_str = f"{total / 1000:.1f}K"
            else:
                count_str = str(total)

            w_pct = int(white_wins / total * 100)
            d_pct = int(draws / total * 100)
            b_pct = 100 - w_pct - d_pct

            stats = (w_pct, d_pct, b_pct, count_str)

            piece_symbol = None
            try:
                move_obj = self.board_widget.board.parse_san(san)
                self.board_widget.book_destinations.append(move_obj.to_square)
                piece = self.board_widget.board.piece_at(move_obj.from_square)
                if piece:
                    piece_symbol = piece.symbol()
            except Exception:
                pass

            row_widget = self._create_book_row_widget(
                san, None, piece_symbol, stats=stats
            )
            self.book_layout.addWidget(row_widget)
            self._book_row_widgets.append(row_widget)

        self._current_book_count = len(self._book_row_widgets)
        self._update_book_toggle()
        self.lichess_attribution.setVisible(self._current_book_count > 0)
        self.board_widget.draw_interactive_overlays()


"""
Explorer View - The main container for the Opening Explorer.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSplitter, 
    QScrollArea, QCheckBox, QLineEdit, QPushButton, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QByteArray
from PyQt6.QtGui import QColor, QPixmap, QPainter, QIcon
from PyQt6.QtSvg import QSvgRenderer
import chess

from src.gui.styles import Styles
from src.gui.board.explorer_board_widget import ExplorerBoardWidget
from src.gui.analysis.analysis_lines_widget import AnalysisLinesWidget
from src.gui.analysis.live_analysis import LiveAnalysisWorker
from src.gui.analysis.explorer_move_list import ExplorerMoveListWidget
from src.backend.analysis.opening_db import OpeningDB, _normalize_fen
from src.backend.analysis.polyglot_book import PolyglotBookManager
from src.backend.analysis.math_utils import get_win_probability
from src.backend.analysis.move_classifier import classify_move
from src.utils.path_utils import get_resource_path, get_user_data_dir
from src.utils.logger import logger
from src.gui.utils.gui_utils import clear_layout
from src.gui.components.loading_widget import LoadingOverlay
import os
from src.gui.analysis.captured import CapturedPiecesWidget

from dataclasses import dataclass
from typing import Optional

@dataclass
class ClassificationContext:
    san: str
    uci: str
    best_move: Optional[str] = None
    eval_before_cp: Optional[float] = None
    eval_before_mate: Optional[int] = None
    eval_after_cp: Optional[float] = None
    eval_after_mate: Optional[int] = None
    win_chance_before: float = 0.5
    win_chance_after: float = 0.5
    classification: Optional[str] = None
    explanation: Optional[str] = None

class BookRowWidget(QWidget):
    def __init__(self, san, parent=None):
        super().__init__(parent)
        self.san = san
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            p = self.parent()
            while p is not None:
                if isinstance(p, ExplorerView):
                    p.on_book_move_clicked(self.san)
                    break
                p = p.parent()

class ExplorerView(QWidget):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.engine_path = self.config_manager.get("engine_path", "stockfish")
        self.live_worker = LiveAnalysisWorker(self.engine_path, config_manager=self.config_manager)
        self.live_worker.info_ready.connect(self.on_live_analysis_update)
        self.live_worker.thinking_started.connect(self._on_engine_thinking_started)
        self.live_worker.thinking_stopped.connect(self._on_engine_thinking_stopped)
        
        # State tracking
        self.live_data = {}
        self._position_seq = 0  # monotonic counter for stale-signal detection
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
        
        # Loading overlay for background tasks
        self.loading_overlay = LoadingOverlay(self)
        
        # Show loading while opening DB initializes (first launch imports TSV)
        if not self.opening_db.is_populated():
            QTimer.singleShot(50, lambda: self.loading_overlay.start(
                "Loading Opening Book...",
                "Importing Lichess ECO database (first launch only)"
            ))
        
        self.live_worker.start()
        self._send_to_engine(self.board.fen())
        self.update_opening_db(self.board.fen())
        self.loading_overlay.stop()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header Bar Container
        self.header_bar = QFrame()
        self.header_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_BACKGROUND};
                border-bottom: 1px solid {Styles.COLOR_BORDER};
            }}
        """)
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(20, 6, 20, 6)

        # Title
        title_lbl = QLabel("Opening Explorer")
        title_lbl.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; background: transparent; border: none;")
        header_layout.addWidget(title_lbl)

        # Opening badge (inline after title)
        self.opening_badge = QLabel("Opening: -")
        self.opening_badge.setStyleSheet(f"font-size: 13px; color: {Styles.COLOR_TEXT_SECONDARY}; padding: 0px 0px 0px 12px; background: transparent; border: none;")
        header_layout.addWidget(self.opening_badge)

        header_layout.addStretch()

        # Action buttons header style
        btn_style = f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE};
                color: {Styles.COLOR_TEXT_SECONDARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border-color: {Styles.COLOR_ACCENT};
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
        """

        self.btn_flip = QPushButton("Flip Board")
        self.btn_flip.setStyleSheet(btn_style)
        self.btn_flip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_flip.clicked.connect(self._flip_board)
        header_layout.addWidget(self.btn_flip)

        self.btn_copy_fen = QPushButton("Copy FEN")
        self.btn_copy_fen.setStyleSheet(btn_style)
        self.btn_copy_fen.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_fen.clicked.connect(self._copy_fen)
        header_layout.addWidget(self.btn_copy_fen)

        self.btn_copy_pgn = QPushButton("Copy PGN")
        self.btn_copy_pgn.setStyleSheet(btn_style)
        self.btn_copy_pgn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_pgn.clicked.connect(self._copy_pgn)
        header_layout.addWidget(self.btn_copy_pgn)

        main_layout.addWidget(self.header_bar)
        
        # Content Area - Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        splitter.setStyleSheet(f"QSplitter::handle {{ background-color: {Styles.COLOR_BORDER}; }}")
        
        # ==========================================
        # LEFT PANEL (Board & Eval)
        # ==========================================
        left_panel = QWidget()
        self.left_layout = QVBoxLayout(left_panel)
        self.left_layout.setContentsMargins(8, 8, 8, 8)
        self.left_layout.setSpacing(6)
        
        # Opponent Label (Top)
        self.black_header_widget = QWidget()
        black_header = QHBoxLayout(self.black_header_widget)
        black_header.setContentsMargins(0, 0, 0, 0)
        lbl_black = QLabel("Black")
        lbl_black.setStyleSheet(Styles.get_label_style(size=16, bold=True))
        self.captured_black = CapturedPiecesWidget(side="black")
        black_header.addWidget(lbl_black)
        black_header.addWidget(self.captured_black)
        black_header.addStretch()
        self.left_layout.addWidget(self.black_header_widget)
        
        # Board Container (EvalBar + Board)
        board_container = QWidget()
        board_h_layout = QHBoxLayout(board_container)
        board_h_layout.setContentsMargins(0, 0, 0, 0)
        board_h_layout.setSpacing(10)
        
        self.board_widget = ExplorerBoardWidget()
        self.board_widget.move_made.connect(self.on_move_made)
        
        board_h_layout.addWidget(self.board_widget.eval_bar)
        board_h_layout.addWidget(self.board_widget)
        board_h_layout.setStretch(1, 1) # Board takes extra space
        
        self.left_layout.addWidget(board_container, stretch=1)
        
        # Player Label (Bottom)
        self.white_header_widget = QWidget()
        white_header = QHBoxLayout(self.white_header_widget)
        white_header.setContentsMargins(0, 0, 0, 0)
        lbl_white = QLabel("White")
        lbl_white.setStyleSheet(Styles.get_label_style(size=16, bold=True))
        self.captured_white = CapturedPiecesWidget(side="white")
        white_header.addWidget(lbl_white)
        white_header.addWidget(self.captured_white)
        white_header.addStretch()
        self.left_layout.addWidget(self.white_header_widget)
        
        splitter.addWidget(left_panel)
        
        # ==========================================
        # RIGHT PANEL (Controls & Analysis)
        # ==========================================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
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
            chk.setStyleSheet(f"""
                QCheckBox {{
                    color: {Styles.COLOR_TEXT_SECONDARY}; 
                    font-size: 12px; 
                    font-weight: 500;
                }}
            """)
            chk.setCursor(Qt.CursorShape.PointingHandCursor)
            toggles_layout.addWidget(chk)
            
        right_layout.addLayout(toggles_layout)
        
        # Engine Lines
        self.lines_widget = AnalysisLinesWidget()
        self.lines_widget.line_clicked.connect(self.on_engine_line_clicked)
        right_layout.addWidget(self.lines_widget)
        
        self.lines_widget.setVisible(False)
        
        # Book Moves Toggle + Table
        self._current_book_count = 0
        self.book_toggle = QPushButton("▶  Book Moves")
        self.book_toggle.setCheckable(True)
        self.book_toggle.setChecked(True)
        self.book_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.book_toggle.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                text-align: left;
                font-size: 14px;
                font-weight: bold;
                color: {Styles.COLOR_TEXT_PRIMARY};
                padding: 2px 0px;
            }}
            QPushButton:hover {{
                color: {Styles.COLOR_ACCENT};
            }}
        """)
        self.book_toggle.toggled.connect(self._toggle_book)
        right_layout.addWidget(self.book_toggle)
        
        self.book_scroll = QScrollArea()
        self.book_scroll.setWidgetResizable(True)
        self.book_scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
            }}
            QScrollBar:vertical {{
                background-color: {Styles.COLOR_BACKGROUND};
                width: 10px;
                margin: 0px 0px 0px 0px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {Styles.COLOR_BORDER_LIGHT};
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        
        self.book_container = QWidget()
        self.book_container.setStyleSheet(f"background-color: {Styles.COLOR_SURFACE};")
        self.book_layout = QVBoxLayout(self.book_container)
        self.book_layout.setContentsMargins(0, 0, 0, 0)
        self.book_layout.setSpacing(0)
        self.book_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.book_scroll.setWidget(self.book_container)
        
        right_layout.addWidget(self.book_scroll, stretch=1)
        
        # Move List Header (inline with move input)
        moves_header = QHBoxLayout()
        moves_header.setContentsMargins(0, 0, 0, 0)
        moves_header.setSpacing(8)
        move_list_label = QLabel("Moves")
        move_list_label.setStyleSheet(Styles.get_label_style(size=14, bold=True))
        moves_header.addWidget(move_list_label)
        self.move_input = QLineEdit()
        self.move_input.setPlaceholderText("type SAN move...")
        self.move_input.setToolTip("Enter a move in standard algebraic notation (e.g. e4, Nf3, O-O)")
        self.move_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Styles.COLOR_SURFACE};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {Styles.COLOR_ACCENT};
            }}
        """)
        self.move_input.setMinimumWidth(120)
        self.move_input.returnPressed.connect(self._on_move_text_entered)
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
        self.engine_status_label.setStyleSheet(f"font-size: 11px; color: {Styles.COLOR_TEXT_MUTED}; padding: 2px 0px;")
        right_layout.addWidget(self.engine_status_label)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([700, 450])
        main_layout.addWidget(splitter, 1)

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
        
        self.live_data = {}
        if self.chk_engine.isChecked():
            self._send_to_engine(fen)
        else:
            self.lines_widget.clear()
            self.board_widget.eval_bar.set_eval(0.0, None)
        # Trigger initial material update
        self._update_material()
        
    def _send_to_engine(self, fen):
        """Send a position to the live engine with a fresh sequence number
        so stale results from previous positions are discarded."""
        self._position_seq += 1
        self.live_data = {}
        self.lines_widget.clear()
        self.live_worker.set_chess960(self.is_chess960)
        self.live_worker.set_position(fen, seq=self._position_seq)

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
        for i, m in enumerate(self.move_history):
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
        # Wait for engine eval, then use it in on_live_analysis_update
        self._classify_before_eval = None
        self._send_to_engine(self.board.fen())

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
            
        self.board_widget.best_move_uci = None
        self.board_widget.last_move_classification = None
        self.board_widget.update_board()
        self.board_widget.draw_interactive_overlays()
        self.board_widget.move_made.connect(self.on_move_made)
        
        fen = self.board.fen()
        self.update_opening_db(fen)
        self._update_material()
        
        self.live_data = {}
        if self.chk_engine.isChecked():
            self._send_to_engine(fen)
        else:
            self.lines_widget.clear()
            self.board_widget.eval_bar.set_eval(0.0, None)

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
        if self._is_book_move(node_id, move.uci(), fen_before):
            if self.classify_enabled:
                self.move_list_widget.update_classification(self.pending_classification_index, "Book")
                self.pending_classification_index = -1
                self.board_widget.last_move_classification = "Book"
                
        # Update engine and opening db
        self.live_data = {}
        if self.chk_engine.isChecked():
            self._send_to_engine(fen_after)
        else:
            self.lines_widget.clear()
            self.board_widget.eval_bar.set_eval(0.0, None)
            
        self.update_opening_db(fen_after)

    def _get_piece_pixmap(self, symbol, size=18):
        cache_key = (symbol, size)
        if not hasattr(self, '_piece_pixmap_cache'):
            self._piece_pixmap_cache = {}
        if cache_key not in self._piece_pixmap_cache:
            from src.gui.board.piece_themes import _load_theme_cached
            pieces_svg = _load_theme_cached("Standard")
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

    def _create_book_row_widget(self, san, info_text, piece_symbol=None):
        row_widget = BookRowWidget(san, self)
        row_widget.setStyleSheet(f"""
            QWidget {{
                border-bottom: 1px solid {Styles.COLOR_BORDER};
            }}
            QWidget:hover {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
            }}
        """)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(14, 10, 14, 10)
        row_layout.setSpacing(8)
        
        if piece_symbol:
            pixmap = self._get_piece_pixmap(piece_symbol)
            if pixmap:
                icon_label = QLabel()
                icon_label.setPixmap(pixmap)
                icon_label.setFixedSize(18, 18)
                icon_label.setStyleSheet("border: none; background: transparent;")
                row_layout.addWidget(icon_label)
        
        lbl_san = QLabel(san)
        lbl_san.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: bold; font-size: 15px; border: none; background: transparent;")
        row_layout.addWidget(lbl_san)
        
        if info_text:
            lbl_info = QLabel(info_text)
            lbl_info.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 13px; font-style: italic; border: none; background: transparent;")
            lbl_info.setMinimumWidth(0)
            row_layout.addWidget(lbl_info, stretch=1)
        else:
            row_layout.addStretch()
        
        return row_widget

    def update_opening_db(self, fen):
        norm_fen = _normalize_fen(fen)
        node_id = self.opening_db.get_node_by_fen(norm_fen)
        self.board_widget.book_destinations = []
        
        # Remove all existing book row widgets
        if hasattr(self, '_book_row_widgets'):
            for w in self._book_row_widgets:
                self.book_layout.removeWidget(w)
                w.deleteLater()
        self._book_row_widgets = []
        
        if not self.board_widget.board.move_stack:
            self.opening_badge.setText("Opening: -")
        
        # --- Update opening badge from SQLite (always) ---
        if node_id is not None:
            openings = self.opening_db.get_openings_at_node(node_id)
            if openings:
                best_name = max(openings, key=lambda x: len(x[1]))[1]
                best_eco = max(openings, key=lambda x: len(x[1]))[0]
                self.opening_badge.setText(f"Opening: {best_eco} - {best_name}")
        
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
                        row_widget = self._create_book_row_widget(san, weight_str, piece_symbol)
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
                            child_openings = self.opening_db.get_openings_at_node(child_node_id)
                            if child_openings:
                                best_name = max(child_openings, key=lambda x: len(x[1]))[1]
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
                    row_widget = self._create_book_row_widget(san, move_name, piece_symbol)
                    self.book_layout.addWidget(row_widget)
                    self._book_row_widgets.append(row_widget)
            
        self._current_book_count = len(self._book_row_widgets)
        arrow = "▼" if self.book_toggle.isChecked() else "▶"
        self.book_toggle.setText(f"{arrow}  Book Moves  ({self._current_book_count})")
        
        if self._current_book_count > 0:
            self.book_toggle.show()
            if not self.book_toggle.isChecked():
                self.book_scroll.hide()
            else:
                self.book_scroll.show()
        else:
            self.book_toggle.hide()
            self.book_scroll.hide()
            
        self.board_widget.draw_interactive_overlays()

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
            self.move_input.setStyleSheet(f"""
                QLineEdit {{
                    background-color: #3d1a1a;
                    color: {Styles.COLOR_TEXT_PRIMARY};
                    border: 1px solid #e74c3c;
                    border-radius: 6px;
                    padding: 2px 8px;
                    font-size: 12px;
                    font-weight: 600;
                }}
            """)
            QTimer.singleShot(1000, self._reset_move_input_style)

    def _reset_move_input_style(self):
        self.move_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Styles.COLOR_SURFACE};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {Styles.COLOR_ACCENT};
            }}
        """)

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
        # After removal, only board_container remains at index 0
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
        self.engine_status_label.setStyleSheet(f"font-size: 11px; color: #27ae60; padding: 2px 0px;")
        QTimer.singleShot(2000, self._reset_status)

    def _copy_pgn(self):
        import chess.pgn
        from datetime import date
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
        self.engine_status_label.setStyleSheet(f"font-size: 11px; color: #27ae60; padding: 2px 0px;")
        QTimer.singleShot(2000, self._reset_status)

    def _reset_status(self):
        self.engine_status_label.setText("⬤ Ready")
        self.engine_status_label.setStyleSheet(f"font-size: 11px; color: #27ae60; padding: 2px 0px;")

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
        self.board_widget.board = self.board.copy()
        self.board_widget.selected_square = None
        self.board_widget.legal_destinations = []
        self.board_widget.best_move_uci = None
        self.board_widget.last_move_classification = None
        self.board_widget.update_board()
        self.board_widget.draw_interactive_overlays()
        
        # Sync move list
        self.move_list_widget.set_index(index)
        
        # Sync engine & DB
        fen = self.board.fen()
        self.live_data = {}
        if self.chk_engine.isChecked():
            self._send_to_engine(fen)
        else:
            self.lines_widget.clear()
            self.board_widget.eval_bar.set_eval(0.0, None)
            
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

    def _on_engine_thinking_started(self):
        self.engine_status_label.setText("⬤ Analyzing...")
        self.engine_status_label.setStyleSheet(f"font-size: 11px; color: #e67e22; padding: 2px 0px;")
        # Discard stale analysis data from previous position so old info_ready
        # signals don't mix with new position data
        self.live_data = {}

    def _on_engine_thinking_stopped(self):
        self.engine_status_label.setText("⬤ Ready")
        self.engine_status_label.setStyleSheet(f"font-size: 11px; color: #27ae60; padding: 2px 0px;")

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
        self.board_widget.show_legal_moves = checked
        self.board_widget.draw_interactive_overlays()

    def on_engine_toggled(self, enabled):
        self.lines_widget.setVisible(enabled)
        if enabled:
            self._send_to_engine(self.board_widget.board.fen())
        else:
            self.live_worker.set_position(None)
            self.lines_widget.clear()

    def on_live_analysis_update(self, info):
        # Discard stale results from previous positions
        if info.get("seq", 0) != self._position_seq:
            return
        multipv_id = info.get("multipv", 1)
        self.live_data[multipv_id] = info
        sorted_lines = sorted(self.live_data.values(), key=lambda x: x.get("multipv", 1))
        
        self.lines_widget.update_lines(sorted_lines, self.board_widget.board.turn)
        
        best_mate = None
        best_cp = None
        
        if len(sorted_lines) > 0:
            best_line = sorted_lines[0]
            
            # Draw best move arrow
            if "pv_uci" in best_line and len(best_line["pv_uci"]) > 0:
                self.board_widget.set_best_move(best_line["pv_uci"][0])
                
            # Extract raw eval relative to side to move
            raw_cp = best_line.get("cp")
            raw_mate = best_line.get("mate")
            
            # Only update if we actually received a score
            if raw_cp is not None or raw_mate is not None:
                # Convert to White's perspective
                if self.board_widget.board.turn == chess.BLACK:
                    best_cp = -raw_cp if raw_cp is not None else None
                    best_mate = -raw_mate if raw_mate is not None else None
                else:
                    best_cp = raw_cp
                    best_mate = raw_mate
                    
                self.board_widget.eval_bar.set_eval(best_cp, best_mate)

                depth = info.get("depth", 0)

                # Cache eval for next move (store in White's perspective, centipawns)
                if depth >= 10:
                    self.last_eval = {
                        'cp': best_cp,
                        'mate': best_mate,
                        'best_move': best_line["pv_uci"][0] if "pv_uci" in best_line and len(best_line["pv_uci"]) > 0 else None
                    }

                # Backlog classification: step forward when before-eval is ready
                if (self._classify_queue and self.pending_classification_index < 0
                        and self._classify_before_eval is None and depth >= 10
                        and self.last_eval is not None):
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
                    self._send_to_engine(self.board.fen())
                    return

                # Instant Classification Logic
                if self.classify_enabled and self.pending_classification_index >= 0 and depth >= 12:
                    if self.pending_before_eval is not None:
                        self._run_classification(best_cp, best_mate)
                        # After classifying, process next backlog item
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
            self.board_widget.last_move_classification = "Book"
            self.board_widget.draw_interactive_overlays()
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
            self.board_widget.last_move_classification = ctx.classification
            self.board_widget.draw_interactive_overlays()
            
        self.pending_classification_index = -1

    def closeEvent(self, event):
        self.live_worker.stop()
        super().closeEvent(event)

    def refresh_styles(self):
        self.header_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_BACKGROUND};
                border-bottom: 1px solid {Styles.COLOR_BORDER};
            }}
        """)
        self.setStyleSheet(Styles.get_theme())

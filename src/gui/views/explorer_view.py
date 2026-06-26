"""
Explorer View - The main container for the Opening Explorer.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSplitter, 
    QScrollArea, QCheckBox, QLineEdit, QPushButton
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
import chess

from src.gui.styles import Styles
from src.gui.board.explorer_board_widget import ExplorerBoardWidget
from src.gui.analysis.analysis_lines_widget import AnalysisLinesWidget
from src.gui.analysis.live_analysis import LiveAnalysisWorker
from src.gui.analysis.explorer_move_list import ExplorerMoveListWidget
from src.backend.analysis.opening_db import OpeningDB, _normalize_fen
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
        header_layout.addStretch()
        
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
        right_layout.setContentsMargins(8, 12, 12, 8)
        right_layout.setSpacing(8)
        
        # Opening Badge (No border, clean text)
        self.opening_badge = QLabel("Opening: -")
        self.opening_badge.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; padding: 0px 0px 5px 0px;")
        self.opening_badge.setWordWrap(True)
        right_layout.addWidget(self.opening_badge)
        
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
        
        # Action Toolbar
        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 6)
        action_layout.setSpacing(8)
        
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
        action_layout.addWidget(self.btn_flip)
        
        self.btn_copy_fen = QPushButton("Copy FEN")
        self.btn_copy_fen.setStyleSheet(btn_style)
        self.btn_copy_fen.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_fen.clicked.connect(self._copy_fen)
        action_layout.addWidget(self.btn_copy_fen)
        
        self.btn_copy_pgn = QPushButton("Copy PGN")
        self.btn_copy_pgn.setStyleSheet(btn_style)
        self.btn_copy_pgn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_pgn.clicked.connect(self._copy_pgn)
        action_layout.addWidget(self.btn_copy_pgn)
        
        action_layout.addStretch()
        right_layout.addLayout(action_layout)
        
        # Engine Lines
        self.lines_widget = AnalysisLinesWidget()
        self.lines_widget.line_clicked.connect(self.on_engine_line_clicked)
        right_layout.addWidget(self.lines_widget)
        
        self.lines_widget.setVisible(False)
        
        # Book Moves Table
        self.book_label = QLabel("Book Moves")
        self.book_label.setStyleSheet(Styles.get_label_style(size=14, bold=True))
        right_layout.addWidget(self.book_label)
        
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
        
        right_layout.addWidget(self.book_scroll, stretch=2)
        
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
        try:
            test_board = chess.Board(fen)
        except ValueError as e:
            logger.error(f"Invalid FEN: {fen} — {e}")
            return
            
        self.board = test_board
        self.move_history = []
        self.move_list_widget.clear()
        self.pending_classification_index = -1
        self.last_eval = None
        self.pending_before_eval = None
        
        self.board_widget.load_fen(fen)
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
        self.live_worker.set_position(fen, seq=self._position_seq)

    def _is_book_move(self, node_id, uci, fen_before):
        """Check if a move (by UCI) is a book move at the given node."""
        try:
            board = chess.Board(fen_before)
            candidates = self.opening_db.get_children(node_id)
            for candidate_san in candidates:
                candidate_move = board.parse_san(candidate_san)
                if candidate_move.uci() == uci:
                    return True
        except Exception as e:
            logger.warning(f"Error checking book move: {e}")
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

    def load_board_state(self, source_board, source_moves=None):
        """Loads a full board state including its move stack history and optional existing classifications."""
        self.board = chess.Board(source_board.starting_fen)
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
        self.board_widget.load_fen(source_board.starting_fen)
        
        # Play out the move stack
        for i, move in enumerate(source_board.move_stack):
            fen_before = self.board.fen()
            san = self.board.san(move)
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
        san = self.board.san(move)
        
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
        if node_id is not None and self._is_book_move(node_id, move.uci(), fen_before):
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

    def _create_book_row_widget(self, san, move_name):
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
        
        lbl_san = QLabel(san)
        lbl_san.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: bold; font-size: 15px; border: none; background: transparent;")
        row_layout.addWidget(lbl_san)
        
        if move_name:
            lbl_name = QLabel(move_name)
            lbl_name.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 13px; font-style: italic; border: none; background: transparent;")
            lbl_name.setMinimumWidth(0)
            row_layout.addWidget(lbl_name, stretch=1)
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
        
        has_books = False
        
        if not self.board_widget.board.move_stack:
            self.opening_badge.setText("Opening: -")
            
        if node_id is not None:
            openings = self.opening_db.get_openings_at_node(node_id)
            if openings:
                best_name = max(openings, key=lambda x: len(x[1]))[1]
                best_eco = max(openings, key=lambda x: len(x[1]))[0]
                self.opening_badge.setText(f"Opening: {best_eco} - {best_name}")
                
            candidates = self.opening_db.get_children(node_id)
            if candidates:
                has_books = True
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
                        logger.warning(f"Error processing book move {san}: {e}")
                        if push_done:
                            try:
                                self.board_widget.board.pop()
                            except Exception:
                                pass
                    
                    row_widget = self._create_book_row_widget(san, move_name)
                    self.book_layout.addWidget(row_widget)
                    self._book_row_widgets.append(row_widget)
            
        if has_books:
            self.book_label.show()
            self.book_scroll.show()
        else:
            self.book_label.hide()
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
                logger.debug(f"Move input error: {e}")
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

    def _flip_board(self):
        self.board_widget.flip_board()
        self.board_widget.draw_interactive_overlays()
        # Swap captured pieces headers around the board
        self.left_layout.removeWidget(self.white_header_widget)
        self.left_layout.removeWidget(self.black_header_widget)
        if self.board_widget.is_flipped:
            self.left_layout.insertWidget(2, self.white_header_widget)
            self.left_layout.insertWidget(0, self.black_header_widget)
        else:
            self.left_layout.insertWidget(0, self.black_header_widget)
            self.left_layout.insertWidget(2, self.white_header_widget)

    def _copy_fen(self):
        fen = self.board_widget.board.fen()
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(fen)
        self.engine_status_label.setText("✓ FEN copied")
        self.engine_status_label.setStyleSheet(f"font-size: 11px; color: #27ae60; padding: 2px 0px;")
        QTimer.singleShot(2000, self._reset_status)

    def _copy_pgn(self):
        import chess.pgn
        starting_fen = self.board_widget.board.starting_fen if hasattr(self.board_widget.board, 'starting_fen') else chess.STARTING_FEN
        board = chess.Board(starting_fen)
        game = chess.pgn.Game()
        if starting_fen != chess.STARTING_FEN:
            game.headers["FEN"] = starting_fen
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
            self.board = chess.Board()
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
        is_book = False
        if node_id is not None:
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

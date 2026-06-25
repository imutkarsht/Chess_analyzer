"""
Explorer View - The main container for the Opening Explorer.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSplitter, 
    QScrollArea, QCheckBox
)
from PyQt6.QtCore import Qt
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
import os
from src.gui.analysis.captured import CapturedPiecesWidget

class DummyMove:
    pass

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
        self.board = chess.Board()
        self.move_history = [] # list of (Move object, FEN before, FEN after, SAN)
        
        # Classification State
        self.last_eval = None
        self.pending_classification_index = -1
        self.pending_before_eval = None
        
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
        self.live_worker.start()
        self.live_worker.set_position(self.board.fen())
        self.update_opening_db(self.board.fen())

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
        header_layout.setContentsMargins(40, 12, 40, 12)

        # Title
        title_lbl = QLabel("Opening Explorer")
        title_lbl.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; background: transparent; border: none;")
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
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(10)
        
        # Opponent Label (Top)
        black_header = QHBoxLayout()
        lbl_black = QLabel("Black")
        lbl_black.setStyleSheet(Styles.get_label_style(size=16, bold=True))
        self.captured_black = CapturedPiecesWidget(side="black")
        black_header.addWidget(lbl_black)
        black_header.addWidget(self.captured_black)
        black_header.addStretch()
        left_layout.addLayout(black_header)
        
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
        
        left_layout.addWidget(board_container, stretch=1)
        
        # Player Label (Bottom)
        white_header = QHBoxLayout()
        lbl_white = QLabel("White")
        lbl_white.setStyleSheet(Styles.get_label_style(size=16, bold=True))
        self.captured_white = CapturedPiecesWidget(side="white")
        white_header.addWidget(lbl_white)
        white_header.addWidget(self.captured_white)
        white_header.addStretch()
        left_layout.addLayout(white_header)
        
        splitter.addWidget(left_panel)
        
        # ==========================================
        # RIGHT PANEL (Controls & Analysis)
        # ==========================================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 20, 20, 20)
        right_layout.setSpacing(15)
        
        # Opening Badge (No border, clean text)
        self.opening_badge = QLabel("Opening: -")
        self.opening_badge.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; padding: 0px 0px 5px 0px;")
        self.opening_badge.setWordWrap(True)
        right_layout.addWidget(self.opening_badge)
        
        # Toggles Bar
        toggles_layout = QHBoxLayout()
        toggles_layout.setContentsMargins(0, 0, 0, 10)
        toggles_layout.setSpacing(12)
        
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
            
        toggles_layout.addStretch()
        right_layout.addLayout(toggles_layout)
        
        # Engine Lines
        self.lines_widget = AnalysisLinesWidget()
        self.lines_widget.line_clicked.connect(self.on_engine_line_clicked)
        right_layout.addWidget(self.lines_widget)
        
        # Book Moves Table
        self.book_label = QLabel("Book Moves")
        self.book_label.setStyleSheet(Styles.get_label_style(size=14, bold=True))
        right_layout.addWidget(self.book_label)
        
        self.book_scroll = QScrollArea()
        self.book_scroll.setWidgetResizable(True)
        self.book_scroll.setMaximumHeight(180)
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
        
        right_layout.addWidget(self.book_scroll)
        
        # Move List
        move_list_label = QLabel("Moves")
        move_list_label.setStyleSheet(Styles.get_label_style(size=14, bold=True))
        right_layout.addWidget(move_list_label)
        
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
            self.live_worker.set_position(fen)
        else:
            self.lines_widget.clear()
            self.board_widget.eval_bar.set_eval(0.0, None)
        # Trigger initial material update
        self._update_material()
        
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
            
        self.board_widget.update_board()
        self.board_widget.draw_interactive_overlays()
        self.board_widget.move_made.connect(self.on_move_made)
        
        fen = self.board.fen()
        self.update_opening_db(fen)
        
        self.live_data = {}
        if self.chk_engine.isChecked():
            self.live_worker.set_position(fen)
        else:
            self.lines_widget.clear()
            self.board_widget.eval_bar.set_eval(0.0, None)

    def on_move_made(self, fen):
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
            self.live_worker.set_position(fen_after)
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
        row_layout.setContentsMargins(12, 8, 12, 8)
        
        lbl_san = QLabel(san)
        lbl_san.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: bold; font-size: 14px; border: none; background: transparent;")
        row_layout.addWidget(lbl_san)
        
        if move_name:
            lbl_name = QLabel(move_name)
            lbl_name.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; font-style: italic; border: none; background: transparent;")
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
                    try:
                        move = self.board_widget.board.parse_san(san)
                        self.board_widget.board.push(move)
                        child_fen = _normalize_fen(self.board_widget.board.fen())
                        self.board_widget.board.pop()
                        
                        child_node_id = self.opening_db.get_node_by_fen(child_fen)
                        if child_node_id is not None:
                            child_openings = self.opening_db.get_openings_at_node(child_node_id)
                            if child_openings:
                                best_name = max(child_openings, key=lambda x: len(x[1]))[1]
                                move_name = best_name
                        
                        self.board_widget.book_destinations.append(move.to_square)
                    except Exception as e:
                        logger.warning(f"Error processing book move {san}: {e}")
                        if self.board_widget.board.move_stack:
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
            self.board_widget.attempt_move(move.from_square, move.to_square)
        except Exception as e:
            logger.warning(f"Failed to play book move {san}: {e}")

    def on_engine_line_clicked(self, uci_move):
        try:
            move = chess.Move.from_uci(uci_move)
            self.board_widget.attempt_move(move.from_square, move.to_square)
        except Exception as e:
            logger.warning(f"Failed to play engine line move {uci_move}: {e}")

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
        self.board_widget.update_board()
        self.board_widget.draw_interactive_overlays()
        
        # Sync move list
        self.move_list_widget.set_index(index)
        
        # Sync engine & DB
        fen = self.board.fen()
        self.live_data = {}
        if self.chk_engine.isChecked():
            self.live_worker.set_position(fen)
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
            # Clear pending classifications
            if self.pending_classification_index >= 0:
                self.move_list_widget.set_pending_classification(self.pending_classification_index, False)
            self.pending_classification_index = -1
            self.pending_before_eval = None
            
    def on_legal_moves_toggled(self, checked):
        self.board_widget.show_legal_moves = checked
        self.board_widget.draw_interactive_overlays()

    def on_engine_toggled(self, enabled):
        if enabled:
            self.live_worker.set_position(self.board_widget.board.fen())
        else:
            self.live_worker.set_position(None)
            self.lines_widget.clear()

    def on_live_analysis_update(self, info):
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

                # Instant Classification Logic
                depth = info.get("depth", 0)
                if self.classify_enabled and self.pending_classification_index >= 0 and depth >= 12:
                    if self.pending_before_eval is not None:
                        self._run_classification(best_cp, best_mate)
                        
                # Cache eval for next move (store in White's perspective, centipawns)
                if depth >= 10:
                    self.last_eval = {
                        'cp': best_cp,
                        'mate': best_mate,
                        'best_move': best_line["pv_uci"][0] if "pv_uci" in best_line and len(best_line["pv_uci"]) > 0 else None
                    }

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
        
        # Build dummy move object for classify_move
        dm = DummyMove()
        dm.san = san
        dm.uci = move_obj.uci()
        
        before_eval = self.pending_before_eval or {}
        dm.best_move = before_eval.get('best_move')
        dm.eval_before_cp = before_eval.get('cp')
        dm.eval_before_mate = before_eval.get('mate')
        
        dm.eval_after_cp = after_cp
        dm.eval_after_mate = after_mate
        
        dm.win_chance_before = get_win_probability(dm.eval_before_cp, dm.eval_before_mate)
        dm.win_chance_after = get_win_probability(dm.eval_after_cp, dm.eval_after_mate)
        
        wpl = abs(dm.win_chance_before - dm.win_chance_after) # simplify WPL
        
        classify_move(dm, wpl, side_str)
        
        if hasattr(dm, 'classification') and dm.classification:
            self.move_list_widget.update_classification(self.pending_classification_index, dm.classification)
            self.board_widget.last_move_classification = dm.classification
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

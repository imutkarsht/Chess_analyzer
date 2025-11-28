from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QLabel, QGridLayout, QFrame, QHBoxLayout, 
                             QPushButton, QAbstractItemView, QCheckBox, QTabWidget, QSizePolicy)
from .graph_widget import GraphWidget
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QBrush, QFont, QIcon
from .styles import Styles
from ..utils.resources import ResourceManager
from ..utils.resources import ResourceManager
from ..utils.logger import logger
from ..utils.resources import ResourceManager
from ..utils.logger import logger
import chess
from .live_analysis import LiveAnalysisWorker
from PyQt6.QtCore import QTimer, QThread
from ..backend.gemini_service import GeminiService
from PyQt6.QtWidgets import QTextEdit, QMessageBox, QInputDialog, QLineEdit
from ..utils.config import ConfigManager

class StatCard(QFrame):
    def __init__(self, title, value, color=None):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 10px;
            }}
            QLabel {{ border: none; background: transparent; }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        lbl_value = QLabel(str(value))
        lbl_value.setStyleSheet(f"color: {color if color else Styles.COLOR_TEXT_PRIMARY}; font-size: 18px; font-weight: bold;")
        lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_value)

class CapturedPiecesWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 5px;
            }}
            {Styles.CAPTURED_PIECES_STYLE}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # White captured (pieces lost by Black)
        self.white_captured_layout = QHBoxLayout()
        self.white_captured_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addLayout(self.white_captured_layout)
        
        # Black captured (pieces lost by White)
        self.black_captured_layout = QHBoxLayout()
        self.black_captured_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addLayout(self.black_captured_layout)
        
    def update_captured(self, fen):
        # Clear existing
        self._clear_layout(self.white_captured_layout)
        self._clear_layout(self.black_captured_layout)
        
        if not fen:
            return

        # Standard piece counts
        starting_pieces = {
            'p': 8, 'n': 2, 'b': 2, 'r': 2, 'q': 1,
            'P': 8, 'N': 2, 'B': 2, 'R': 2, 'Q': 1
        }
        
        # Count current pieces
        current_pieces = {}
        board_part = fen.split(' ')[0]
        for char in board_part:
            if char.isalpha():
                current_pieces[char] = current_pieces.get(char, 0) + 1
                
        # Calculate captured (Starting - Current)
        # Pieces captured by White are Black pieces (lowercase)
        # Pieces captured by Black are White pieces (uppercase)
        
        piece_values = {'p': 1, 'n': 3, 'b': 3, 'r': 5, 'q': 9}
        
        white_score = 0
        black_score = 0
        
        # White captured (Black pieces)
        for p in ['p', 'n', 'b', 'r', 'q']:
            count = starting_pieces[p] - current_pieces.get(p, 0)
            if count > 0:
                self._add_pieces(self.white_captured_layout, p, count, Styles.COLOR_PIECE_BLACK)
                white_score += count * piece_values[p]
                
        # Black captured (White pieces)
        for p in ['P', 'N', 'B', 'R', 'Q']:
            count = starting_pieces[p] - current_pieces.get(p, 0)
            if count > 0:
                self._add_pieces(self.black_captured_layout, p, count, Styles.COLOR_PIECE_WHITE)
                black_score += count * piece_values[p.lower()]
                
        # Add score difference
        diff = white_score - black_score
        if diff > 0:
            lbl = QLabel(f"+{diff}")
            lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: bold;")
            self.white_captured_layout.addWidget(lbl)
        elif diff < 0:
            lbl = QLabel(f"+{-diff}")
            lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: bold;")
            self.black_captured_layout.addWidget(lbl)

    def _add_pieces(self, layout, piece, count, color):
        # Using unicode pieces for now, could use icons
        piece_map = {
            'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛',
            'P': '♟', 'N': '♞', 'B': '♝', 'R': '♜', 'Q': '♛'
        }
        
        for _ in range(count):
            lbl = QLabel(piece_map.get(piece, '?'))
            lbl.setStyleSheet(f"color: {color}; font-size: 18px;")
            layout.addWidget(lbl)
            
    def _clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

class AnalysisLinesWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 10px;
            }}
            QLabel {{ border: none; background: transparent; }}
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(5)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        self.lines_layout = QVBoxLayout()
        self.layout.addLayout(self.lines_layout)
        
    def update_lines(self, multi_pvs, turn_color):
        self._clear_layout(self.lines_layout)
        
        if not multi_pvs:
            lbl = QLabel("No analysis available")
            lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-style: italic;")
            self.lines_layout.addWidget(lbl)
            return
            
        # Sort by multipv id if available, or score?
        # Usually sorted by score descending (for White) or ascending (for Black)
        # But engine usually returns them in order of multipv id (1 is best).
        
        # If live analysis, we might get partial updates.
        # We should probably store the lines and update them individually?
        # For now, full redraw is fine.
        
        for i, pv_data in enumerate(multi_pvs):
            # Create a row for each line
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(10)
            
            # Depth (if available)
            depth = pv_data.get("depth", "?")
            lbl_depth = QLabel(f"d{depth}")
            lbl_depth.setFixedWidth(30)
            lbl_depth.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 10px;")
            row_layout.addWidget(lbl_depth)
            
            # Eval
            score_val = pv_data.get("score_value", "?")
            
            display_score = score_val
            
            try:
                if not score_val.startswith("M"):
                    val = float(score_val)
                    if turn_color == chess.BLACK:
                        val = -val
                    display_score = f"{val:+.2f}"
            except:
                pass

            lbl_eval = QLabel(display_score)
            lbl_eval.setFixedWidth(50)
            lbl_eval.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: bold;")
            row_layout.addWidget(lbl_eval)
            
            # PV (SAN preferred)
            pv_text = pv_data.get("pv_san", "")
            if not pv_text:
                pv_moves = pv_data.get("pv", [])
                pv_text = " ".join(pv_moves[:5]) # Fallback to UCI
            
            lbl_pv = QLabel(pv_text)
            lbl_pv.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY};")
            lbl_pv.setWordWrap(True)
            row_layout.addWidget(lbl_pv)
            
            self.lines_layout.addWidget(row_widget)

    def _clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

class GameControlsWidget(QWidget):
    first_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    last_clicked = pyqtSignal()
    flip_clicked = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(10)
        
        self.btn_first = self._create_btn("<<", self.first_clicked)
        self.btn_prev = self._create_btn("<", self.prev_clicked)
        self.btn_next = self._create_btn(">", self.next_clicked)
        self.btn_last = self._create_btn(">>", self.last_clicked)
        self.btn_flip = self._create_btn("Flip", self.flip_clicked)
        
        layout.addWidget(self.btn_first)
        layout.addWidget(self.btn_prev)
        layout.addWidget(self.btn_next)
        layout.addWidget(self.btn_last)
        layout.addStretch()
        layout.addWidget(self.btn_flip)
        
    def _create_btn(self, text, signal):
        btn = QPushButton(text)
        btn.setStyleSheet(Styles.CONTROL_BUTTON_STYLE)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(signal.emit)
        return btn

class MoveListPanel(QWidget):
    move_selected = pyqtSignal(int)
    
    def __init__(self, engine_path="stockfish"):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)
        
        self.resource_manager = ResourceManager()
        self.current_game = None
        
        # Live Analysis
        self.engine_path = engine_path
        self.live_worker = LiveAnalysisWorker(self.engine_path)
        self.live_worker.info_ready.connect(self.on_live_analysis_update)
        self.live_worker.start()
        
        self.live_data = {}
        self.current_turn = chess.WHITE
        
        self.analysis_timer = QTimer()
        self.analysis_timer.setSingleShot(True)
        self.analysis_timer.setInterval(4000) # 4 seconds delay
        self.analysis_timer.timeout.connect(self.start_live_analysis)
        
        # Move List Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["#", "White", "Black"])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 40) # Reduced width
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.cellClicked.connect(self.on_cell_clicked)
        
        # Tighter table styling
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 4px;
                gridline-color: {Styles.COLOR_BORDER};
            }}
            QTableWidget::item {{
                padding: 2px 4px; /* Reduced padding */
                border-bottom: 1px solid {Styles.COLOR_SURFACE_LIGHT};
            }}
            QTableWidget::item:selected {{
                background-color: {Styles.COLOR_HIGHLIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
        """)
        
        self.layout.addWidget(self.table)
        
        # Analysis Lines
        self.lines_widget = AnalysisLinesWidget()
        self.layout.addWidget(self.lines_widget)
        
        # Stretch factors
        self.layout.setStretch(0, 3) # Table
        self.layout.setStretch(1, 1) # Lines

    def set_game(self, game_analysis):
        self.current_game = game_analysis
        self.refresh()
        
    def refresh(self):
        if not self.current_game:
            return
            
        self.table.setRowCount(0)
        moves = self.current_game.moves
        if not moves:
            return
            
        last_move_num = moves[-1].move_number
        self.table.setRowCount(last_move_num)
        
        for i, move in enumerate(moves):
            row = move.move_number - 1
            col = 1 if i % 2 == 0 else 2
            
            # Set Move Number
            if col == 1:
                num_item = QTableWidgetItem(str(move.move_number))
                num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                num_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                num_item.setForeground(QBrush(QColor(Styles.COLOR_TEXT_SECONDARY)))
                self.table.setItem(row, 0, num_item)
            
            self._set_move_item(row, col, move, i)
            
        self.lines_widget.update_lines([], chess.WHITE)

    def _set_move_item(self, row, col, move, index):
        item = QTableWidgetItem(move.san)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setData(Qt.ItemDataRole.UserRole, index)
        
        if move.classification:
            icon = self.resource_manager.get_icon(move.classification)
            if not icon.isNull():
                item.setIcon(icon)
        
        color = Styles.get_class_color(move.classification)
        if color:
             item.setForeground(QBrush(QColor(color)))
             
        self.table.setItem(row, col, item)

    def on_cell_clicked(self, row, col):
        item = self.table.item(row, col)
        if item:
            index = item.data(Qt.ItemDataRole.UserRole)
            if index is not None:
                self.move_selected.emit(index)

    def select_move(self, index):
        if not self.current_game:
            return
            
        if index < 0:
            self.table.clearSelection()
            self.lines_widget.update_lines([], chess.WHITE)
            return
            
        if index >= len(self.current_game.moves):
            return
            
        row = index // 2
        col = 1 if index % 2 == 0 else 2
        
        self.table.setCurrentCell(row, col)
        self.table.scrollToItem(self.table.item(row, col))
        
        move = self.current_game.moves[index]
        turn = chess.WHITE if index % 2 == 0 else chess.BLACK
        self.lines_widget.update_lines(move.multi_pvs, turn)
        
        self.current_turn = turn
        self.live_data = {}
        self.analysis_timer.start()

    def start_live_analysis(self):
        if not self.current_game:
            return
        index = self.table.currentRow() * 2 + (self.table.currentColumn() - 1)
        if index < 0 or index >= len(self.current_game.moves):
            return
        move = self.current_game.moves[index]
        self.live_worker.set_position(move.fen_before)

    def on_live_analysis_update(self, info):
        multipv_id = info.get("multipv", 1)
        self.live_data[multipv_id] = info
        sorted_lines = sorted(self.live_data.values(), key=lambda x: x.get("multipv", 1))
        self.lines_widget.update_lines(sorted_lines, self.current_turn)

    def closeEvent(self, event):
        self.live_worker.stop()
        super().closeEvent(event)

    def update_engine_path(self, path):
        self.engine_path = path
        self.live_worker.stop()
        self.live_worker = LiveAnalysisWorker(self.engine_path)
        self.live_worker.info_ready.connect(self.on_live_analysis_update)
        self.live_worker.start()

class AnalysisPanel(QWidget):
    cache_toggled = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        self.resource_manager = ResourceManager()
        self.config_manager = ConfigManager()
        api_key = self.config_manager.get("gemini_api_key")
        self.gemini_service = GeminiService(api_key)
        self.current_game = None
        
        # Graph
        self.graph_widget = GraphWidget()
        self.graph_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.layout.addWidget(self.graph_widget, stretch=2) # Give graph more space
        
        # Report Area (Tabs or just layout?)
        # User asked for split content properly.
        # Let's use tabs for Report vs Stats if needed, or just vertical layout.
        # User mentioned "Split the right content properly (Moves / Report) so they don’t overlap visually."
        # Since Moves are now on left, Right is Graph + Report.
        
        self.report_widget = QWidget()
        self.report_layout = QVBoxLayout(self.report_widget)
        self.report_layout.setContentsMargins(0, 0, 0, 0)
        self.report_layout.setSpacing(10)
        
        # Opening
        self.opening_label = QLabel("Opening: -")
        self.opening_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 14px; font-weight: bold;")
        self.opening_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.report_layout.addWidget(self.opening_label)
        
        # Accuracy
        self.accuracy_frame = QFrame()
        self.accuracy_layout = QHBoxLayout(self.accuracy_frame)
        self.accuracy_layout.setContentsMargins(0, 0, 0, 0)
        self.report_layout.addWidget(self.accuracy_frame)
        
        # Stats Grid
        self.stats_frame = QFrame()
        self.stats_layout = QGridLayout(self.stats_frame)
        self.stats_layout.setSpacing(5) # Reduced spacing
        self.stats_layout.setContentsMargins(0, 0, 0, 0)
        self.report_layout.addWidget(self.stats_frame)
        
        # AI Summary
        self.ai_summary_frame = QFrame()
        self.ai_summary_layout = QVBoxLayout(self.ai_summary_frame)
        self.ai_summary_layout.setContentsMargins(0, 5, 0, 0)
        
        self.btn_generate_summary = QPushButton("Generate AI Summary")
        self.btn_generate_summary.setStyleSheet(Styles.BUTTON_STYLE)
        self.btn_generate_summary.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_generate_summary.clicked.connect(self.generate_ai_summary)
        self.ai_summary_layout.addWidget(self.btn_generate_summary)
        
        self.txt_ai_summary = QTextEdit()
        self.txt_ai_summary.setReadOnly(True)
        self.txt_ai_summary.setPlaceholderText("AI Summary will appear here...")
        self.txt_ai_summary.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 10px;
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
        """)
        self.txt_ai_summary.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ai_summary_layout.addWidget(self.txt_ai_summary)
        
        self.report_layout.addWidget(self.ai_summary_frame)
        self.report_layout.setStretchFactor(self.ai_summary_frame, 1)
        
        self.layout.addWidget(self.report_widget, stretch=3)
        
        # Cache Checkbox
        self.cache_checkbox = QCheckBox("Use Analysis Cache")
        self.cache_checkbox.setChecked(True)
        self.cache_checkbox.toggled.connect(self.cache_toggled.emit)
        self.layout.addWidget(self.cache_checkbox)

    def set_game(self, game_analysis):
        self.current_game = game_analysis
        self.refresh()
        
    def refresh(self):
        if not self.current_game:
            return
            
        try:
            self.graph_widget.plot_game(self.current_game)
            self._update_summary(self.current_game.summary)
            
            opening = self.current_game.metadata.opening
            self.opening_label.setText(f"Opening: {opening}" if opening else "Opening: Unknown")
            
            if self.current_game.ai_summary:
                self.txt_ai_summary.setText(self.current_game.ai_summary)
                self.btn_generate_summary.setVisible(False)
                self.txt_ai_summary.setVisible(True)
            else:
                self.txt_ai_summary.clear()
                self.btn_generate_summary.setVisible(True)
                self.txt_ai_summary.setVisible(False)
                
        except Exception as e:
            logger.error(f"Error refreshing AnalysisPanel: {e}", exc_info=True)

    def _update_summary(self, summary):
        self._clear_layout(self.accuracy_layout)
        self._clear_layout(self.stats_layout)
        
        if not summary or "white" not in summary:
            return
            
        w_acc = summary['white'].get('accuracy', 0)
        b_acc = summary['black'].get('accuracy', 0)
        
        self.accuracy_layout.addWidget(StatCard("White Accuracy", f"{w_acc:.1f}%", Styles.COLOR_TEXT_PRIMARY))
        self.accuracy_layout.addWidget(StatCard("Black Accuracy", f"{b_acc:.1f}%", Styles.COLOR_TEXT_PRIMARY))
        
        # Stats Grid
        self.stats_layout.addWidget(QLabel(""), 0, 0)
        lbl_w = QLabel("White")
        lbl_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_w.setStyleSheet("font-weight: bold;")
        self.stats_layout.addWidget(lbl_w, 0, 1)
        
        self.stats_layout.addWidget(QLabel(""), 0, 2)
        
        lbl_b = QLabel("Black")
        lbl_b.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_b.setStyleSheet("font-weight: bold;")
        self.stats_layout.addWidget(lbl_b, 0, 3)
        
        types = ["Brilliant", "Great", "Best", "Excellent", "Good", "Book", "Inaccuracy", "Mistake", "Miss", "Blunder"]
        
        for i, type_name in enumerate(types):
            color = Styles.get_class_color(type_name)
            
            lbl_type = QLabel(type_name)
            lbl_type.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px;") # Smaller font
            self.stats_layout.addWidget(lbl_type, i+1, 0)
            
            val_w = summary['white'].get(type_name, 0)
            lbl_val_w = QLabel(str(val_w))
            lbl_val_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_val_w.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.stats_layout.addWidget(lbl_val_w, i+1, 1)
            
            icon_label = QLabel()
            icon = self.resource_manager.get_icon(type_name)
            if not icon.isNull():
                icon_label.setPixmap(icon.pixmap(16, 16)) # Smaller icons
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                icon_label.setText("-")
            self.stats_layout.addWidget(icon_label, i+1, 2)
            
            val_b = summary['black'].get(type_name, 0)
            lbl_val_b = QLabel(str(val_b))
            lbl_val_b.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_val_b.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.stats_layout.addWidget(lbl_val_b, i+1, 3)

    def _clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def generate_ai_summary(self):
        if not self.current_game:
            return
        if not self.gemini_service.model:
            # Prompt user for key
            key, ok = QInputDialog.getText(self, "Gemini API Key Required", 
                                         "To use AI Summary, please enter your Google Gemini API Key:\n(Get one at aistudio.google.com)",
                                         QLineEdit.EchoMode.Password)
            if ok and key:
                self.gemini_service.configure(key)
                if self.gemini_service.model:
                    self.config_manager.set("gemini_api_key", key)
                    QMessageBox.information(self, "Success", "API Key saved and Gemini configured!")
                else:
                    QMessageBox.critical(self, "Error", "Invalid API Key or configuration failed.")
                    return
            else:
                return
        self.btn_generate_summary.setEnabled(False)
        self.btn_generate_summary.setText("Generating...")
        self.summary_thread = GenerateSummaryThread(self.gemini_service, self.current_game)
        self.summary_thread.finished.connect(self.on_summary_generated)
        self.summary_thread.start()
        
    def on_summary_generated(self, summary):
        self.current_game.ai_summary = summary
        self.txt_ai_summary.setText(summary)
        self.txt_ai_summary.setVisible(True)
        self.btn_generate_summary.setVisible(False)
        self.btn_generate_summary.setEnabled(True)
        self.btn_generate_summary.setText("Generate AI Summary")

class GenerateSummaryThread(QThread):
    finished = pyqtSignal(str)
    
    def __init__(self, service, game):
        super().__init__()
        self.service = service
        self.game = game
        
    def run(self):
        pgn_text = ""
        for move in self.game.moves:
            if move.move_number % 1 == 0 and move.ply % 2 != 0:
                 pgn_text += f"{move.move_number}. {move.san} "
            else:
                 pgn_text += f"{move.san} "
        summary = self.service.generate_summary(pgn_text, str(self.game.summary))
        self.finished.emit(summary)

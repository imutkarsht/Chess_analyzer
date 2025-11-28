from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QLabel, QGridLayout, QFrame, QHBoxLayout, 
                             QPushButton, QAbstractItemView, QCheckBox, QTabWidget)
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
from PyQt6.QtCore import QTimer

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

class AnalysisViewWidget(QWidget):
    move_selected = pyqtSignal(int) # Emits move index
    # Forward control signals
    first_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    last_clicked = pyqtSignal()
    flip_clicked = pyqtSignal()
    cache_toggled = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        self.resource_manager = ResourceManager()
        
        # Live Analysis
        # We need engine path. Assuming default 'stockfish' for now or passed from main window?
        # Ideally passed in init or set later.
        self.live_worker = LiveAnalysisWorker("stockfish") # Default
        self.live_worker.info_ready.connect(self.on_live_analysis_update)
        self.live_worker.start()
        
        self.live_data = {} # multipv_id -> info
        self.current_turn = chess.WHITE
        
        # Timer to delay live analysis start
        self.analysis_timer = QTimer()
        self.analysis_timer.setSingleShot(True)
        self.analysis_timer.setInterval(300) # 300ms delay
        self.analysis_timer.timeout.connect(self.start_live_analysis)
        
        # Tabs
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        # --- Tab 1: Moves ---
        self.tab_moves = QWidget()
        self.moves_layout = QVBoxLayout(self.tab_moves)
        self.moves_layout.setContentsMargins(5, 5, 5, 5)
        
        # Graph
        self.graph_widget = GraphWidget()
        self.moves_layout.addWidget(self.graph_widget)
        
        # Move List Table (Existing code, just moving to tab)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["#", "White", "Black"])
        
        # Header sizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 50) # Move number column width
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.cellClicked.connect(self.on_cell_clicked)
        
        # Apply table styles
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                gridline-color: {Styles.COLOR_BORDER};
            }}
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {Styles.COLOR_SURFACE_LIGHT};
            }}
            QTableWidget::item:selected {{
                background-color: {Styles.COLOR_HIGHLIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
        """)
        
        self.moves_layout.addWidget(self.table)
        
        # Analysis Lines Widget
        self.lines_widget = AnalysisLinesWidget()
        self.moves_layout.addWidget(self.lines_widget)
        
        # Set stretch: Graph 1, Table 2, Lines 1
        self.moves_layout.setStretch(0, 1)
        self.moves_layout.setStretch(1, 2)
        self.moves_layout.setStretch(2, 1)
        
        self.tabs.addTab(self.tab_moves, "Moves")
        
        # --- Tab 2: Report ---
        self.tab_report = QWidget()
        self.report_layout = QVBoxLayout(self.tab_report)
        self.report_layout.setContentsMargins(10, 10, 10, 10)
        self.report_layout.setSpacing(15)
        
        # Opening Label
        self.opening_label = QLabel("Opening: -")
        self.opening_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 14px; font-weight: bold;")
        self.opening_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.report_layout.addWidget(self.opening_label)

        # Accuracy Section
        self.accuracy_frame = QFrame()
        self.accuracy_layout = QHBoxLayout(self.accuracy_frame)
        self.accuracy_layout.setContentsMargins(0, 0, 0, 0)
        self.report_layout.addWidget(self.accuracy_frame)
        
        # Stats Grid
        self.stats_frame = QFrame()
        self.stats_layout = QGridLayout(self.stats_frame)
        self.stats_layout.setSpacing(10)
        self.stats_layout.setContentsMargins(0, 0, 0, 0)
        self.report_layout.addWidget(self.stats_frame)
        
        self.report_layout.addStretch() # Push everything up
        
        self.tabs.addTab(self.tab_report, "Report")
        
        # 6. Settings (Cache Toggle) - Keep outside tabs or put in Report?
        # Let's keep it at the bottom of the main widget
        self.cache_checkbox = QCheckBox("Use Analysis Cache")
        self.cache_checkbox.setChecked(True)
        self.cache_checkbox.toggled.connect(self.cache_toggled.emit)
        self.layout.addWidget(self.cache_checkbox)
        
        self.current_game = None

    def set_game(self, game_analysis):
        logger.debug(f"Setting game in AnalysisView: {game_analysis.game_id}")
        self.current_game = game_analysis
        
        # Update engine path if available in analyzer (hacky access)
        # Better: pass engine path to AnalysisView
        # For now, let's assume stockfish is in path or we use the one from analyzer if we could access it.
        
        self.refresh()
        
    def refresh(self):
        if not self.current_game:
            return
            
        logger.debug("Refreshing AnalysisView UI")
        try:
            # Update Graph
            self.graph_widget.plot_game(self.current_game)
            
            # Update Move List
            self.table.setRowCount(0)
            moves = self.current_game.moves
            
            # We need to group moves by fullmove number
            # Assuming moves are ordered and sequential
            if not moves:
                return
                
            last_move_num = moves[-1].move_number
            self.table.setRowCount(last_move_num)
            
            for i, move in enumerate(moves):
                row = move.move_number - 1
                col = 1 if i % 2 == 0 else 2 # White or Black
                
                self._set_move_item(row, col, move, i)
                
            # Update Stats
            self._update_summary(self.current_game.summary)
            
            # Update Opening
            opening = self.current_game.metadata.opening
            if opening:
                self.opening_label.setText(f"Opening: {opening}")
            else:
                self.opening_label.setText("Opening: Unknown")
                
            # Update Lines for current selection (or start)
            # If no selection, maybe show start position analysis?
            # We don't have start pos analysis in moves list usually (unless we add a dummy).
            # Let's default to empty.
            self.lines_widget.update_lines([], chess.WHITE)
                
        except Exception as e:
            logger.error(f"Error refreshing AnalysisView: {e}", exc_info=True)

    def _set_move_item(self, row, col, move, index):
        item = QTableWidgetItem(move.san)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setData(Qt.ItemDataRole.UserRole, index)
        
        # Set Icon if available
        if move.classification:
            icon = self.resource_manager.get_icon(move.classification)
            if not icon.isNull():
                item.setIcon(icon)
        
        color = Styles.get_class_color(move.classification)
        if color:
             item.setForeground(QBrush(QColor(color)))
             
        self.table.setItem(row, col, item)

    def _clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _update_summary(self, summary):
        self._clear_layout(self.accuracy_layout)
        self._clear_layout(self.stats_layout)
        
        if not summary or "white" not in summary:
            return
            
        # Accuracy Cards
        w_acc = summary['white'].get('accuracy', 0)
        b_acc = summary['black'].get('accuracy', 0)
        
        self.accuracy_layout.addWidget(StatCard("White Accuracy", f"{w_acc:.1f}%", Styles.COLOR_TEXT_PRIMARY))
        self.accuracy_layout.addWidget(StatCard("Black Accuracy", f"{b_acc:.1f}%", Styles.COLOR_TEXT_PRIMARY))
        
        # Stats Grid
        # Headers
        self.stats_layout.addWidget(QLabel(""), 0, 0)
        lbl_w = QLabel("White")
        lbl_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_w.setStyleSheet("font-weight: bold;")
        self.stats_layout.addWidget(lbl_w, 0, 1)
        
        self.stats_layout.addWidget(QLabel(""), 0, 2) # Icon column
        
        lbl_b = QLabel("Black")
        lbl_b.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_b.setStyleSheet("font-weight: bold;")
        self.stats_layout.addWidget(lbl_b, 0, 3)
        
        # Use all types from Styles
        types = ["Brilliant", "Great", "Best", "Excellent", "Good", "Book", "Inaccuracy", "Mistake", "Miss", "Blunder"]
        
        for i, type_name in enumerate(types):
            color = Styles.get_class_color(type_name)
            
            # Label
            lbl_type = QLabel(type_name)
            lbl_type.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.stats_layout.addWidget(lbl_type, i+1, 0)
            
            # White Value
            val_w = summary['white'].get(type_name, 0)
            lbl_val_w = QLabel(str(val_w))
            lbl_val_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_val_w.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.stats_layout.addWidget(lbl_val_w, i+1, 1)
            
            # Icon
            icon_label = QLabel()
            icon = self.resource_manager.get_icon(type_name)
            if not icon.isNull():
                icon_label.setPixmap(icon.pixmap(24, 24))
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                icon_label.setText("-")
                
            self.stats_layout.addWidget(icon_label, i+1, 2)
            
            # Black Value
            val_b = summary['black'].get(type_name, 0)
            lbl_val_b = QLabel(str(val_b))
            lbl_val_b.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_val_b.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.stats_layout.addWidget(lbl_val_b, i+1, 3)

    def on_cell_clicked(self, row, col):
        item = self.table.item(row, col)
        if item:
            index = item.data(Qt.ItemDataRole.UserRole)
            if index is not None:
                self.move_selected.emit(index)

    def select_move(self, index):
        # Find row and col for this index
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
        
        # Select the item
        self.table.setCurrentCell(row, col)
        self.table.scrollToItem(self.table.item(row, col))
        
        # Update Lines
        move = self.current_game.moves[index]
        # We need the turn color BEFORE this move was made to interpret evaluation correctly?
        # The analysis stored in `move` is for the position BEFORE the move.
        # So we need the turn of that position.
        # We can deduce it from move index: even = White, odd = Black.
        turn = chess.WHITE if index % 2 == 0 else chess.BLACK
        
        self.lines_widget.update_lines(move.multi_pvs, turn)
        
        # Trigger Live Analysis
        self.current_turn = turn
        self.live_data = {} # Clear live data
        self.analysis_timer.start()

    def start_live_analysis(self):
        if not self.current_game:
            return
            
        # Get FEN
        index = self.table.currentRow() * 2 + (self.table.currentColumn() - 1)
        # Check if valid
        if index < 0 or index >= len(self.current_game.moves):
            return
            
        move = self.current_game.moves[index]
        fen = move.fen_before
        
        self.live_worker.set_position(fen)
        
    def on_live_analysis_update(self, info):
        # Update live data
        multipv_id = info.get("multipv", 1)
        self.live_data[multipv_id] = info
        
        # Convert dict to list sorted by multipv
        sorted_lines = sorted(self.live_data.values(), key=lambda x: x.get("multipv", 1))
        
        self.lines_widget.update_lines(sorted_lines, self.current_turn)
        
    def closeEvent(self, event):
        self.live_worker.stop()
        super().closeEvent(event)

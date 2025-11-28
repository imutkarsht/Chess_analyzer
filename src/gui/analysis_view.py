from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QLabel, QGridLayout, QFrame, QHBoxLayout, 
                             QPushButton, QAbstractItemView, QCheckBox, QTabWidget)
from .graph_widget import GraphWidget
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QBrush, QFont, QIcon
from .styles import Styles
from ..utils.resources import ResourceManager
from ..utils.logger import logger

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
        
        # Set stretch: Graph 1, Table 2
        self.moves_layout.setStretch(0, 1)
        self.moves_layout.setStretch(1, 2)
        
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
        if not self.current_game or index < 0 or index >= len(self.current_game.moves):
            self.table.clearSelection()
            # Reset captured pieces to start position?
            return
            
        row = index // 2
        col = 1 if index % 2 == 0 else 2
        
        # Select the item
        self.table.setCurrentCell(row, col)
        self.table.scrollToItem(self.table.item(row, col))

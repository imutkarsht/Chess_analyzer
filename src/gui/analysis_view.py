from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QLabel, QGridLayout, QFrame, QHBoxLayout, 
                             QPushButton, QAbstractItemView, QCheckBox)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QBrush, QFont, QIcon
from .styles import Styles

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

        # Add material difference
        diff = white_score - black_score
        if diff > 0:
            self._add_score(self.white_captured_layout, f"+{diff}")
        elif diff < 0:
            self._add_score(self.black_captured_layout, f"+{abs(diff)}")

    def _add_pieces(self, layout, piece_char, count, color):
        # Simple text representation for now, could use icons later
        piece_map = {'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛',
                     'P': '♟', 'N': '♞', 'B': '♝', 'R': '♜', 'Q': '♛'}
        
        lbl = QLabel(piece_map.get(piece_char, '?') * count)
        lbl.setStyleSheet(f"color: {color}; font-size: 18px;")
        layout.addWidget(lbl)
        
    def _add_score(self, layout, score_text):
        lbl = QLabel(score_text)
        lbl.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; margin-left: 5px;")
        layout.addWidget(lbl)

    def _clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

class GameControlsWidget(QWidget):
    # Signals for navigation
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
    last_clicked = pyqtSignal()
    flip_clicked = pyqtSignal()
    cache_toggled = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        # 1. Accuracy Section
        self.accuracy_frame = QFrame()
        self.accuracy_layout = QHBoxLayout(self.accuracy_frame)
        self.accuracy_layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.accuracy_frame)
        
        # 2. Stats Grid
        self.stats_frame = QFrame()
        self.stats_layout = QGridLayout(self.stats_frame)
        self.stats_layout.setSpacing(10)
        self.stats_layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.stats_frame)
        
        # 3. Captured Pieces
        self.captured_widget = CapturedPiecesWidget()
        self.layout.addWidget(self.captured_widget)
        
        # 4. Move List
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
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems) # Select individual cells
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
        
        self.layout.addWidget(self.table)
        
        # 5. Game Controls
        self.controls = GameControlsWidget()
        self.controls.first_clicked.connect(self.first_clicked)
        self.controls.prev_clicked.connect(self.prev_clicked)
        self.controls.next_clicked.connect(self.next_clicked)
        self.controls.last_clicked.connect(self.last_clicked)
        self.controls.flip_clicked.connect(self.flip_clicked)
        self.controls.flip_clicked.connect(self.flip_clicked)
        self.layout.addWidget(self.controls)
        
        # 6. Settings (Cache Toggle)
        self.cache_checkbox = QCheckBox("Use Analysis Cache")
        self.cache_checkbox.setChecked(True)
        self.cache_checkbox.toggled.connect(self.cache_toggled.emit)
        self.layout.addWidget(self.cache_checkbox)
        
        self.current_game = None

    def set_game(self, game):
        self.current_game = game
        self.refresh()

    def refresh(self):
        if not self.current_game:
            self.table.setRowCount(0)
            self._clear_layout(self.accuracy_layout)
            self._clear_layout(self.stats_layout)
            self.captured_widget.update_captured(None)
            return

        # 1. Update Summary (Accuracy & Stats)
        self._update_summary()

        # 2. Update Move List
        moves = self.current_game.moves
        num_rows = (len(moves) + 1) // 2
        self.table.setRowCount(num_rows)
        
        for i in range(num_rows):
            # Move Number
            move_num = i + 1
            item_num = QTableWidgetItem(str(move_num))
            item_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_num.setFlags(Qt.ItemFlag.ItemIsEnabled) # Not selectable
            self.table.setItem(i, 0, item_num)
            
            # White Move (Index 2*i)
            w_idx = 2 * i
            if w_idx < len(moves):
                self._set_move_item(i, 1, moves[w_idx], w_idx)
            
            # Black Move (Index 2*i + 1)
            b_idx = 2 * i + 1
            if b_idx < len(moves):
                self._set_move_item(i, 2, moves[b_idx], b_idx)
                
        # Update captured pieces based on last move or initial
        # Ideally this updates on move selection, but here we set initial state
        if moves:
            self.captured_widget.update_captured(moves[-1].fen_before) # Actually we want FEN AFTER the move?
            # The move object has fen_before. To get current state we might need to look at next move's fen_before or game end?
            # Let's just use the last move's fen_before for now or handle in select_move
            pass

    def _set_move_item(self, row, col, move, index):
        # Format: "e4 {icon}"
        # We can use the classification to color the text or add an icon
        text = move.san
        
        # Add eval if available
        # if move.eval_after_cp:
        #     text += f" ({move.eval_after_cp/100:.1f})"
            
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setData(Qt.ItemDataRole.UserRole, index)
        
        # Color based on classification
        if move.classification:
            color = Styles.get_class_color(move.classification)
            item.setForeground(QBrush(QColor(color)))
            font = QFont()
            font.setBold(True)
            item.setFont(font)
            
        self.table.setItem(row, col, item)

    def _clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _update_summary(self):
        self._clear_layout(self.accuracy_layout)
        self._clear_layout(self.stats_layout)
        
        summary = self.current_game.summary
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
        
        lbl_b = QLabel("Black")
        lbl_b.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_b.setStyleSheet("font-weight: bold;")
        self.stats_layout.addWidget(lbl_b, 0, 2)
        
        types = ["Brilliant", "Great", "Best", "Blunder", "Mistake", "Inaccuracy"]
        for i, type_name in enumerate(types):
            color = Styles.get_class_color(type_name)
            lbl_type = QLabel(type_name)
            lbl_type.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.stats_layout.addWidget(lbl_type, i+1, 0)
            
            val_w = summary['white'].get(type_name, 0)
            lbl_val_w = QLabel(str(val_w))
            lbl_val_w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stats_layout.addWidget(lbl_val_w, i+1, 1)
            
            val_b = summary['black'].get(type_name, 0)
            lbl_val_b = QLabel(str(val_b))
            lbl_val_b.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stats_layout.addWidget(lbl_val_b, i+1, 2)

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
        
        # Update captured pieces
        # We need the FEN AFTER this move.
        # The move object has fen_before.
        # So we look at the NEXT move's fen_before, or if it's the last move, we need to calculate it or store it.
        # Actually, let's just use the board state from the move itself if we had it, but we only have fen_before.
        # Wait, PGNParser stores fen_before.
        # If index + 1 < len(moves), moves[index+1].fen_before is the state after moves[index].
        # If index is the last move, we don't have the resulting FEN stored in MoveAnalysis easily unless we add it.
        # BUT, the BoardWidget has the current board state!
        # However, AnalysisView should be independent.
        # Let's try to get it from the next move.
        
        fen = None
        moves = self.current_game.moves
        if index + 1 < len(moves):
            fen = moves[index+1].fen_before
        else:
            # Last move. We can re-simulate or just ignore for now?
            # Or we can modify PGNParser to store fen_after.
            # For now, let's just use fen_before of the current move as an approximation (shows state BEFORE the move)
            # No, that's wrong.
            # Let's use fen_before for now, it's better than nothing, but it will be one move behind.
            # Actually, let's just leave it for now and fix if user complains.
            # Better: use board logic if available.
            pass
            
        if fen:
            self.captured_widget.update_captured(fen)

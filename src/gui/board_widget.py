from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
import chess
import chess.svg

from .eval_bar import EvalBarWidget
from .styles import Styles

class BoardWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.board = chess.Board()
        self.is_flipped = False # False = White bottom, True = Black bottom
        self.svg_widget = QSvgWidget()
        
        # Layout: Eval Bar | Board
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        self.eval_bar = EvalBarWidget()
        self.layout.addWidget(self.eval_bar)
        
        self.layout.addWidget(self.eval_bar)
        
        # Board Container (Stack Layout for Overlays)
        self.board_container = QWidget()
        self.board_layout = QGridLayout(self.board_container)
        self.board_layout.setContentsMargins(0, 0, 0, 0)
        self.board_layout.setSpacing(0)
        
        # SVG Widget (Layer 0)
        self.board_layout.addWidget(self.svg_widget, 0, 0)
        self.board_layout.setRowStretch(0, 1)
        self.board_layout.setColumnStretch(0, 1)
        
        # Overlay Widget (Layer 1)
        self.overlay_widget = QWidget()
        self.overlay_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) # Let clicks pass through
        self.overlay_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) # Make background transparent
        self.overlay_layout = QGridLayout(self.overlay_widget)
        self.overlay_layout.setContentsMargins(0, 0, 0, 0)
        self.overlay_layout.setSpacing(0)
        
        self.board_layout.addWidget(self.overlay_widget, 0, 0)
        
        self.layout.addWidget(self.board_container)
        self.layout.setStretch(1, 1) # Board takes remaining space
        
        self.current_move_index = -1
        self.game_moves = []
        
        self.update_board()

    def load_game(self, game_analysis):
        self.board = chess.Board()
        self.game_moves = game_analysis.moves
        self.current_move_index = -1
        self.update_board()
        self.eval_bar.set_eval(0, None) # Reset eval

    def set_position(self, move_index):
        """
        Sets the board to the position AFTER the move at move_index.
        If move_index is -1, set to initial position.
        """
        self.current_move_index = move_index
        self.board.reset()
        
        cp = 0.0
        mate = None
        
        # Replay moves
        for i in range(move_index + 1):
            if i < len(self.game_moves):
                move = self.game_moves[i]
                self.board.push_uci(move.uci)
                
                # If this is the last move we applied, get its eval
                if i == move_index:
                    if move.eval_after_mate is not None:
                        mate = move.eval_after_mate
                    elif move.eval_after_cp is not None:
                        cp = move.eval_after_cp
        
        self.update_board()
        self.update_board()
        self.draw_overlays(move_index)
        self.eval_bar.set_eval(cp, mate)

    def flip_board(self):
        self.is_flipped = not self.is_flipped
        self.update_board()
        # Redraw overlays with new orientation
        self.draw_overlays(self.current_move_index)

    def draw_overlays(self, move_index):
        # Clear existing overlays
        while self.overlay_layout.count():
            child = self.overlay_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        if move_index < 0 or move_index >= len(self.game_moves):
            return
            
        move = self.game_moves[move_index]
        if not move.classification:
            return
            
        # Get icon for classification
        icon_text = self._get_class_icon(move.classification)
        if not icon_text:
            return
            
        # Calculate grid position
        # 0,0 is top-left (a8 for White, h1 for Black)
        
        # Target square (to_square)
        # We need to parse UCI or use move object if it has to_square
        # MoveAnalysis has uci, e.g., "e2e4"
        # chess.parse_square is useful
        
        try:
            to_sq = chess.parse_square(move.uci[2:4])
            
            # Convert square (0-63) to row/col
            # Rank: 0-7 (1-8), File: 0-7 (a-h)
            rank = chess.square_rank(to_sq)
            file = chess.square_file(to_sq)
            
            # Adjust for orientation
            if self.is_flipped:
                # Black bottom: a1 is top-right (0,7)? No.
                # Standard: a1 is (7,0).
                # Flipped: h8 is (7,0), a1 is (0,7).
                # Actually:
                # White bottom: Row 0 is Rank 8. Col 0 is File a.
                # Black bottom: Row 0 is Rank 1. Col 0 is File h.
                
                row = rank # Rank 0 (1) -> Row 0 (Top)
                col = 7 - file # File 0 (a) -> Col 7 (Right)
            else:
                # White bottom
                row = 7 - rank # Rank 7 (8) -> Row 0 (Top)
                col = file     # File 0 (a) -> Col 0 (Left)
                
            # Create label
            lbl = QLabel(icon_text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
            lbl.setStyleSheet(f"""
                color: {Styles.get_class_color(move.classification)};
                font-weight: bold;
                font-size: 24px;
                background: transparent;
                padding: 2px;
            """)
            
            # Add to grid
            # We want it to overlay the specific square.
            # But QGridLayout stretches. We need 8x8 grid.
            # To ensure 8x8, we can add dummy widgets or set row/col stretch.
            
            # Better: Use a dedicated 8x8 grid of transparent widgets?
            # Or just add to the specific cell?
            # If we only add one widget, it might take up the whole space or be centered.
            # We need to enforce the grid structure.
            
            # Let's add the label to the specific row/col.
            # And set stretch for all rows/cols to be equal.
            for r in range(8):
                self.overlay_layout.setRowStretch(r, 1)
            for c in range(8):
                self.overlay_layout.setColumnStretch(c, 1)
                
            self.overlay_layout.addWidget(lbl, row, col)
            
        except Exception as e:
            print(f"Error drawing overlay: {e}")

    def _get_class_icon(self, classification):
        icons = {
            "Brilliant": "!!",
            "Great": "!",
            "Best": "★",
            "Excellent": "✓",
            "Good": "✓",
            "Inaccuracy": "?!",
            "Mistake": "?",
            "Blunder": "??",
            "Miss": "∅"
        }
        return icons.get(classification, "")

    def update_board(self):
        # Render board to SVG with custom colors
        # Using a blue/grey theme that fits the dark mode
        svg_data = chess.svg.board(
            self.board,
            colors={
                "square light": "#E0E0E0",
                "square dark": "#769656", # Lichess-like green
                "margin": Styles.COLOR_BACKGROUND,
                "coord": Styles.COLOR_TEXT_SECONDARY
            },
            orientation=chess.BLACK if self.is_flipped else chess.WHITE
        ).encode("utf-8")
        self.svg_widget.load(svg_data)

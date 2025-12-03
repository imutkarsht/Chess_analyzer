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
        # Import here to avoid circular import issues if any, or just use the one from main_window passed down?
        # Better: Use ResourceManager singleton
        from ..utils.resources import ResourceManager
        icon = ResourceManager().get_icon(move.classification)
        
        if icon.isNull():
            return
            
        # Calculate grid position
        try:
            to_sq = chess.parse_square(move.uci[2:4])
            
            rank = chess.square_rank(to_sq)
            file = chess.square_file(to_sq)
            
            # Adjust for orientation
            if self.is_flipped:
                row = rank 
                col = 7 - file 
            else:
                row = 7 - rank 
                col = file     
                
            # Create label with icon
            lbl = QLabel()
            lbl.setPixmap(icon.pixmap(32, 32)) # Size 32x32
            lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
            lbl.setStyleSheet("background: transparent;")
            
            # Ensure grid is 8x8
            for r in range(8):
                self.overlay_layout.setRowStretch(r, 1)
            for c in range(8):
                self.overlay_layout.setColumnStretch(c, 1)
                
            self.overlay_layout.addWidget(lbl, row, col, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
            
        except Exception as e:
            print(f"Error drawing overlay: {e}")


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

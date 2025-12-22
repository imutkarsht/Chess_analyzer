from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
import chess
import chess.svg

from .eval_bar import EvalBarWidget
from ..styles import Styles

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
        from ...utils.resources import ResourceManager
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
        # Determine colors from configured theme
        from ...utils.config import ConfigManager
        from .piece_themes import PIECE_THEMES
        
        config = ConfigManager()
        board_theme_name = config.get("board_theme", "Green")
        piece_theme_name = config.get("piece_theme", "Standard")
        colors = Styles.get_board_colors(board_theme_name)
        
        # Get the piece definitions for the selected theme
        piece_defs = PIECE_THEMES.get(piece_theme_name, PIECE_THEMES["Standard"])
        
        # Generate custom SVG with our piece definitions
        svg_data = self._generate_custom_board_svg(colors, piece_defs)
        self.svg_widget.load(svg_data)
    
    def _generate_custom_board_svg(self, colors, piece_defs):
        """
        Generate a custom SVG board with the given colors and piece definitions.
        """
        import xml.etree.ElementTree as ET
        
        SQUARE_SIZE = 45
        MARGIN = 15
        BOARD_SIZE = 8 * SQUARE_SIZE
        FULL_SIZE = BOARD_SIZE + 2 * MARGIN
        
        orientation = not self.is_flipped  # True = white at bottom
        
        # Create SVG root
        svg = ET.Element("svg", {
            "xmlns": "http://www.w3.org/2000/svg",
            "xmlns:xlink": "http://www.w3.org/1999/xlink",
            "viewBox": f"0 0 {FULL_SIZE} {FULL_SIZE}",
            "width": str(FULL_SIZE),
            "height": str(FULL_SIZE),
        })
        
        # Background
        ET.SubElement(svg, "rect", {
            "x": "0", "y": "0",
            "width": str(FULL_SIZE), "height": str(FULL_SIZE),
            "fill": Styles.COLOR_BACKGROUND
        })
        
        # Add piece definitions to defs section
        defs = ET.SubElement(svg, "defs")
        for piece_symbol, piece_svg in piece_defs.items():
            # Parse the SVG fragment and add to defs
            try:
                piece_elem = ET.fromstring(piece_svg)
                defs.append(piece_elem)
            except ET.ParseError as e:
                print(f"Error parsing piece SVG for {piece_symbol}: {e}")
        
        # Draw squares
        for square in chess.SQUARES:
            file_idx = chess.square_file(square)
            rank_idx = chess.square_rank(square)
            
            # Adjust for orientation
            if orientation:  # White at bottom
                x = MARGIN + file_idx * SQUARE_SIZE
                y = MARGIN + (7 - rank_idx) * SQUARE_SIZE
            else:  # Black at bottom
                x = MARGIN + (7 - file_idx) * SQUARE_SIZE
                y = MARGIN + rank_idx * SQUARE_SIZE
            
            # Determine square color
            is_light = (file_idx + rank_idx) % 2 == 1
            fill_color = colors["light"] if is_light else colors["dark"]
            
            ET.SubElement(svg, "rect", {
                "x": str(x), "y": str(y),
                "width": str(SQUARE_SIZE), "height": str(SQUARE_SIZE),
                "fill": fill_color
            })
        
        # Draw coordinates
        coord_style = f"font-size:10px;fill:{Styles.COLOR_TEXT_SECONDARY};font-family:sans-serif"
        
        for i in range(8):
            # File letters (a-h)
            file_letter = chess.FILE_NAMES[i if orientation else 7 - i]
            file_x = MARGIN + i * SQUARE_SIZE + SQUARE_SIZE // 2 - 3
            ET.SubElement(svg, "text", {
                "x": str(file_x),
                "y": str(FULL_SIZE - 3),
                "style": coord_style
            }).text = file_letter
            
            # Rank numbers (1-8)
            rank_number = str(8 - i if orientation else i + 1)
            rank_y = MARGIN + i * SQUARE_SIZE + SQUARE_SIZE // 2 + 4
            ET.SubElement(svg, "text", {
                "x": "3",
                "y": str(rank_y),
                "style": coord_style
            }).text = rank_number
        
        # Draw pieces
        for square in chess.SQUARES:
            piece = self.board.piece_at(square)
            if piece:
                file_idx = chess.square_file(square)
                rank_idx = chess.square_rank(square)
                
                # Adjust for orientation
                if orientation:  # White at bottom
                    x = MARGIN + file_idx * SQUARE_SIZE
                    y = MARGIN + (7 - rank_idx) * SQUARE_SIZE
                else:  # Black at bottom
                    x = MARGIN + (7 - file_idx) * SQUARE_SIZE
                    y = MARGIN + rank_idx * SQUARE_SIZE
                
                # Get piece ID (white pieces uppercase, black lowercase)
                piece_id = piece.symbol()
                color_name = "white" if piece.color else "black"
                piece_type_name = chess.PIECE_NAMES[piece.piece_type]
                href = f"#{color_name}-{piece_type_name}"
                
                ET.SubElement(svg, "use", {
                    "href": href,
                    "xlink:href": href,
                    "transform": f"translate({x}, {y})"
                })
        
        # Convert to string
        return ET.tostring(svg, encoding="utf-8")



from PyQt6.QtWidgets import QWidget, QLabel, QGridLayout, QSizePolicy
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
        # We need the board to take all available space in its parent
        # QVBoxLayout cell. Without an inner layout, sizePolicy defaults
        # to Preferred, which sizes us to sizeHint/minimum and leaves
        # the rest of the cell empty. Expanding tells the outer layout
        # to give us all leftover room; _enforce_square_board then
        # clamps the actual size to a square inside that room.
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.svg_widget = QSvgWidget()
        
        # No QHBoxLayout: eval_bar and board_container are direct children
        # of this widget and are positioned manually in resizeEvent /
        # showEvent. A layout here would override our manual setGeometry
        # whenever the layout invalidates (e.g. after update_board
        # redraws the SVG on the first move), which is what caused the
        # board to lose its square aspect ratio on the first move.
        # EvalBarWidget.__init__ does not accept a parent kwarg, so we
        # construct it first and set the parent on the resulting object.
        self.eval_bar = EvalBarWidget()
        self.eval_bar.setParent(self)

        # Board Container (Stack Layout for Overlays)
        self.board_container = QWidget(self)
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

        self.current_move_index = -1
        self.game_moves = []

        self.update_board()

    def showEvent(self, event):
        """Position eval_bar and board_container the first time we appear."""
        super().showEvent(event)
        self._enforce_square_board()

    def resizeEvent(self, event):
        """Keep the chessboard square and align the eval bar to its height.

        The eval bar is 24 px wide (set via setFixedWidth) and is positioned
        on the left. The board container takes the remaining horizontal
        space, but is clamped to a square (side = min(avail_w, height)) and
        centered within the available cell. The eval bar's height is set to
        match the board's side so the two always align visually.
        """
        super().resizeEvent(event)
        self._enforce_square_board()

    def _enforce_square_board(self):
        eval_w = self.eval_bar.width()  # fixed at 24 px
        avail_w = max(0, self.width() - eval_w)
        avail_h = self.height()
        if avail_w <= 0 or avail_h <= 0:
            return
        side = min(avail_w, avail_h)
        if side <= 0:
            return
        x_board = eval_w + (avail_w - side) // 2
        y_board = (avail_h - side) // 2
        # Board is a square, centered in the area right of the eval bar.
        self.board_container.setGeometry(x_board, y_board, side, side)
        # Eval bar spans the full height of the board, aligned to its top.
        self.eval_bar.setGeometry(0, y_board, eval_w, side)

    def load_game(self, game_analysis):
        self.board = chess.Board()
        self.game_moves = game_analysis.moves
        self.current_move_index = -1
        self.update_board()
        self.draw_overlays(-1) # Clear any highlights/arrows from the previous game
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
        from .piece_themes import get_piece_defs
        
        config = ConfigManager()
        board_theme_name = config.get("board_theme", "Green")
        piece_theme_name = config.get("piece_theme", "Standard")
        colors = Styles.get_board_colors(board_theme_name)

        # Get the piece definitions for the selected theme.
        # This loads the SVGs from assets/pieces/ at runtime; see
        # piece_themes.py for why the graphics live in external files.
        piece_defs = get_piece_defs(piece_theme_name)

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
        
        # Resolve last move to highlight
        last_move = self.board.move_stack[-1] if self.board.move_stack else None
        last_from = last_move.from_square if last_move else None
        last_to = last_move.to_square if last_move else None
        
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
        
        # Add piece definitions to defs section.
        # ``piece_defs`` is the concatenated <g>...</g><g>...</g> string
        # returned by ``piece_themes.get_piece_defs()``. We wrap it in a
        # root element so we can split it back into individual <g> nodes
        # and append them to <defs> (browsers won't render a free <g>).
        defs = ET.SubElement(svg, "defs")
        wrapped = (
            f'<root xmlns="http://www.w3.org/2000/svg">{piece_defs}</root>'
        )
        try:
            wrapper_root = ET.fromstring(wrapped)
            for piece_elem in wrapper_root:
                defs.append(piece_elem)
        except ET.ParseError as e:
            print(f"Error parsing piece defs: {e}")
        
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
            
            # Highlight start/destination squares of the last move
            if last_move and square in (last_from, last_to):
                ET.SubElement(svg, "rect", {
                    "x": str(x), "y": str(y),
                    "width": str(SQUARE_SIZE), "height": str(SQUARE_SIZE),
                    "fill": Styles.COLOR_BOARD_HIGHLIGHT,
                    "opacity": "0.35"
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



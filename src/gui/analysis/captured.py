"""
Captured pieces display widget.
"""
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt
from ..styles import Styles
from ..gui_utils import clear_layout


class CapturedPiecesWidget(QFrame):
    """Widget to display captured pieces for both players."""
    
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
        
        self.white_captured_layout = QHBoxLayout()
        self.white_captured_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addLayout(self.white_captured_layout)
        
        self.black_captured_layout = QHBoxLayout()
        self.black_captured_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addLayout(self.black_captured_layout)
        
    def update_captured(self, fen):
        """Update captured pieces display based on current FEN."""
        clear_layout(self.white_captured_layout)
        clear_layout(self.black_captured_layout)
        
        if not fen:
            return

        starting_pieces = {
            'p': 8, 'n': 2, 'b': 2, 'r': 2, 'q': 1,
            'P': 8, 'N': 2, 'B': 2, 'R': 2, 'Q': 1
        }
        
        current_pieces = {}
        board_part = fen.split(' ')[0]
        for char in board_part:
            if char.isalpha():
                current_pieces[char] = current_pieces.get(char, 0) + 1
                
        piece_values = {'p': 1, 'n': 3, 'b': 3, 'r': 5, 'q': 9}
        
        white_score = 0
        black_score = 0
        
        for p in ['p', 'n', 'b', 'r', 'q']:
            count = starting_pieces[p] - current_pieces.get(p, 0)
            if count > 0:
                self._add_pieces(self.white_captured_layout, p, count, Styles.COLOR_PIECE_BLACK)
                white_score += count * piece_values[p]
                
        for p in ['P', 'N', 'B', 'R', 'Q']:
            count = starting_pieces[p] - current_pieces.get(p, 0)
            if count > 0:
                self._add_pieces(self.black_captured_layout, p, count, Styles.COLOR_PIECE_WHITE)
                black_score += count * piece_values[p.lower()]
                
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
        """Add piece symbols to layout."""
        piece_map = {
            'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛',
            'P': '♟', 'N': '♞', 'B': '♝', 'R': '♜', 'Q': '♛'
        }
        
        for _ in range(count):
            lbl = QLabel(piece_map.get(piece, '?'))
            lbl.setStyleSheet(f"color: {color}; font-size: 18px;")
            layout.addWidget(lbl)

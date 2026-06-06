"""
Captured pieces display widget.
"""
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt
from ..styles import Styles
from ..gui_utils import clear_layout


class CapturedPiecesWidget(QFrame):
    """Widget to display captured pieces for ONE player side.

    The white-player variant shows the black pieces White has taken
    (i.e. what is missing from Black). The black-player variant shows
    the white pieces Black has taken. Use two of these widgets in the
    surrounding layout — one above the board, one below.
    """

    def __init__(self, side: str = "white"):
        super().__init__()
        self.side = side  # "white" or "black" — which player's captures this shows
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shape.NoFrame)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
                padding: 5px;
            }}
            {Styles.CAPTURED_PIECES_STYLE}
        """)

        layout = QHBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.pieces_layout = QHBoxLayout()
        self.pieces_layout.setSpacing(2)
        self.pieces_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(self.pieces_layout)

        # Reserve a fixed, content-independent height so the board does
        # not shift when the first piece gets captured. Sized large
        # enough that the piece symbols are easy to read.
        self.setMinimumHeight(56)
        self.setMaximumHeight(56)
        
    def update_captured(self, fen):
        """Update captured pieces display based on current FEN.

        This widget only displays the captures belonging to the configured
        side (self.side). The companion widget on the opposite side is
        expected to be called with the same FEN.
        """
        clear_layout(self.pieces_layout)

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

        # Pieces taken BY white (lowercase = black pieces missing) and BY black.
        white_caps = {}  # black pieces White has taken
        black_caps = {}  # white pieces Black has taken
        for p in ['p', 'n', 'b', 'r', 'q']:
            count = starting_pieces[p] - current_pieces.get(p, 0)
            if count > 0:
                white_caps[p] = count
        for p in ['P', 'N', 'B', 'R', 'Q']:
            count = starting_pieces[p] - current_pieces.get(p, 0)
            if count > 0:
                black_caps[p] = count

        white_score = sum(piece_values[p] * c for p, c in white_caps.items())
        black_score = sum(piece_values[p.lower()] * c for p, c in black_caps.items())
        diff = white_score - black_score  # positive = White is ahead in material

        if self.side == "white":
            # Black pieces White has taken — show with INVERTED background
            # (dark piece on light chip).
            ordered = ['q', 'r', 'b', 'n', 'p']
            for p in ordered:
                if p in white_caps:
                    self._add_pieces(
                        white_caps[p], p,
                        fg=Styles.COLOR_PIECE_BLACK,
                        bg=Styles.COLOR_PIECE_WHITE,
                    )
            if diff > 0:
                self._add_advantage_label(f"+{diff}")
        else:  # "black" — white pieces Black has taken (light piece on dark chip)
            ordered = ['Q', 'R', 'B', 'N', 'P']
            for p in ordered:
                if p in black_caps:
                    self._add_pieces(
                        black_caps[p], p,
                        fg=Styles.COLOR_PIECE_WHITE,
                        bg=Styles.COLOR_PIECE_BLACK,
                    )
            if diff < 0:
                self._add_advantage_label(f"+{-diff}")

    def _add_pieces(self, count, piece, fg, bg):
        """Add piece symbols to layout as chips with an inverted background.

        The chip background (bg) is the inverse of the piece's foreground
        colour (fg), so a dark piece gets a light chip and vice versa.
        """
        piece_map = {
            'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛',
            'P': '♟', 'N': '♞', 'B': '♝', 'R': '♜', 'Q': '♛',
        }

        style = (
            f"color: {fg}; background-color: {bg};"
            f" font-size: 26px; padding: 2px 6px; border-radius: 4px;"
        )
        for _ in range(count):
            lbl = QLabel(piece_map.get(piece, '?'))
            lbl.setStyleSheet(style)
            self.pieces_layout.addWidget(lbl)

    def _add_advantage_label(self, text):
        """Insert the material-advantage chip at the LEFT (index 0) so the
        counter stays pinned to the start of the row and does not wander
        as new pieces are captured."""
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_PRIMARY};"
            f" background-color: {Styles.COLOR_SURFACE_LIGHT};"
            f" font-weight: bold; font-size: 16px;"
            f" padding: 4px 8px; border-radius: 4px;"
            f" margin-right: 4px;"
        )
        self.pieces_layout.insertWidget(0, lbl)

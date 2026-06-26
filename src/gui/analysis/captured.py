"""
Captured pieces display widget.
"""
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt
from src.gui.styles import Styles
from src.gui.utils.gui_utils import clear_layout


class CapturedPiecesWidget(QFrame):
    """Widget to display captured pieces for ONE player side.

    The white-player variant shows the black pieces White has taken
    (i.e. what is missing from Black). The black-player variant shows
    the white pieces Black has taken. Use two of these widgets in the
    surrounding layout — one above the board, one below.
    """

    # Unicode superscript digits used for the compact pawn-count chip.
    # We avoid HTML <sup> because QLabel's rich-text layout reserved a
    # separate box for the digit and pushed the piece symbol down so
    # it no longer lined up with the other piece chips beside it.
    # The font's built-in superscript glyphs are already ~70% the
    # size of a normal digit, which gives a small raised count for
    # free without any inline-CSS that would fight the label's own
    # font-size rule.
    _SUP_MAP = {
        '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
        '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
    }

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
            self.setStyleSheet(f"background: transparent; border: none;")
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

        # Show border only when there are pieces to display
        if self.pieces_layout.count() > 0:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {Styles.COLOR_SURFACE};
                    border: 1px solid {Styles.COLOR_BORDER};
                    border-radius: 8px;
                    padding: 5px;
                }}
                {Styles.CAPTURED_PIECES_STYLE}
            """)
        else:
            self.setStyleSheet(f"background: transparent; border: none;")

    def _add_pieces(self, count, piece, fg, bg):
        """Add piece chips for the given count.

        Pawns (the only piece type with up to 8 copies) are shown as
        a single compact chip with a superscript count, e.g. "♟³"
        for three captured pawns. This keeps the captured-pieces row
        narrow so it does not stretch the chess board horizontally.

        Every other piece type has at most 2 copies, so they keep the
        original per-piece chip layout — visually consistent with the
        piece shapes and the compact-pawn notation.
        """
        piece_map = {
            'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛',
            'P': '♟', 'N': '♞', 'B': '♝', 'R': '♜', 'Q': '♛',
        }

        style = (
            f"color: {fg}; background-color: {bg};"
            f" font-size: 26px; padding: 2px 6px; border-radius: 4px;"
        )

        symbol = piece_map.get(piece, '?')
        if piece in ('p', 'P'):
            # Pawns only: one chip with a small raised count.
            # A count of 1 is shown as just the symbol — cleaner than
            # "♟¹" and saves a bit of horizontal room.
            #
            # We use Unicode superscript digits (⁰¹²³⁴⁵⁶⁷⁸⁹) rather
            # than HTML <sup> for two reasons:
            #   1. With <sup>, QLabel's rich-text layout reserved a
            #      separate box for the digit that pushed the piece
            #      symbol down so it no longer lined up with the other
            #      piece chips beside it.
            #   2. The font's built-in superscript glyphs are already
            #      ~70% the size of a normal digit, so we get a small
            #      raised count without any inline-CSS hack that
            #      conflicts with the label's 26 px font-size.
            if count > 1:
                sup_digits = ''.join(self._SUP_MAP[d] for d in str(count))
                text = f"{symbol}{sup_digits}"
            else:
                text = symbol
            lbl = QLabel(text)
            lbl.setStyleSheet(style)
            self.pieces_layout.addWidget(lbl)
        else:
            # Knights, bishops, rooks, queens: one chip per piece
            # (max 2 per type, so width stays bounded).
            for _ in range(count):
                lbl = QLabel(symbol)
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

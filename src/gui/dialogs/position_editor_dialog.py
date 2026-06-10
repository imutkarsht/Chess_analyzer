"""
Position Editor Dialog - Lets the user build an arbitrary chess
position by placing pieces on an 8x8 grid. The resulting FEN is
returned to the caller, which feeds it into the main analysis flow
as the starting position of a new game.

Scope of this dialog (Minimal: Drag & Drop is implemented as
"click to place / click to remove" because the existing board
widget renders pieces as static SVG and does not support live
re-positioning of pieces via mouse drag).

The user picks an active piece from the palette on the left, then
clicks a square to place it, or clicks an existing piece to remove
it. Right-clicking a square always removes whatever is on it.

A FEN text field at the bottom of the dialog always reflects the
current position and is editable — typing a valid FEN and pressing
Enter loads it into the board.
"""
from __future__ import annotations

from typing import Optional

import chess
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QLineEdit, QFrame, QWidget, QButtonGroup, QToolButton,
    QMessageBox,
)

from ..styles import Styles
from ...utils.path_utils import get_resource_path


# Piece symbol that the palette lets the user pick. Empty string means
# "eraser" — clicking a square with this active removes the piece.
PIECE_CHOICES = ["K", "Q", "R", "B", "N", "P", "k", "q", "r", "b", "n", "p"]

# Same order as PIECE_CHOICES, but with the human-readable label and
# the SVG file used to render the icon in the palette button.
PIECE_DISPLAY = [
    ("K", "♔", "white-king.svg"),
    ("Q", "♕", "white-queen.svg"),
    ("R", "♖", "white-rook.svg"),
    ("B", "♗", "white-bishop.svg"),
    ("N", "♘", "white-knight.svg"),
    ("P", "♙", "white-pawn.svg"),
    ("k", "♚", "black-king.svg"),
    ("q", "♛", "black-queen.svg"),
    ("r", "♜", "black-rook.svg"),
    ("b", "♝", "black-bishop.svg"),
    ("n", "♞", "black-knight.svg"),
    ("p", "♟", "black-pawn.svg"),
]


def _load_piece_pixmap(symbol: str, size: int = 36) -> QPixmap:
    """Return a QPixmap for the given piece symbol.

    Tries to load the theme SVG from ``assets/pieces/`` and falls back
    to a unicode glyph in a serif font if the asset is missing so the
    dialog is still usable on a fresh checkout without artwork.
    """
    file_name = next(
        (f for s, _, f in PIECE_DISPLAY if s == symbol), None
    )
    if file_name:
        svg_path = get_resource_path(f"assets/pieces/{file_name}")
        try:
            pix = QPixmap(svg_path)
            if not pix.isNull():
                return pix.scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
        except Exception:
            pass

    # Fallback: paint a unicode glyph centred on a transparent pixmap.
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    glyph = next((g for s, g, _ in PIECE_DISPLAY if s == symbol), "?")
    colour = "#111" if symbol.islower() else "#f0f0f0"
    p.setPen(QColor(colour))
    f = QFont("Segoe UI Symbol", int(size * 0.7))
    f.setBold(True)
    p.setFont(f)
    p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, glyph)
    p.end()
    return pix


def _build_initial_board() -> chess.Board:
    """Start the editor with the standard chess starting position."""
    return chess.Board()


class PositionEditorDialog(QDialog):
    """Modal dialog for building an arbitrary chess position.

    On accept, the caller can read :attr:`result_fen` to get the FEN
    string of the position the user built.
    """

    def __init__(self, parent: Optional[QWidget] = None,
                 initial_fen: Optional[str] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Build Position")
        self.setMinimumSize(720, 560)
        self.setStyleSheet(
            f"QDialog {{ background-color: {Styles.COLOR_BACKGROUND}; "
            f"color: {Styles.COLOR_TEXT_PRIMARY}; }}"
        )

        # Active piece selected in the palette. "" = eraser.
        self._active_piece: str = "K"
        # 8x8 buttons representing the squares, indexed [row][col] with
        # row 0 = rank 8 (top of the board in white-orientation).
        self._square_buttons: list[list[QPushButton]] = []
        # Board state mirrored from the buttons.
        self._board: chess.Board = _build_initial_board()
        if initial_fen:
            try:
                self._board = chess.Board(initial_fen)
            except ValueError:
                # Fall back to start position on bad input rather than
                # crashing the dialog.
                self._board = chess.Board()

        self._build_ui()
        self._refresh_squares()
        self._sync_fen_field()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def result_fen(self) -> str:
        """FEN of the position the user built (always readable)."""
        return self._board.fen()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        root.addWidget(self._build_palette(), 0)
        root.addWidget(self._build_board_panel(), 1)
        root.addLayout(self._build_side_panel(), 0)

    def _build_palette(self) -> QWidget:
        """Left column: piece buttons + eraser."""
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background-color: {Styles.COLOR_SURFACE}; "
            f"border: 1px solid {Styles.COLOR_BORDER}; border-radius: 8px; }}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Pieces")
        title.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: 600; "
            f"font-size: 13px; border: none;"
        )
        layout.addWidget(title)

        # White pieces (uppercase symbols)
        white_lbl = QLabel("White")
        white_lbl.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px; "
            f"border: none;"
        )
        layout.addWidget(white_lbl)
        self._piece_group = QButtonGroup(self)
        self._piece_group.setExclusive(True)
        for sym in ["K", "Q", "R", "B", "N", "P"]:
            layout.addWidget(self._make_palette_button(sym))

        # Black pieces
        black_lbl = QLabel("Black")
        black_lbl.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px; "
            f"border: none;"
        )
        layout.addWidget(black_lbl)
        for sym in ["k", "q", "r", "b", "n", "p"]:
            layout.addWidget(self._make_palette_button(sym))

        # Eraser (no piece / remove)
        spacer = QFrame()
        spacer.setFixedHeight(8)
        spacer.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(spacer)
        eraser = QToolButton()
        eraser.setText("Eraser")
        eraser.setCheckable(True)
        eraser.setToolTip("Click a square to remove the piece on it")
        eraser.setStyleSheet(
            f"QToolButton {{ background-color: {Styles.COLOR_SURFACE_LIGHT}; "
            f"color: {Styles.COLOR_TEXT_PRIMARY}; border: 1px solid "
            f"{Styles.COLOR_BORDER}; border-radius: 6px; padding: 6px; }}"
            f"QToolButton:checked {{ background-color: {Styles.COLOR_ACCENT}; "
            f"color: white; border: 1px solid {Styles.COLOR_ACCENT}; }}"
        )
        eraser.clicked.connect(lambda: self._set_active_piece(""))
        self._piece_group.addButton(eraser)
        layout.addWidget(eraser)

        layout.addStretch()
        return frame

    def _make_palette_button(self, symbol: str) -> QToolButton:
        btn = QToolButton()
        btn.setCheckable(True)
        btn.setIcon(QIcon(_load_piece_pixmap(symbol, 32)))
        btn.setIconSize(QSize(32, 32))
        btn.setToolTip(self._tooltip_for(symbol))
        btn.setFixedSize(48, 48)
        btn.setStyleSheet(
            f"QToolButton {{ background-color: {Styles.COLOR_SURFACE_LIGHT}; "
            f"border: 1px solid {Styles.COLOR_BORDER}; border-radius: 6px; }}"
            f"QToolButton:hover {{ border-color: {Styles.COLOR_BORDER_LIGHT}; }}"
            f"QToolButton:checked {{ background-color: {Styles.COLOR_ACCENT_SUBTLE}; "
            f"border: 1px solid {Styles.COLOR_ACCENT}; }}"
        )
        btn.clicked.connect(lambda _checked=False, s=symbol: self._set_active_piece(s))
        self._piece_group.addButton(btn)
        if symbol == "K":
            btn.setChecked(True)
        return btn

    @staticmethod
    def _tooltip_for(symbol: str) -> str:
        if not symbol:
            return "Eraser"
        names = {
            "K": "White King", "Q": "White Queen", "R": "White Rook",
            "B": "White Bishop", "N": "White Knight", "P": "White Pawn",
            "k": "Black King", "q": "Black Queen", "r": "Black Rook",
            "b": "Black Bishop", "n": "Black Knight", "p": "Black Pawn",
        }
        return names.get(symbol, symbol)

    def _build_board_panel(self) -> QWidget:
        """Centre: the 8x8 board grid + FEN editor + action buttons."""
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background-color: {Styles.COLOR_SURFACE}; "
            f"border: 1px solid {Styles.COLOR_BORDER}; border-radius: 8px; }}"
        )
        v = QVBoxLayout(frame)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        # 8x8 board. We surround the grid with a rank/file coordinate
        # label so the user can see at a glance which square they are
        # editing.
        grid_outer = QGridLayout()
        grid_outer.setSpacing(2)
        for file_idx in range(8):
            lbl = QLabel(chess.FILE_NAMES[file_idx])
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 10px; "
                f"border: none;"
            )
            grid_outer.addWidget(lbl, 0, file_idx + 1)
        for rank_idx in range(8):
            lbl = QLabel(str(rank_idx + 1))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 10px; "
                f"border: none;"
            )
            grid_outer.addWidget(lbl, rank_idx + 1, 0)
        # Top-right corner spacer
        corner = QLabel("")
        corner.setStyleSheet("border: none;")
        grid_outer.addWidget(corner, 0, 0)

        for row in range(8):
            row_buttons: list[QPushButton] = []
            for col in range(8):
                btn = QPushButton()
                btn.setFixedSize(56, 56)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(self._square_button_style("light"))
                # Click coords in board space: row 0 = rank 8, so
                # chess square index = (7 - row) * 8 + col
                square = (7 - row) * 8 + col
                btn.clicked.connect(
                    lambda _checked=False, sq=square: self._on_square_left(sq)
                )
                # Use a customContextMenuEvent via mousePressEvent so we
                # can distinguish left vs right click without subclassing.
                btn.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
                btn.installEventFilter(self)
                btn.setProperty("square", square)
                grid_outer.addWidget(btn, row + 1, col + 1)
                row_buttons.append(btn)
            self._square_buttons.append(row_buttons)
        v.addLayout(grid_outer)

        # FEN text field — always reflects the current position, and
        # the user can paste a FEN to load it.
        fen_row = QHBoxLayout()
        fen_lbl = QLabel("FEN:")
        fen_lbl.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 12px; "
            f"border: none;"
        )
        fen_row.addWidget(fen_lbl)
        self._fen_edit = QLineEdit()
        self._fen_edit.setPlaceholderText(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        )
        self._fen_edit.setStyleSheet(
            f"QLineEdit {{ background-color: {Styles.COLOR_SURFACE_LIGHT}; "
            f"color: {Styles.COLOR_TEXT_PRIMARY}; border: 1px solid "
            f"{Styles.COLOR_BORDER}; border-radius: 6px; padding: 6px; "
            f"font-family: 'Consolas','Menlo',monospace; font-size: 12px; }}"
        )
        self._fen_edit.returnPressed.connect(self._load_fen_from_field)
        fen_row.addWidget(self._fen_edit, 1)
        v.addLayout(fen_row)

        # Bottom action buttons.
        actions = QHBoxLayout()
        actions.setSpacing(8)
        for label, handler in [
            ("Reset", self._reset_position),
            ("Clear Board", self._clear_board),
        ]:
            b = QPushButton(label)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton {{ background-color: {Styles.COLOR_SURFACE_LIGHT}; "
                f"color: {Styles.COLOR_TEXT_PRIMARY}; border: 1px solid "
                f"{Styles.COLOR_BORDER}; border-radius: 6px; padding: 8px 14px; }}"
                f"QPushButton:hover {{ background-color: {Styles.COLOR_HIGHLIGHT}; }}"
            )
            b.clicked.connect(handler)
            actions.addWidget(b)
        actions.addStretch()
        v.addLayout(actions)

        return frame

    def _build_side_panel(self) -> QVBoxLayout:
        """Right column: help text + primary action buttons."""
        layout = QVBoxLayout()
        layout.setSpacing(8)

        help_text = QLabel(
            "Pick a piece on the left, then click a square to place it.\n"
            "Right-click a square to remove the piece on it.\n"
            "Switch to the eraser to remove pieces with a left click."
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px; "
            f"line-height: 1.4;"
        )
        layout.addWidget(help_text)

        layout.addStretch()

        # Cancel / Use Position
        cancel = QPushButton("Cancel")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet(
            f"QPushButton {{ background-color: {Styles.COLOR_SURFACE}; "
            f"color: {Styles.COLOR_TEXT_SECONDARY}; border: 1px solid "
            f"{Styles.COLOR_BORDER}; border-radius: 6px; padding: 10px 18px; "
            f"font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {Styles.COLOR_SURFACE_LIGHT}; "
            f"color: {Styles.COLOR_TEXT_PRIMARY}; }}"
        )
        cancel.clicked.connect(self.reject)
        layout.addWidget(cancel)

        use = QPushButton("Use Position")
        use.setCursor(Qt.CursorShape.PointingHandCursor)
        use.setStyleSheet(
            f"QPushButton {{ background-color: {Styles.COLOR_ACCENT}; "
            f"color: white; border: none; border-radius: 6px; padding: 10px 18px; "
            f"font-size: 13px; font-weight: 600; }}"
            f"QPushButton:hover {{ background-color: {Styles.COLOR_ACCENT_HOVER}; }}"
        )
        use.clicked.connect(self._on_use_position)
        layout.addWidget(use)

        return layout

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def eventFilter(self, source, event):
        """Catch right-click on a square button to remove the piece."""
        if (event.type() == event.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.RightButton
                and source.property("square") is not None):
            square = int(source.property("square"))
            self._remove_piece_at(square)
            return True
        return super().eventFilter(source, event)

    def _on_square_left(self, square: int) -> None:
        if self._active_piece == "":
            self._remove_piece_at(square)
        else:
            self._place_piece_at(square, self._active_piece)

    def _on_use_position(self) -> None:
        if not self._board.piece_type_at(chess.E1) and any(
            self._board.piece_type_at(sq) == chess.KING
            and self._board.color_at(sq) == chess.WHITE
            for sq in chess.SQUARES
        ):
            pass  # white king present somewhere, all good
        if not any(
            self._board.piece_type_at(sq) == chess.KING
            for sq in chess.SQUARES
        ):
            QMessageBox.warning(
                self, "Invalid Position",
                "A chess position needs at least one king. Please add a "
                "king before using the position."
            )
            return
        if self._has_king(chess.WHITE) and self._has_king(chess.BLACK):
            # Also warn if the side-not-to-move is already in check; many
            # analysis flows assume a legal starting position.
            turn = self._board.turn
            king_sq = self._board.king(turn)
            if king_sq is not None and self._board.is_attacked_by(
                not turn, king_sq
            ):
                QMessageBox.warning(
                    self, "Invalid Position",
                    "The side to move is in check. Adjust the position "
                    "before continuing."
                )
                return
        self.accept()

    # ------------------------------------------------------------------
    # Board mutation helpers
    # ------------------------------------------------------------------
    def _set_active_piece(self, symbol: str) -> None:
        self._active_piece = symbol

    def _place_piece_at(self, square: int, symbol: str) -> None:
        piece = chess.Piece.from_symbol(symbol)
        if piece is None:
            return
        self._board.set_piece_at(square, piece)
        # Setting pieces directly puts the board in a messy state w.r.t.
        # turn/castling rights. Reset turn to white and clear castling
        # & en-passant so the position is a clean FEN the user can edit.
        self._board.turn = chess.WHITE
        self._board.castling_rights = 0
        self._board.ep_square = None
        self._board.clear_stack()
        self._refresh_squares()
        self._sync_fen_field()

    def _remove_piece_at(self, square: int) -> None:
        self._board.remove_piece_at(square)
        self._board.turn = chess.WHITE
        self._board.castling_rights = 0
        self._board.ep_square = None
        self._board.clear_stack()
        self._refresh_squares()
        self._sync_fen_field()

    def _reset_position(self) -> None:
        self._board = chess.Board()
        self._refresh_squares()
        self._sync_fen_field()

    def _clear_board(self) -> None:
        self._board = chess.Board.empty()
        self._board.turn = chess.WHITE
        self._refresh_squares()
        self._sync_fen_field()

    def _load_fen_from_field(self) -> None:
        text = self._fen_edit.text().strip()
        if not text:
            return
        try:
            new_board = chess.Board(text)
        except ValueError as e:
            QMessageBox.warning(
                self, "Invalid FEN", f"The FEN could not be parsed:\n{e}"
            )
            return
        self._board = new_board
        self._refresh_squares()
        self._sync_fen_field()

    # ------------------------------------------------------------------
    # View sync
    # ------------------------------------------------------------------
    def _refresh_squares(self) -> None:
        """Re-render every square button from the current board state."""
        for row_idx, row_buttons in enumerate(self._square_buttons):
            for col_idx, btn in enumerate(row_buttons):
                square = (7 - row_idx) * 8 + col_idx
                piece = self._board.piece_at(square)
                is_light = (chess.square_file(square)
                            + chess.square_rank(square)) % 2 == 1
                btn.setStyleSheet(self._square_button_style(
                    "light" if is_light else "dark"
                ))
                if piece is None:
                    btn.setText("")
                    btn.setIcon(QIcon())
                else:
                    sym = piece.symbol()
                    pix = _load_piece_pixmap(sym, 44)
                    btn.setIcon(QIcon(pix))
                    btn.setIconSize(QSize(44, 44))
                    btn.setText("")

    def _sync_fen_field(self) -> None:
        # Block the signal so we don't trigger a reload loop.
        self._fen_edit.blockSignals(True)
        self._fen_edit.setText(self._board.fen())
        self._fen_edit.blockSignals(False)

    @staticmethod
    def _square_button_style(scheme: str) -> str:
        if scheme == "light":
            bg = Styles.COLOR_SURFACE_LIGHT
        else:
            bg = Styles.COLOR_HIGHLIGHT
        return (
            f"QPushButton {{ background-color: {bg}; border: 1px solid "
            f"{Styles.COLOR_BORDER}; border-radius: 0; }}"
            f"QPushButton:hover {{ border: 1px solid {Styles.COLOR_ACCENT}; }}"
        )

    def _has_king(self, color: bool) -> bool:
        for sq in chess.SQUARES:
            p = self._board.piece_at(sq)
            if p and p.piece_type == chess.KING and p.color == color:
                return True
        return False

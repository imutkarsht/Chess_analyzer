"""
Position Editor View - Lets the user build an arbitrary chess position
by placing pieces on an 8x8 grid. The resulting FEN is exposed via the
``result_fen`` property (always readable) and via the
``position_accepted`` signal, which the MainWindow listens to in order
to load the position into the analysis flow.

This is a *view* (a QWidget hosted by the MainWindow's QStackedWidget),
not a modal dialog, so it sits inside the existing layout — the sidebar
stays visible, the status bar is still accessible, and the user can
press "Back" to return to whatever page they came from. The header row
matches the style used by HistoryView and SettingsView (title on the
left, primary action on the right) for visual consistency.

The user picks an active piece from the palette on the left, then
clicks a square to place it, or clicks an existing piece to remove it.
Right-clicking a square always removes whatever is on it. A FEN text
field at the bottom of the view always reflects the current position
and is editable — typing a valid FEN and pressing Enter loads it.
"""
from __future__ import annotations

from typing import Optional

import chess
from PyQt6.QtCore import Qt, QSize, QPoint, QPointF, pyqtSignal, QEvent
from PyQt6.QtGui import QIcon, QPixmap, QColor, QFont, QPainter, QCursor, QImage
from PyQt6.QtSvg import QSvgRenderer

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QLineEdit, QFrame, QButtonGroup, QToolButton,
    QMessageBox, QSizePolicy, QSplitter,
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
    """Return a QPixmap for the given piece symbol (palette + drag).

    Uses QSvgRenderer → QImage(ARGB32) at the *exact* target size so
    the vector art is rendered sharp.  Since we now paint the drag
    pixmap locally via _DragOverlay (chessx model) instead of handing
    it to the X11 drag protocol, the alpha channel survives intact.
    """
    file_name = next(
        (f for s, _, f in PIECE_DISPLAY if s == symbol), None
    )
    if file_name:
        svg_path = get_resource_path(f"assets/pieces/{file_name}")
        try:
            renderer = QSvgRenderer(svg_path)
            if renderer.isValid():
                img = QImage(size, size, QImage.Format.Format_ARGB32)
                img.fill(QColor(0, 0, 0, 0))
                p = QPainter(img)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                renderer.render(p)
                p.end()
                pix = QPixmap.fromImage(img)
                if not pix.isNull():
                    return pix
        except Exception:
            pass

    # Fallback: paint a unicode glyph centred on a transparent pixmap.
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
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


class _DragOverlay(QWidget):
    """Invisible canvas on top of the board that paints the piece
    under the cursor during a drag operation.

    This is the chessx model: instead of using QDrag (whose pixmap
    has no alpha on X11), we paint directly on a transparent widget
    layered over the board.  Qt's widget compositing handles
    transparency correctly because it's all local rendering — no
    X11 server pixmap ever crosses the wire.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._pixmap: QPixmap | None = None
        self._hotspot: QPoint = QPoint(0, 0)
        self.hide()

    def configure(self, pixmap: QPixmap, pos: QPointF) -> None:
        """Set the image and its on-screen centre in parent coords."""
        self._pixmap = pixmap
        self._hotspot = QPoint(
            int(pos.x() - pixmap.width() // 2),
            int(pos.y() - pixmap.height() // 2),
        )
        self.update()

    def clear(self) -> None:
        self._pixmap = None
        self.hide()

    def paintEvent(self, _event) -> None:
        if self._pixmap is None:
            return
        p = QPainter(self)
        p.drawPixmap(self._hotspot, self._pixmap)
        p.end()


def _build_initial_board() -> chess.Board:
    """Start the editor with the standard chess starting position."""
    return chess.Board()


class PositionEditorView(QWidget):
    """Full-page view for building an arbitrary chess position.

    On accept, the caller can read :attr:`result_fen` to get the FEN
    string of the position the user built. The
    :attr:`position_accepted` signal is emitted at the same time so
    the MainWindow can switch back to the analysis view and load the
    position into the standard game/board pipeline.

    Signals
    -------
    position_accepted(str)
        Emitted when the user clicks "Use Position" with a valid
        position. Payload is the FEN string.
    back_requested()
        Emitted when the user clicks "Back". The MainWindow listens
        to this to return to the previously active page (Analyze by
        default).
    """

    position_accepted = pyqtSignal(str)
    back_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None,
                 initial_fen: Optional[str] = None) -> None:
        super().__init__(parent)
        # No window title or min-size — we're embedded in the
        # QStackedWidget and the main window owns sizing.

        # Active piece selected in the palette. "" = eraser.
        self._active_piece: str = "K"
        # Exclusive button group so only one palette piece (or the
        # eraser) is selected at a time.
        self._piece_group = QButtonGroup(self)
        self._piece_group.setExclusive(True)
        # Painted-drag state (chessx model — no QDrag).
        # _drag_source_square → pressed square (>=0 means "button down
        #   on a piece, maybe about to start a drag").
        # _drag_start_pos     → pixel position of the press.
        # _drag_piece         → non-None when a drag is ACTIVE and the
        #   overlay is painting the piece under the cursor.
        self._drag_source_square: int = -1
        self._drag_start_pos: QPointF | None = None
        self._drag_piece: chess.Piece | None = None
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
                # crashing the view.
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
        # Root layout — 1:1 identical to setup_analysis_page(parent_widget)
        # in main_window.py. QHBoxLayout with margins=0, spacing=0
        # wrapping a QSplitter. NO header — the splitter fills the
        # entire available space.
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        root.addWidget(splitter)

        # Left slot — QWidget(QVBoxLayout(margins=0)) wrapping palette
        # + button row, exactly like main_window's left_widget wrapping
        # btn_layout + MoveListPanel.
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Button row — mirrors the Load Game / Analyze Game row above
        # MoveListPanel. Same "secondary" style as Load Game.
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        eraser_btn = QPushButton("Eraser")
        eraser_btn.setCheckable(True)
        eraser_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        eraser_btn.setStyleSheet(
            Styles.get_control_button_style()
            + f"QPushButton:checked {{ background-color: {Styles.COLOR_ACCENT}; "
            f"color: white; border: 1px solid {Styles.COLOR_ACCENT}; }}"
        )
        eraser_btn.clicked.connect(lambda: self._set_active_piece(""))
        self._piece_group.addButton(eraser_btn)
        btn_row.addWidget(eraser_btn)
        left_layout.insertLayout(0, btn_row)

        left_layout.addWidget(self._build_palette())
        splitter.addWidget(left_widget)

        # Center slot — _build_board_panel() now includes the title
        # label just like Analyze has game_info_label above the board.
        splitter.addWidget(self._build_board_panel())

        # Right slot — QWidget wrapping side panel + action buttons,
        # mirroring how AnalysisPanel holds the Load/Analyze buttons.
        side_widget = QWidget()
        side_widget.setLayout(self._build_side_panel())
        splitter.addWidget(side_widget)

        # ⚠️ MUST match the Analyze tab's splitter proportions exactly
        # (main_window.py line 629). Without this the palette's narrower
        # width causes the board to grab extra horizontal space.
        splitter.setSizes([250, 600, 350])

    def _build_palette(self) -> QWidget:
        """Left column: piece buttons (white & black side by side) + eraser."""
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background-color: {Styles.COLOR_SURFACE}; "
            f"border: 1px solid {Styles.COLOR_BORDER}; border-radius: 8px; }}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title = QLabel("Pieces")
        title.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: 600; "
            f"font-size: 13px; border: none;"
        )
        layout.addWidget(title)

        # Two columns: White (left) | Black (right)
        cols = QHBoxLayout()
        cols.setSpacing(8)

        # ── White column ──
        white_col = QVBoxLayout()
        white_col.setSpacing(4)
        white_lbl = QLabel("White")
        white_lbl.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px; "
            f"border: none;"
        )
        white_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        white_col.addWidget(white_lbl)
        for sym in ["K", "Q", "R", "B", "N", "P"]:
            white_col.addWidget(
                self._make_palette_button(sym), 0,
                Qt.AlignmentFlag.AlignCenter
            )
        cols.addLayout(white_col)

        # ── Black column ──
        black_col = QVBoxLayout()
        black_col.setSpacing(4)
        black_lbl = QLabel("Black")
        black_lbl.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px; "
            f"border: none;"
        )
        black_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        black_col.addWidget(black_lbl)
        for sym in ["k", "q", "r", "b", "n", "p"]:
            black_col.addWidget(
                self._make_palette_button(sym), 0,
                Qt.AlignmentFlag.AlignCenter
            )
        cols.addLayout(black_col)

        layout.addLayout(cols)

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
        """Centre column — same layout parameters as the Analyze page's
        ``center_layout`` (margins=10, spacing=10, BoardWidget at
        stretch=1). No extra QFrame wrapper so the BoardWidget receives
        the exact same amount of space it gets in the Analyze tab, and
        therefore renders at the same size.
        """
        from ..board.board_widget import BoardWidget

        panel = QWidget()
        layout = QVBoxLayout(panel)
        # ⚠️  MUST match the Analyze page's center_layout exactly:
        #     main_window.py lines 519-520
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Title label — mirrors game_info_label in Analyze
        title = QLabel("Build Position")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"font-size: 16px; font-weight: bold; "
            f"color: {Styles.COLOR_TEXT_PRIMARY}; padding: 5px;"
        )
        layout.addWidget(title)

        self._board_widget = BoardWidget()
        self._board_widget.board = self._board
        self._board_widget.eval_bar.hide()
        self._board_widget.update_board()
        # Catch mouse events on the SVG surface for click / painted drag.
        self._board_widget.svg_widget.installEventFilter(self)
        # Transparent overlay that paints the dragged piece at the mouse
        # position (chessx approach — no QDrag, no X11 pixmap issues).
        self._drag_overlay = _DragOverlay(self._board_widget.board_container)
        self._drag_overlay.setGeometry(
            0, 0,
            self._board_widget.board_container.width(),
            self._board_widget.board_container.height(),
        )
        self._drag_overlay.raise_()
        layout.addWidget(self._board_widget, 1)

        # FEN text field
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
        layout.addLayout(fen_row)

        # Bottom action buttons
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
        layout.addLayout(actions)

        return panel

    def _build_side_panel(self) -> QVBoxLayout:
        """Right column: action buttons + help text.

        Mirroring how AnalysisPanel holds the Load Game / Analyze Game
        buttons in the Analyze tab, we put the primary actions (Back,
        Use Position) at the top of the right panel.
        """
        layout = QVBoxLayout()
        layout.setSpacing(8)

        # ── Action buttons ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        back = QPushButton("Back")
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.setStyleSheet(
            f"QPushButton {{ background-color: {Styles.COLOR_SURFACE}; "
            f"color: {Styles.COLOR_TEXT_SECONDARY}; border: 1px solid "
            f"{Styles.COLOR_BORDER}; border-radius: 6px; padding: 10px 18px; "
            f"font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {Styles.COLOR_SURFACE_LIGHT}; "
            f"color: {Styles.COLOR_TEXT_PRIMARY}; }}"
        )
        back.clicked.connect(self.back_requested.emit)
        btn_row.addWidget(back)

        use = QPushButton("Use Position")
        use.setCursor(Qt.CursorShape.PointingHandCursor)
        use.setStyleSheet(
            f"QPushButton {{ background-color: {Styles.COLOR_ACCENT}; "
            f"color: white; border: none; border-radius: 6px; "
            f"padding: 10px 18px; font-size: 13px; font-weight: 600; }}"
            f"QPushButton:hover {{ background-color: {Styles.COLOR_ACCENT_HOVER}; }}"
        )
        use.clicked.connect(self._on_use_position)
        btn_row.addWidget(use)
        layout.addLayout(btn_row)

        # ── Help text ──
        help_text = QLabel(
            "Pick a piece on the left, then click a square to place it.\n"
            "Right-click a square to remove the piece on it.\n"
            "Drag a piece to move it to a different square.\n\n"
            "Click \"Use Position\" to load the position into the\n"
            "analyzer, or \"Back\" to return without changes."
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px; "
            f"line-height: 1.4;"
        )
        layout.addWidget(help_text)
        layout.addStretch()
        return layout

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def _on_square_clicked(self, square: int, button: Qt.MouseButton) -> None:
        """Callback from the _BoardGridWidget on click.

        Right-click always removes the piece on the square (regardless
        of which palette piece is active). Left-click places the
        active piece, or — if the eraser is selected — removes the
        piece.
        """
        if button == Qt.MouseButton.RightButton:
            self._remove_piece_at(square)
            return
        if self._active_piece == "":
            self._remove_piece_at(square)
        else:
            self._place_piece_at(square, self._active_piece)

    def _on_use_position(self) -> None:
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
            # Warn if the side-to-move is already in check; many
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
        self.position_accepted.emit(self._board.fen())

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
        # IMPORTANT: mutate the existing board in place rather than
        # replacing ``self._board`` with a new instance. The
        # ``_BoardGridWidget`` holds its own reference to the board
        # we passed in at construction time — if we swap the view's
        # ``self._board`` for a new chess.Board, the grid keeps
        # pointing at the old (now stale) instance and continues to
        # paint whatever was on it last. That bug showed up as
        # "Clear Board / Reset doesn't actually clear the board".
        self._board.set_fen(chess.STARTING_FEN)
        self._refresh_squares()
        self._sync_fen_field()

    def _clear_board(self) -> None:
        # Same in-place mutation as ``_reset_position`` above — see
        # the comment there for why we cannot just rebind
        # ``self._board`` here.
        self._board.set_fen("8/8/8/8/8/8/8/8 w - - 0 1")
        self._refresh_squares()
        self._sync_fen_field()

    def _load_fen_from_field(self) -> None:
        text = self._fen_edit.text().strip()
        if not text:
            return
        try:
            parsed = chess.Board(text)
        except ValueError as e:
            QMessageBox.warning(
                self, "Invalid FEN", f"The FEN could not be parsed:\n{e}"
            )
            return
        # Mutate the existing board in place (see the comment in
        # ``_reset_position`` for the rationale). If we rebind
        # ``self._board`` to a new instance, the ``_BoardGridWidget``
        # keeps painting the previous one.
        self._board.set_fen(parsed.fen())
        self._refresh_squares()
        self._sync_fen_field()

    # ------------------------------------------------------------------
    # View sync
    # ------------------------------------------------------------------
    def _refresh_squares(self) -> None:
        """Re-render the board from the current chess.Board state.

        The editor and the BoardWidget share the same ``chess.Board``
        object (``self._board``). A single ``update_board()`` call
        regenerates the SVG with the latest piece set.
        """
        if hasattr(self, "_board_widget"):
            self._board_widget.update_board()

    # ------------------------------------------------------------------
    # Click / painted-drag handling (event filter on BoardWidget.svg_widget)
    # ------------------------------------------------------------------
    def eventFilter(self, obj, event):
        """Catch mouse press / move / release on the SVG surface.

        Clicks place or remove pieces.  Pressing on an occupied square
        and moving >5 px starts a *painted* drag — the piece is painted
        on a transparent overlay at the cursor position without ever
        touching QDrag (same technique chessx uses).
        """
        if not (hasattr(self, "_board_widget")
                and obj is self._board_widget.svg_widget):
            return super().eventFilter(obj, event)

        etype = event.type()

        # ── Press ────────────────────────────────────────────────
        if etype == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                square = self._map_click_to_square(event.position(), obj)
                if square < 0:
                    return True
                piece = self._board.piece_at(square)
                if piece is not None:
                    # Occupied square — prepare for a possible drag.
                    self._drag_source_square = square
                    self._drag_start_pos = event.position()
                    return True
                # Empty square — place the active piece (or erase).
                self._on_square_clicked(square, Qt.MouseButton.LeftButton)
                return True
            if event.button() == Qt.MouseButton.RightButton:
                square = self._map_click_to_square(event.position(), obj)
                if square >= 0:
                    self._on_square_clicked(square, Qt.MouseButton.RightButton)
                return True

        # ── Move (potential drag start, or active drag) ─────────
        if etype == QEvent.Type.MouseMove:
            square = self._map_click_to_square(event.position(), obj)
            pos = event.position()

            if self._drag_piece is not None:
                # Already dragging — keep the overlay centred on cursor.
                self._drag_overlay.configure(self._drag_pixmap, pos)
                return True

            if (self._drag_source_square >= 0
                    and self._drag_start_pos is not None):
                delta = pos - self._drag_start_pos
                if delta.manhattanLength() > 5:
                    self._begin_painted_drag(pos)
                return True

        # ── Release ─────────────────────────────────────────────
        if etype == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton:
                if self._drag_piece is not None:
                    # Finishing a painted drag.
                    target = self._map_click_to_square(
                        event.position(), obj
                    )
                    self._end_painted_drag(target)
                    return True
                # Simple click (press+release without drag) on a
                # piece — do nothing extra; the piece stays in place.
                self._drag_source_square = -1
                self._drag_start_pos = None
            return True

        return super().eventFilter(obj, event)

    # ── Painted drag (chessx model) ─────────────────────────────
    def _begin_painted_drag(self, pos: QPointF) -> None:
        """Start painting the piece under the cursor.

        The piece is temporarily removed from the board model so the
        user doesn't see a duplicate.  A transparent overlay paints
        the SVG pixmap centred on the mouse position.
        """
        piece = self._board.piece_at(self._drag_source_square)
        if piece is None:
            return
        self._drag_piece = piece
        self._board.remove_piece_at(self._drag_source_square)
        self._refresh_squares()

        # Build the pixmap at the exact on-screen square size.
        board_side = self._board_widget.board_container.width()
        square_size = max(board_side * 45 // 390, 36)
        self._drag_pixmap = _load_piece_pixmap(piece.symbol(), square_size)

        # Ensure the overlay covers the whole board container.
        c = self._board_widget.board_container
        self._drag_overlay.setGeometry(0, 0, c.width(), c.height())
        self._drag_overlay.configure(self._drag_pixmap, pos)
        self._drag_overlay.show()
        self._drag_overlay.raise_()
        self._drag_start_pos = None  # consumed

    def _end_painted_drag(self, target: int) -> None:
        """Finish the painted drag: place (or return) the piece."""
        piece = self._drag_piece
        source = self._drag_source_square
        self._drag_piece = None
        self._drag_source_square = -1
        self._drag_overlay.clear()

        if piece is None:
            return

        if target < 0 or target == source:
            # Invalid drop or same square — put the piece back.
            self._board.set_piece_at(source, piece)
        else:
            self._board.set_piece_at(target, piece)
            self._board.turn = chess.WHITE
            self._board.castling_rights = 0
            self._board.ep_square = None
            self._board.clear_stack()

        self._refresh_squares()
        self._sync_fen_field()

    @staticmethod
    def _map_click_to_square(pos, container) -> int:
        """Map a click position (relative to ``board_container``) to a
        chess square index, or -1 if the click is outside the 8x8 area.

        The calculation uses the fixed SVG constants from
        ``BoardWidget._generate_custom_board_svg`` (SQUARE_SIZE=45,
        MARGIN=15, FULL_SIZE=390). The SVG is scaled to fill the
        container, so we convert the pixel position to SVG-space first.
        """
        # BoardWidget SVG constants (from _generate_custom_board_svg)
        SVG_SQUARE = 45
        SVG_MARGIN = 15
        SVG_FULL = 8 * SVG_SQUARE + 2 * SVG_MARGIN  # 390

        side = container.width()
        if side <= 0:
            return -1
        scale = SVG_FULL / side
        svg_x = pos.x() * scale
        svg_y = pos.y() * scale
        if svg_x < SVG_MARGIN or svg_y < SVG_MARGIN:
            return -1
        file_idx = int((svg_x - SVG_MARGIN) // SVG_SQUARE)
        rank_idx = int((svg_y - SVG_MARGIN) // SVG_SQUARE)
        if not (0 <= file_idx < 8 and 0 <= rank_idx < 8):
            return -1
        # White at bottom: SVG rank 0 = chess rank 7 (a8…), SVG rank 7
        # = chess rank 0 (a1…).
        return (7 - rank_idx) * 8 + file_idx

    def _sync_fen_field(self) -> None:
        # Block the signal so we don't trigger a reload loop.
        self._fen_edit.blockSignals(True)
        self._fen_edit.setText(self._board.fen())
        self._fen_edit.blockSignals(False)

    def _has_king(self, color: bool) -> bool:
        for sq in chess.SQUARES:
            p = self._board.piece_at(sq)
            if p and p.piece_type == chess.KING and p.color == color:
                return True
        return False

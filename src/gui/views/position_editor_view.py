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

import time
from typing import Optional
from enum import IntEnum

import chess
from PyQt6.QtCore import Qt, QSize, QPoint, QPointF, pyqtSignal, QEvent, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QColor, QFont, QPainter, QCursor, QImage, QPen, QBrush
from PyQt6.QtSvg import QSvgRenderer

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QLineEdit, QFrame, QButtonGroup, QToolButton,
    QMessageBox, QSizePolicy, QSplitter, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)

from ..styles import Styles
from ...backend.models import GameAnalysis, GameMetadata, MoveAnalysis
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


class EditorMode(IntEnum):
    """Editing modes for the Position Editor."""
    FREE = 0         # Pieces can be placed anywhere, no rules.
    LEGAL_MOVES = 1  # Only legal moves allowed; target squares highlighted.
    BEST_MOVE = 2    # Legal moves + engine best-move indicator.


class _LegalMovesOverlay(QWidget):
    """Transparent canvas on top of the board that paints legal-move
    target dots and optionally an engine best-move indicator.

    This is a sibling of ``_DragOverlay`` — both sit on top of the
    board container but serve different purposes.  This one shows
    static move-hint dots while the drag overlay paints the piece
    being dragged.
    """

    _DOT_COLOR = QColor(0, 180, 0, 120)          # semi-transparent green
    _DOT_OUTLINE = QColor(0, 140, 0, 200)
    _BEST_DOT_COLOR = QColor(0, 200, 0, 220)      # more opaque, brighter
    _BEST_DOT_OUTLINE = QColor(0, 220, 0, 255)
    _CAPTURE_COLOR = QColor(220, 60, 60, 140)     # reddish for captures
    _CAPTURE_OUTLINE = QColor(180, 40, 40, 200)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._legal_squares: set[int] = set()
        self._best_square: int | None = None
        self._board: chess.Board | None = None
        self._svg_square: int = 45
        self._svg_margin: int = 15
        self._svg_full: int = 8 * 45 + 2 * 15  # 390
        self.hide()

    def set_squares(self, legal: set[int], best: int | None = None,
                    board: chess.Board | None = None) -> None:
        """Set the squares to highlight and optionally the best-move square."""
        self._legal_squares = legal
        self._best_square = best
        self._board = board
        if legal or best is not None:
            self.show()
            self.raise_()
        else:
            self.hide()
        self.update()

    def clear(self) -> None:
        self._legal_squares = set()
        self._best_square = None
        self._board = None
        self.hide()

    def _square_to_overlay_rect(self, square: int,
                                 container_w: int, container_h: int):
        """Return (x, y, w, h) in overlay pixel coords for a chess square."""
        scale = container_w / self._svg_full if container_w > 0 else 1.0
        rank_idx = 7 - chess.square_rank(square)  # white at bottom
        file_idx = chess.square_file(square)
        x = self._svg_margin + file_idx * self._svg_square
        y = self._svg_margin + rank_idx * self._svg_square
        return int(x / scale), int(y / scale), max(1, int(self._svg_square / scale)), max(1, int(self._svg_square / scale))

    def paintEvent(self, _event) -> None:
        if not self._legal_squares and self._best_square is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cw, ch = self.width(), self.height()
        if cw <= 0 or ch <= 0:
            p.end()
            return

        for sq in self._legal_squares:
            x, y, w, h = self._square_to_overlay_rect(sq, cw, ch)
            cx, cy = x + w // 2, y + h // 2
            radius = int(w * 0.22)

            # Determine if this is a capture square (enemy piece on it)
            is_capture = (
                self._board is not None
                and self._board.piece_at(sq) is not None
            )
            fill = self._CAPTURE_COLOR if is_capture else self._DOT_COLOR
            outline = self._CAPTURE_OUTLINE if is_capture else self._DOT_OUTLINE

            # For capture squares, draw a ring (hollow circle) around the edge
            if is_capture:
                p.setPen(QPen(outline, max(2, int(w * 0.06))))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)
            else:
                p.setPen(QPen(outline, 1))
                p.setBrush(QBrush(fill))
                p.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)

        # Best-move square gets a brighter, larger filled dot
        if self._best_square is not None:
            sq = self._best_square
            x, y, w, h = self._square_to_overlay_rect(sq, cw, ch)
            cx, cy = x + w // 2, y + h // 2
            radius = int(w * 0.28)
            p.setPen(QPen(self._BEST_DOT_OUTLINE, 2))
            p.setBrush(QBrush(self._BEST_DOT_COLOR))
            p.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)

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

        # Editing mode — see EditorMode enum.  Free = no rules,
        # Legal Moves = only legal chess moves, Best Move = legal +
        # engine best-move indicator.
        self._editor_mode: EditorMode = EditorMode.FREE

        # Optional Analyzer reference for Best Move mode. Set by the
        # MainWindow via set_analyzer() after construction.
        self._analyzer = None

        # Hover state for legal-move / best-move overlay.
        self._hovered_square: int = -1
        self._legal_move_squares: set[int] = set()
        self._best_move_square: int | None = None

        # Engine lifecycle for Best Move mode.
        self._engine_started_for_editor: bool = False

        # Debounce timer for Best Move engine queries — avoids firing
        # on every pixel of mouse movement.
        self._best_move_timer = QTimer(self)
        self._best_move_timer.setSingleShot(True)
        self._best_move_timer.setInterval(120)
        self._best_move_timer.timeout.connect(self._query_best_move)

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

        # ── Move tracking (Legal Moves / Best Move modes) ─────────
        # Record every push() as {ply, san, uci, time_spent, fen_before}
        self._move_history: list[dict] = []
        self._last_move_time: float = 0.0   # timestamp of last move
        self._starting_fen: str = ""        # FEN when recording started
        self._is_recording: bool = False    # True while in Legal/Best mode

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

    def set_analyzer(self, analyzer) -> None:
        """Give the editor access to the engine analyzer for Best Move mode.

        ``analyzer`` is an instance of ``Analyzer`` (src/backend/analyzer.py).
        It must be set before Best Move mode can be used.
        """
        self._analyzer = analyzer

    @property
    def editor_mode(self) -> EditorMode:
        return self._editor_mode

    @editor_mode.setter
    def editor_mode(self, mode: EditorMode) -> None:
        old = self._editor_mode
        self._editor_mode = mode
        # Manage engine lifecycle when entering / leaving Best Move mode.
        if mode == EditorMode.BEST_MOVE and old != EditorMode.BEST_MOVE:
            self._start_editor_engine()
        elif mode != EditorMode.BEST_MOVE and old == EditorMode.BEST_MOVE:
            self._stop_editor_engine()
        # Start / stop move recording.
        if mode != EditorMode.FREE and old == EditorMode.FREE:
            self._start_recording()
            self._refresh_move_table()
        elif mode == EditorMode.FREE and old != EditorMode.FREE:
            self._stop_recording()
            self._refresh_move_table()
        # Clear highlights on mode change.
        self._clear_highlights()

    # ------------------------------------------------------------------
    # Engine lifecycle (Best Move mode)
    # ------------------------------------------------------------------
    def _start_editor_engine(self) -> None:
        """Start the engine for Best Move queries, if not already running."""
        if self._analyzer is None:
            return
        try:
            em = self._analyzer.engine_manager
            if em.engine is None:
                em.start_engine()
            self._engine_started_for_editor = True
        except Exception:
            # Engine not available — Best Move mode will silently
            # fall back to Legal Moves behaviour.
            self._engine_started_for_editor = False

    def _stop_editor_engine(self) -> None:
        """Stop the engine if we started it for the editor."""
        if not self._engine_started_for_editor or self._analyzer is None:
            return
        try:
            self._analyzer.engine_manager.stop_engine()
        except Exception:
            pass
        finally:
            self._engine_started_for_editor = False

    # ------------------------------------------------------------------
    # Highlight helpers
    # ------------------------------------------------------------------
    def _compute_legal_targets(self, from_square: int) -> set[int]:
        """Return the set of legal target squares for the piece on
        ``from_square``.  Returns an empty set if the square is empty
        or if the position itself is illegal (e.g. no kings)."""
        piece = self._board.piece_at(from_square)
        if piece is None:
            return set()
        # Only legal_moves uses chess' built-in legality check which
        # requires a somewhat sensible position (at least one king of
        # each colour, not in check after the move, etc.).  If the
        # position is crazy (e.g. no kings), we fall back gracefully.
        try:
            targets = set()
            for m in self._board.legal_moves:
                if m.from_square == from_square:
                    targets.add(m.to_square)
            return targets
        except (ValueError, AssertionError):
            # Position is not legal enough for legal_moves to work.
            return set()

    def _query_best_move(self) -> None:
        """Ask the engine for the best move in the current position.

        Called by the debounce timer when the user hovers a piece in
        Best Move mode.  Stores the result in ``self._best_move_square``
        and refreshes the overlay.
        """
        if (self._editor_mode != EditorMode.BEST_MOVE
                or self._analyzer is None
                or self._hovered_square < 0):
            return
        try:
            em = self._analyzer.engine_manager
            if em.engine is None:
                em.start_engine()
                self._engine_started_for_editor = True
            info = em.analyze_position(self._board, time_limit=0.1)
            pv = info.get("pv", [])
            if pv and len(pv) > 0:
                self._best_move_square = pv[0].to_square
            else:
                self._best_move_square = None
        except Exception:
            self._best_move_square = None
        self._draw_legal_move_highlights()

    def _draw_legal_move_highlights(self) -> None:
        """Paint legal-move dots and optional best-move indicator on the overlay."""
        if not hasattr(self, "_legal_moves_overlay"):
            return
        legal = self._legal_move_squares
        best = self._best_move_square if self._editor_mode == EditorMode.BEST_MOVE else None
        self._legal_moves_overlay.set_squares(legal, best, self._board)

    def _clear_highlights(self) -> None:
        """Remove all legal-move / best-move visual indicators."""
        self._hovered_square = -1
        self._legal_move_squares = set()
        self._best_move_square = None
        self._best_move_timer.stop()
        if hasattr(self, "_legal_moves_overlay"):
            self._legal_moves_overlay.clear()

    def _on_hover_square(self, square: int) -> None:
        """Handle mouse hovering over a square — show legal-move /
        best-move highlights for the piece on that square.

        Called from eventFilter on every MouseMove when not dragging
        and the editor is in Legal or Best Move mode.
        """
        if square == self._hovered_square:
            return
        self._hovered_square = square
        if square < 0:
            self._clear_highlights()
            return
        piece = self._board.piece_at(square)
        if piece is None:
            self._clear_highlights()
            return
        self._legal_move_squares = self._compute_legal_targets(square)
        if self._editor_mode == EditorMode.BEST_MOVE:
            self._best_move_square = None  # reset until engine answers
            self._best_move_timer.start()   # debounced engine query
        else:
            self._best_move_square = None
        self._draw_legal_move_highlights()

    # ------------------------------------------------------------------
    # Move validation
    # ------------------------------------------------------------------
    def _is_move_allowed(self, from_sq: int, to_sq: int) -> bool:
        """Return True if moving from ``from_sq`` to ``to_sq`` is allowed
        under the current editing mode."""
        if self._editor_mode == EditorMode.FREE:
            return True
        try:
            move = chess.Move(from_sq, to_sq)
            return self._board.is_legal(move)
        except (ValueError, AssertionError):
            return False

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

        # ── Left slot — Move list table ─────────────────────────
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self._build_move_list_panel())
        splitter.addWidget(left_widget)

        # ── Center slot — Board + captured pieces ───────────────
        splitter.addWidget(self._build_board_panel())

        # ── Right slot — Eraser + palette + mode + FEN + buttons ──
        side_widget = QWidget()
        side_widget.setLayout(self._build_side_panel())
        splitter.addWidget(side_widget)

        # ⚠️ MUST match the Analyze tab's splitter proportions exactly
        # (main_window.py line 629).
        splitter.setSizes([250, 600, 350])

    def _build_move_list_panel(self) -> QWidget:
        """Left column: move list table (3 columns: #, White, Black).

        Records moves made in Legal Moves / Best Move modes with
        think-time per move.  Styled to match MoveListPanel from
        the Analyze view.
        """
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background-color: {Styles.COLOR_SURFACE}; "
            f"border: 1px solid {Styles.COLOR_BORDER}; border-radius: 8px; }}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        title = QLabel("Moves")
        title.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: 600; "
            f"font-size: 13px; border: none;"
        )
        layout.addWidget(title)

        self._move_table = QTableWidget()
        self._move_table.setColumnCount(3)
        self._move_table.setHorizontalHeaderLabels(["#", "White", "Black"])
        self._move_table.horizontalHeader().setHighlightSections(False)
        self._move_table.horizontalHeader().setMinimumHeight(28)

        header = self._move_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 30)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

        self._move_table.verticalHeader().setVisible(False)
        self._move_table.setShowGrid(False)
        self._move_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self._move_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._move_table.verticalHeader().setDefaultSectionSize(38)
        self._move_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Styles.COLOR_SURFACE};
                border: none;
                gridline-color: transparent;
                font-size: 13px;
            }}
            QTableWidget::item {{
                padding: 4px 6px;
                border-bottom: 1px solid {Styles.COLOR_SURFACE_LIGHT};
            }}
            QTableWidget::item:selected {{
                background-color: {Styles.COLOR_HIGHLIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
            QHeaderView::section {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_SECONDARY};
                padding: 6px 4px;
                border: none;
                border-bottom: 2px solid {Styles.COLOR_ACCENT};
                font-weight: 600;
                font-size: 12px;
            }}
        """)

        layout.addWidget(self._move_table)
        return frame

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
        from ..analysis import CapturedPiecesWidget

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

        # Captured pieces — same order as Analyze: black above board, white below.
        self._captured_black = CapturedPiecesWidget(side="black")
        layout.addWidget(self._captured_black)

        self._board_widget = BoardWidget()
        self._board_widget.board = self._board
        self._board_widget.update_board()
        # Catch mouse events on the SVG surface for click / painted drag.
        self._board_widget.svg_widget.installEventFilter(self)
        self._board_widget.svg_widget.setMouseTracking(True)  # Hover for legal-move highlights
        # Transparent overlay that paints the dragged piece at the mouse
        # position (chessx approach — no QDrag, no X11 pixmap issues).
        self._drag_overlay = _DragOverlay(self._board_widget.board_container)
        self._drag_overlay.setGeometry(
            0, 0,
            self._board_widget.board_container.width(),
            self._board_widget.board_container.height(),
        )
        self._drag_overlay.raise_()

        # Transparent overlay for legal-move dots and best-move indicator.
        self._legal_moves_overlay = _LegalMovesOverlay(
            self._board_widget.board_container
        )
        self._legal_moves_overlay.setGeometry(
            0, 0,
            self._board_widget.board_container.width(),
            self._board_widget.board_container.height(),
        )
        self._legal_moves_overlay.stackUnder(self._drag_overlay)

        layout.addWidget(self._board_widget, 1)

        # White captured pieces below the board (black pieces White took).
        self._captured_white = CapturedPiecesWidget(side="white")
        layout.addWidget(self._captured_white)

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
        """Right column: Eraser + Pieces palette, mode selector,
        FEN field, help text, and action buttons.

        Mirroring how AnalysisPanel holds the Load Game / Analyze Game
        buttons in the Analyze tab.
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

        # ── Eraser button ──
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
        layout.addWidget(eraser_btn)

        # ── Pieces palette ──
        layout.addWidget(self._build_palette())

        # ── Editor Mode ──
        mode_lbl = QLabel("Editing Mode")
        mode_lbl.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: 600; "
            f"font-size: 12px; border: none;"
        )
        layout.addWidget(mode_lbl)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Free", "Legal Moves", "Best Move"])
        self._mode_combo.setCurrentIndex(0)
        self._mode_combo.setStyleSheet(
            f"QComboBox {{ background-color: {Styles.COLOR_SURFACE_LIGHT}; "
            f"color: {Styles.COLOR_TEXT_PRIMARY}; border: 1px solid "
            f"{Styles.COLOR_BORDER}; border-radius: 6px; padding: 6px 10px; "
            f"font-size: 12px; }}"
            f"QComboBox:hover {{ border-color: {Styles.COLOR_BORDER_LIGHT}; }}"
            f"QComboBox::drop-down {{ subcontrol-origin: padding; "
            f"subcontrol-position: top right; width: 20px; "
            f"border-left: 1px solid {Styles.COLOR_BORDER}; }}"
            f"QComboBox QAbstractItemView {{ "
            f"background-color: {Styles.COLOR_SURFACE}; "
            f"color: {Styles.COLOR_TEXT_PRIMARY}; "
            f"selection-background-color: {Styles.COLOR_ACCENT_SUBTLE}; "
            f"border: 1px solid {Styles.COLOR_BORDER}; }}"
        )
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(self._mode_combo)

        # ── FEN field ──
        fen_lbl = QLabel("FEN")
        fen_lbl.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_PRIMARY}; font-weight: 600; "
            f"font-size: 12px; border: none;"
        )
        layout.addWidget(fen_lbl)
        self._fen_edit = QLineEdit()
        self._fen_edit.setPlaceholderText("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        self._fen_edit.setStyleSheet(
            f"QLineEdit {{ background-color: {Styles.COLOR_SURFACE_LIGHT}; "
            f"color: {Styles.COLOR_TEXT_PRIMARY}; border: 1px solid "
            f"{Styles.COLOR_BORDER}; border-radius: 6px; padding: 6px; "
            f"font-family: 'Consolas','Menlo',monospace; font-size: 11px; }}"
        )
        self._fen_edit.returnPressed.connect(self._load_fen_from_field)
        layout.addWidget(self._fen_edit)

        # ── Help text ──
        help_text = QLabel(
            "Pick a piece on the right, then click a square to place it.\n"
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
    # Move recording (Legal Moves / Best Move modes)
    # ------------------------------------------------------------------
    def _start_recording(self) -> None:
        """Begin tracking moves made via board.push()."""
        self._move_history.clear()
        self._starting_fen = self._board.fen()
        self._last_move_time = time.time()
        self._is_recording = True

    def _stop_recording(self) -> None:
        """Stop tracking and clear accumulated moves."""
        self._is_recording = False
        self._move_history.clear()
        self._starting_fen = ""

    def _record_move(self, san: str, uci: str, fen_before: str) -> None:
        """Append a move to the history with time_spent computed from
        the timestamp of the previous move."""
        now = time.time()
        time_spent = now - self._last_move_time if self._move_history else 0.0
        self._last_move_time = now
        ply = len(self._move_history)
        self._move_history.append({
            "ply": ply,
            "move_number": ply // 2 + 1,
            "san": san,
            "uci": uci,
            "fen_before": fen_before,
            "time_spent": time_spent,
        })

    def _refresh_move_table(self) -> None:
        """Rebuild the move list table from _move_history."""
        if not hasattr(self, "_move_table"):
            return
        table = self._move_table
        table.setRowCount(0)

        if not self._is_recording or not self._move_history:
            return

        num_rows = (len(self._move_history) + 1) // 2
        table.setRowCount(num_rows)

        for i, move in enumerate(self._move_history):
            row = i // 2
            col = (i % 2) + 1  # 1=White, 2=Black

            if col == 1:
                num_item = QTableWidgetItem(str(move["move_number"]))
                num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                num_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                num_item.setForeground(QBrush(QColor(Styles.COLOR_TEXT_SECONDARY)))
                table.setItem(row, 0, num_item)

            # Build a cell widget with SAN + time_spent
            cell = QWidget()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(2, 2, 2, 2)
            cell_layout.setSpacing(1)

            san_lbl = QLabel(move["san"])
            san_lbl.setStyleSheet(
                f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 12px; "
                f"background: transparent;"
            )
            san_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell_layout.addWidget(san_lbl)

            t = move["time_spent"]
            time_lbl = QLabel(f"{t:.1f}s" if t < 60 else f"{int(t // 60)}:{t % 60:04.1f}")
            time_lbl.setStyleSheet(
                "color: rgba(255,255,255,120); font-size: 9px; background: transparent;"
            )
            time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell_layout.addWidget(time_lbl)

            # Backing item for selection
            item = QTableWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, i)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item.setSizeHint(QSize(80, 36))
            table.setItem(row, col, item)
            table.setCellWidget(row, col, cell)

    def _build_game_analysis(self) -> GameAnalysis | None:
        """Build a GameAnalysis from the recorded moves.

        Returns None if no moves were recorded.
        """
        if not self._move_history:
            return None
        # Derive player names from the starting FEN
        board = chess.Board(self._starting_fen)
        white = "White" if board.turn == chess.WHITE else "?"
        black = "Black" if board.turn == chess.WHITE else "?"
        moves = []
        tmp = chess.Board(self._starting_fen)
        for m in self._move_history:
            try:
                move_obj = chess.Move.from_uci(m["uci"])
            except (ValueError, chess.InvalidMoveError):
                continue
            if move_obj not in tmp.legal_moves:
                continue
            ma = MoveAnalysis(
                move_number=m["move_number"],
                ply=m["ply"],
                san=tmp.san(move_obj),
                uci=m["uci"],
                fen_before=m["fen_before"],
                time_spent=m["time_spent"],
            )
            moves.append(ma)
            tmp.push(move_obj)
        return GameAnalysis(
            game_id=f"editor_{int(time.time())}",
            metadata=GameMetadata(white=white, black=black),
            moves=moves,
        )

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def _on_mode_changed(self, index: int) -> None:
        """Called when the user switches the editing mode ComboBox."""
        mode_map = {
            0: EditorMode.FREE,
            1: EditorMode.LEGAL_MOVES,
            2: EditorMode.BEST_MOVE,
        }
        new_mode = mode_map.get(index, EditorMode.FREE)
        self.editor_mode = new_mode

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
        self._clear_highlights()
        self._refresh_squares()
        self._sync_fen_field()

    def _remove_piece_at(self, square: int) -> None:
        self._board.remove_piece_at(square)
        self._board.turn = chess.WHITE
        self._board.castling_rights = 0
        self._board.ep_square = None
        self._board.clear_stack()
        self._clear_highlights()
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
        self._clear_highlights()
        self._refresh_squares()
        self._sync_fen_field()

    def _clear_board(self) -> None:
        # Same in-place mutation as ``_reset_position`` above — see
        # the comment there for why we cannot just rebind
        # ``self._board`` here.
        self._board.set_fen("8/8/8/8/8/8/8/8 w - - 0 1")
        self._clear_highlights()
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
        self._clear_highlights()
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
        self._update_captured()

    # ------------------------------------------------------------------
    # Captured pieces
    # ------------------------------------------------------------------
    def _update_captured(self) -> None:
        """Sync captured pieces widgets with the current position."""
        fen = self._board.fen()
        if hasattr(self, "_captured_black"):
            self._captured_black.update_captured(fen)
        if hasattr(self, "_captured_white"):
            self._captured_white.update_captured(fen)

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

            # Hover: show legal-move / best-move highlights when not
            # dragging and not in Free mode.
            if self._editor_mode != EditorMode.FREE:
                self._on_hover_square(square)
            else:
                if self._hovered_square >= 0:
                    self._clear_highlights()

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

        # Put piece back on source first — _is_move_allowed needs the
        # piece on the board for is_legal() to work.
        self._board.set_piece_at(source, piece)

        if target >= 0 and target != source and self._is_move_allowed(source, target):
            if self._editor_mode != EditorMode.FREE:
                # Legal / Best Move: push() handles castling, ep, turn.
                try:
                    move = chess.Move(source, target)
                    fen_before = self._board.fen()
                    san = self._board.san(move)
                    self._board.push(move)
                    if self._is_recording:
                        self._record_move(san, move.uci(), fen_before)
                        self._refresh_move_table()
                except (ValueError, AssertionError):
                    pass
            else:
                # Free mode: simple placement, no rules.
                self._board.remove_piece_at(source)
                self._board.set_piece_at(target, piece)
                self._board.turn = chess.WHITE
                self._board.castling_rights = 0
                self._board.ep_square = None
                self._board.clear_stack()

        self._clear_highlights()
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

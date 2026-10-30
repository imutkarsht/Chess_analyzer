"""The single chess board widget used by every page.

Page differences — interactivity, overlays, eval bar, themes — are expressed with
:class:`BoardConfig`. Pages instantiate ``Board`` with a config and connect its
signals; they never subclass it or re-implement its interaction handling.
"""

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Literal

import chess
from defusedxml.ElementTree import fromstring as safe_fromstring
from PyQt6.QtCore import QByteArray, QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import QDialog, QGridLayout, QLabel, QSizePolicy, QWidget

from src.constants import DEFAULT_BOARD_THEME
from src.utils.logger import logger

from ..styles import Styles
from .eval_bar import EvalBarWidget
from .promotion_dialog import PromotionDialog

ClassificationOverlay = Literal["none", "game_move", "last_move"]


@dataclass(frozen=True)
class BoardConfig:
    """Behaviour switches for one board instance.

    These describe the board's *initial* state and its rendering policy. Runtime
    methods (``load_game``, ``set_interactive``) still override state as the page
    drives the session.
    """

    # Interaction
    interactive: bool = True
    drag_and_drop: bool = True
    click_to_move: bool = True
    show_legal_moves: bool = True

    # Appearance. None follows the global setting; an explicit bool pins it.
    show_coordinates: bool | None = None
    show_last_move: bool | None = None
    show_eval_bar: bool | None = None
    board_theme: str | None = None
    piece_theme: str | None = None

    # Analysis annotations
    show_best_move_arrow: bool | None = None
    # "game_move" draws the classification of the move being replayed; "last_move"
    # draws the badge for the move just played (live exploration).
    classification_overlay: ClassificationOverlay = "game_move"
    # None follows the global setting; an explicit bool pins the overlay on or off.
    show_classification_overlay: bool | None = None

    # Rules
    chess960: bool = False


class Board(QWidget):
    """Interactive chess board with playback, annotation and free-play modes."""

    move_made = pyqtSignal(str)  # Emits board FEN after any move is played
    board_side_changed = pyqtSignal(int)  # Emits the rendered square board size

    def __init__(self, config: BoardConfig | None = None, parent=None):
        super().__init__(parent)
        self.config = config or BoardConfig()

        self.board = chess.Board(chess960=self.config.chess960)
        self.is_flipped = False  # False = White bottom, True = Black bottom
        self.is_chess960 = self.config.chess960
        self._last_board_side = 0

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.svg_widget = QSvgWidget()

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
        # Clicks belong to the SVG layer underneath.
        self.overlay_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.overlay_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.overlay_layout = QGridLayout(self.overlay_widget)
        self.overlay_layout.setContentsMargins(0, 0, 0, 0)
        self.overlay_layout.setSpacing(0)

        self.board_layout.addWidget(self.overlay_widget, 0, 0)

        # Replay state
        self.current_move_index = -1
        self.game_moves = []

        # Interactive play state
        self.interactive = self.config.interactive
        self.show_legal_moves = self.config.show_legal_moves
        self.selected_square = None
        self.legal_destinations = []

        # Analysis annotations
        self.best_move_uci = None
        self.dimmed = False
        self.last_move_classification = None
        # Resolved from BoardConfig + the global appearance settings in update_board().
        self._show_coordinates = True
        self._show_classification = True
        self._show_last_move = True
        self._show_best_move_arrow = True
        self._show_eval_bar = True
        # Hosts (analysis page, explorer) decide when the bar is meaningful;
        # the setting only controls whether it may appear at all.
        self._eval_bar_host_visible = True

        # Drag and drop floating piece visual
        self.drag_piece_label = QLabel(self.board_container)
        self.drag_piece_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.drag_piece_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.drag_piece_label.setStyleSheet(Styles.get_transparent_label_style())
        self.drag_piece_label.hide()
        self.is_dragging = False
        self.drag_start_sq = None
        self.drag_start_pos = None

        # Intercept mouse events on the SVG layer
        self.svg_widget.installEventFilter(self)

        self.update_board()

    def showEvent(self, event):
        """Position eval_bar and board_container the first time we appear."""
        super().showEvent(event)
        self._enforce_square_board()

    def resizeEvent(self, event):
        """Keep the chessboard square and align the eval bar to its height."""
        super().resizeEvent(event)
        self._enforce_square_board()

    def _enforce_square_board(self):
        eval_visible = hasattr(self, "eval_bar") and self.eval_bar.isVisible()
        eval_w = self.eval_bar.width() if eval_visible else 0
        gap = 6 if eval_visible else 0
        total_eval_space = eval_w + gap
        avail_w = max(0, self.width() - total_eval_space)
        avail_h = self.height()
        if avail_w <= 0 or avail_h <= 0:
            return
        side = min(avail_w, avail_h)
        if side <= 0:
            return
        x_board = total_eval_space + (avail_w - side) // 2
        y_board = (avail_h - side) // 2
        self.board_container.setGeometry(x_board, y_board, side, side)
        if eval_visible:
            self.eval_bar.setGeometry(max(0, x_board - eval_w - gap), y_board, eval_w, side)

        margin = int(side * 15 / 390)
        self.overlay_layout.setContentsMargins(margin, margin, margin, margin)
        if side != self._last_board_side:
            self._last_board_side = side
            self.board_side_changed.emit(side)

    # ------------------------------------------------------------------ Mouse & Move Interactions
    def eventFilter(self, obj, event):
        if obj is self.svg_widget and self.interactive:
            if (
                event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
            ):
                self.handle_press(event.position().x(), event.position().y())
                return True
            elif event.type() == QEvent.Type.MouseMove:
                if self.is_dragging or (event.buttons() & Qt.MouseButton.LeftButton):
                    self.handle_move(event.position().x(), event.position().y())
                    return True
            elif (
                event.type() == QEvent.Type.MouseButtonRelease
                and event.button() == Qt.MouseButton.LeftButton
            ):
                self.handle_release(event.position().x(), event.position().y())
                return True
        return super().eventFilter(obj, event)

    def handle_press(self, x, y):
        sq = self._get_square_from_coords(x, y)
        if sq is None:
            return

        piece = self.board.piece_at(sq)

        # Start drag or select if it's our piece
        if piece and piece.color == self.board.turn:
            self.selected_square = sq
            self.legal_destinations = [
                m.to_square for m in self.board.legal_moves if m.from_square == sq
            ]
            self.drag_start_sq = sq
            self.drag_start_pos = (x, y)
            self.is_dragging = False
            self.draw_interactive_overlays()
        else:
            # Click to move
            if (
                self.config.click_to_move
                and self.selected_square is not None
                and sq in self.legal_destinations
            ):
                self.attempt_move(self.selected_square, sq)
            else:
                self.selected_square = None
                self.legal_destinations = []
                self.draw_interactive_overlays()

    def handle_move(self, x, y):
        if not self.config.drag_and_drop or self.drag_start_pos is None:
            return

        if not self.is_dragging:
            dx = x - self.drag_start_pos[0]
            dy = y - self.drag_start_pos[1]
            if dx * dx + dy * dy > 25:  # 5px threshold
                self.is_dragging = True
                self._start_drag_visuals()

        if self.is_dragging:
            sq_size = self.svg_widget.width() / 8
            self.drag_piece_label.resize(int(sq_size), int(sq_size))
            self.drag_piece_label.move(int(x - sq_size / 2), int(y - sq_size / 2))

    def handle_release(self, x, y):
        if self.is_dragging:
            self.is_dragging = False
            self.drag_piece_label.hide()

            sq = self._get_square_from_coords(x, y)
            if sq is not None and sq in self.legal_destinations:
                self.attempt_move(self.drag_start_sq, sq)
                self.drag_start_pos = None
                return

            # Snap back, restore piece visual
            self.update_board()
            self.draw_interactive_overlays()

        self.drag_start_pos = None

    def _start_drag_visuals(self):
        from src.gui.board.piece_themes import _load_theme_cached, get_current_theme_name

        piece = self.board.piece_at(self.drag_start_sq)
        if not piece:
            return

        pieces = _load_theme_cached(get_current_theme_name())
        g_content = pieces.get(piece.symbol(), "")
        svg_str = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 45">{g_content}</svg>'

        sq_size = self.svg_widget.width() / 8
        renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
        pixmap = QPixmap(int(sq_size), int(sq_size))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        self.drag_piece_label.setPixmap(pixmap)
        self.drag_piece_label.setScaledContents(True)

        # Hide original piece temporarily and re-render board
        self.board.remove_piece_at(self.drag_start_sq)
        try:
            self.update_board()
        finally:
            self.board.set_piece_at(self.drag_start_sq, piece)

        self.drag_piece_label.show()
        self.drag_piece_label.raise_()

    def _get_square_from_coords(self, x, y):
        svg_w = self.svg_widget.width()
        svg_h = self.svg_widget.height()
        if svg_w <= 0 or svg_h <= 0:
            return None

        scale = svg_w / 390.0
        svg_x = x / scale
        svg_y = y / scale

        margin = 15
        square = 45
        if svg_x < margin or svg_x > 375 or svg_y < margin or svg_y > 375:
            return None

        file_click = int((svg_x - margin) // square)
        rank_click = int((svg_y - margin) // square)

        if not self.is_flipped:
            file_idx = file_click
            rank_idx = 7 - rank_click
        else:
            file_idx = 7 - file_click
            rank_idx = rank_click

        if 0 <= file_idx <= 7 and 0 <= rank_idx <= 7:
            return chess.square(file_idx, rank_idx)
        return None

    def attempt_move(self, from_sq, to_sq, promotion=None):
        piece = self.board.piece_at(from_sq)
        is_promo = (
            piece and piece.piece_type == chess.PAWN and chess.square_rank(to_sq) in (0, 7)
        )
        if is_promo and promotion is None:
            dlg = PromotionDialog(piece.color, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                promotion = dlg.selected_piece
            else:
                self.update_board()
                self.draw_interactive_overlays()
                return

        move = chess.Move(from_sq, to_sq, promotion=promotion)
        if move in self.board.legal_moves:
            self.board.push(move)
            self.selected_square = None
            self.legal_destinations = []
            # The engine arrow belongs to the position we just left.
            self.best_move_uci = None
            self.update_board()
            self.draw_interactive_overlays()
            self.move_made.emit(self.board.fen())

    def draw_interactive_overlays(self):
        """Draw selection highlight, legal-move dots and the live classification badge."""
        while self.overlay_layout.count():
            child = self.overlay_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for r in range(8):
            self.overlay_layout.setRowStretch(r, 1)
        for c in range(8):
            self.overlay_layout.setColumnStretch(c, 1)

        # Legal move dots
        if self.show_legal_moves and self.legal_destinations:
            for sq in self.legal_destinations:
                dot = QLabel("●")
                dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
                colour = QColor(Styles.COLOR_ACCENT)
                dot.setStyleSheet(
                    Styles.get_label_style(
                        size=24,
                        color=f"rgba({colour.red()},{colour.green()},{colour.blue()},0.5)",
                    )
                    + " "
                    + Styles.get_transparent_label_style()
                )
                r, col = self._sq_to_grid(sq)
                self.overlay_layout.addWidget(dot, r, col)

        if self._show_classification and self.config.classification_overlay == "last_move":
            self._draw_last_move_badge()

    def _draw_last_move_badge(self):
        if not self.last_move_classification or not self.board.move_stack:
            return

        from src.utils.resources import ResourceManager

        icon = ResourceManager().get_icon(self.last_move_classification)
        if icon.isNull():
            return

        badge = QLabel()
        badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        badge.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        badge.setPixmap(icon.pixmap(32, 32))
        badge.setStyleSheet(Styles.get_transparent_label_style())

        row, col = self._sq_to_grid(self.board.peek().to_square)
        self.overlay_layout.addWidget(
            badge, row, col, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight
        )

    def _sq_to_grid(self, square):
        rank = chess.square_rank(square)
        file = chess.square_file(square)
        if self.is_flipped:
            return rank, 7 - file
        return 7 - rank, file

    # ------------------------------------------------------------------ Historic / Free Position
    def load_fen(self, fen: str, flipped: bool | None = None, *, chess960: bool | None = None):
        """Load a position for free play.

        ``flipped`` and ``chess960`` are tri-state: pass a value to override the
        caller's policy, omit it to keep the current orientation. Omitting
        ``chess960`` resets to standard chess, preserving the historic-analysis
        contract; live exploration always passes it explicitly.
        """
        if flipped is not None:
            self.is_flipped = flipped
        self.is_chess960 = bool(chess960) if chess960 is not None else False
        self.board = chess.Board(fen, chess960=self.is_chess960)
        self.interactive = True
        self.dimmed = False
        self.best_move_uci = None
        self.last_move_classification = None
        self.game_moves = []
        self.current_move_index = -1
        self.selected_square = None
        self.legal_destinations = []
        self.drag_start_sq = None
        self.drag_start_pos = None
        self.is_dragging = False
        self.drag_piece_label.hide()
        self.update_board()
        self.draw_interactive_overlays()

    # ------------------------------------------------------------------ Game Playback
    def load_game(self, game_analysis):
        self.interactive = False
        self.dimmed = False
        self.best_move_uci = None
        self.last_move_classification = None
        # Never inherit the orientation of a historic/free-play FEN.
        self.is_flipped = False
        self.selected_square = None
        self.legal_destinations = []
        self.drag_piece_label.hide()
        self.is_dragging = False
        self.drag_start_pos = None
        self.is_chess960 = game_analysis.metadata.chess960
        self.board = chess.Board(chess960=self.is_chess960)
        self.game_moves = game_analysis.moves
        self.current_move_index = -1
        self.update_board()
        self.draw_overlays(-1)
        self.eval_bar.set_eval(0, None)

    def set_position(self, move_index):
        """
        Sets the board to the position AFTER the move at move_index.
        If move_index is -1, set to initial position.
        """
        self.current_move_index = move_index
        cp = 0.0
        mate = None

        if self.game_moves and move_index >= 0:
            idx = min(move_index, len(self.game_moves) - 1)
            move = self.game_moves[idx]
            # fen_before is cached on every MoveAnalysis, so rebuilding the
            # board from move 0 on every navigation step is unnecessary.
            self.board = chess.Board(move.fen_before, chess960=self.is_chess960)
            self.board.push_uci(move.uci)
            if move_index == idx:
                if move.eval_after_mate is not None:
                    mate = move.eval_after_mate
                elif move.eval_after_cp is not None:
                    cp = move.eval_after_cp
        else:
            start_fen = self.game_moves[0].fen_before if self.game_moves else None
            self.board = (
                chess.Board(start_fen, chess960=self.is_chess960)
                if start_fen
                else chess.Board(chess960=self.is_chess960)
            )

        self.update_board()
        self.draw_overlays(move_index)
        self.eval_bar.set_eval(cp, mate)

    def set_board(self, board: chess.Board):
        """Swap in an externally maintained board, clearing interaction state with it."""
        self.board = board
        self.is_chess960 = board.chess960
        self.selected_square = None
        self.legal_destinations = []
        self.best_move_uci = None
        self.last_move_classification = None
        self.update_board()
        self.draw_interactive_overlays()

    # ------------------------------------------------------------------ Analysis / Variation
    def load_analysis_position(self, fen: str, chess960: bool = False):
        """
        Load a position for free analysis while keeping the game replay data.

        Unlike ``load_fen`` this never clears ``game_moves``, so leaving the
        analysis position can restore the game with ``set_position``.
        """
        self.board = chess.Board(fen, chess960=chess960)
        self.is_chess960 = chess960
        self.interactive = True
        self.last_move_classification = None
        self.selected_square = None
        self.legal_destinations = []
        self.drag_start_sq = None
        self.drag_start_pos = None
        self.is_dragging = False
        self.drag_piece_label.hide()
        self.update_board()
        self.draw_interactive_overlays()

    def set_interactive(self, enabled: bool):
        self.interactive = enabled

    def set_show_legal_moves(self, enabled: bool):
        self.show_legal_moves = enabled
        self.draw_interactive_overlays()

    def set_best_move(self, uci: str | None):
        """Draw the engine's top move as an arrow over the board."""
        if uci == self.best_move_uci:
            return
        self.best_move_uci = uci
        self.update_board()

    def set_last_move_classification(self, classification: str | None):
        """Show (or clear) the badge for the move just played."""
        self.last_move_classification = classification
        if self.config.classification_overlay == "last_move":
            self.draw_interactive_overlays()

    def set_dimmed(self, dimmed: bool):
        """Visually mark the board as an analysis/variation surface."""
        if self.dimmed == dimmed:
            return
        self.dimmed = dimmed
        self.update_board()
        if dimmed:
            # The game-move classification badges belong to the replayed game,
            # not to the free-analysis position; drop them when entering it.
            self.draw_interactive_overlays()

    def undo_move(self) -> bool:
        """Pop the last move from the board (used by variation exploration)."""
        if not self.board.move_stack:
            return False
        self.board.pop()
        self.selected_square = None
        self.legal_destinations = []
        self.update_board()
        self.draw_interactive_overlays()
        return True

    def flip_board(self):
        self.is_flipped = not self.is_flipped
        self.update_board()
        if self.interactive:
            self.draw_interactive_overlays()
        else:
            self.draw_overlays(self.current_move_index)

    def draw_overlays(self, move_index):
        # Clear existing overlays
        while self.overlay_layout.count():
            child = self.overlay_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self._show_classification:
            return
        if self.dimmed:
            # Variation/free-analysis positions have no game move at this index.
            return
        if self.config.classification_overlay != "game_move":
            return
        if move_index < 0 or move_index >= len(self.game_moves):
            return

        move = self.game_moves[move_index]
        if not move.classification:
            return

        from ...utils.resources import ResourceManager

        icon = ResourceManager().get_icon(move.classification)

        if icon.isNull():
            return

        try:
            to_sq = chess.parse_square(move.uci[2:4])
            row, col = self._sq_to_grid(to_sq)

            lbl = QLabel()
            lbl.setPixmap(icon.pixmap(32, 32))
            lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
            lbl.setStyleSheet(Styles.get_transparent_label_style())

            # Ensure grid is 8x8
            for r in range(8):
                self.overlay_layout.setRowStretch(r, 1)
            for c in range(8):
                self.overlay_layout.setColumnStretch(c, 1)

            self.overlay_layout.addWidget(
                lbl, row, col, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight
            )
        except Exception as e:
            logger.debug(f"Error drawing overlay: {e}")

    def _resolve_display_preferences(self):
        """Resolve appearance prefs: a page override wins, otherwise the user setting."""
        from ...utils.config import ConfigManager

        prefs = ConfigManager()

        def resolve(override: bool | None, key: str, default: bool = True) -> bool:
            return bool(override) if override is not None else bool(prefs.get(key, default))

        self._show_coordinates = resolve(
            self.config.show_coordinates, "board_show_coordinates"
        )
        self._show_classification = resolve(
            self.config.show_classification_overlay, "board_show_classification"
        )
        self._show_last_move = resolve(
            self.config.show_last_move, "board_show_last_move"
        )
        self._show_best_move_arrow = resolve(
            self.config.show_best_move_arrow, "board_show_best_move_arrow"
        )
        self._show_eval_bar = resolve(
            self.config.show_eval_bar, "board_show_eval_bar"
        )

    def set_eval_bar_visible(self, visible: bool) -> None:
        """Tell the board whether its host currently has a position worth showing."""
        self._eval_bar_host_visible = bool(visible)
        self._apply_eval_bar_visibility()

    def _apply_eval_bar_visibility(self) -> None:
        if hasattr(self, "eval_bar"):
            self.eval_bar.setVisible(self._eval_bar_host_visible and self._show_eval_bar)

    def refresh_settings(self):
        """Re-read appearance settings and redraw, clearing any now-hidden overlay."""
        self.update_board()
        if self.interactive:
            self.draw_interactive_overlays()
        else:
            self.draw_overlays(self.current_move_index)

    def update_board(self):
        # Determine colors from configured theme
        from ...utils.config import ConfigManager
        from .piece_themes import get_piece_defs

        self._resolve_display_preferences()
        self._apply_eval_bar_visibility()
        config = ConfigManager()
        board_theme_name = self.config.board_theme or config.get(
            "board_theme", DEFAULT_BOARD_THEME
        )
        piece_theme_name = self.config.piece_theme or config.get("piece_theme", "Standard")
        colors = Styles.get_board_colors(board_theme_name)

        # Get the piece definitions for the selected theme.
        piece_defs = get_piece_defs(piece_theme_name)

        # Generate custom SVG with our piece definitions
        svg_data = self._generate_custom_board_svg(colors, piece_defs)
        try:
            self.svg_widget.load(svg_data)
        except RuntimeError:
            pass

    def _generate_custom_board_svg(self, colors, piece_defs):
        """
        Generate a custom SVG board with the given colors and piece definitions.
        """
        SQUARE_SIZE = 45
        MARGIN = 15
        BOARD_SIZE = 8 * SQUARE_SIZE
        FULL_SIZE = BOARD_SIZE + 2 * MARGIN

        orientation = not self.is_flipped  # True = white at bottom

        # Resolve last move to highlight
        last_move = None
        if self._show_last_move and self.board.move_stack:
            last_move = self.board.move_stack[-1]
        last_from = last_move.from_square if last_move else None
        last_to = last_move.to_square if last_move else None

        # Create SVG root
        svg = ET.Element(
            "svg",
            {
                "xmlns": "http://www.w3.org/2000/svg",
                "xmlns:xlink": "http://www.w3.org/1999/xlink",
                "viewBox": f"0 0 {FULL_SIZE} {FULL_SIZE}",
                "width": str(FULL_SIZE),
                "height": str(FULL_SIZE),
            },
        )

        # Background
        ET.SubElement(
            svg,
            "rect",
            {
                "x": "0",
                "y": "0",
                "width": str(FULL_SIZE),
                "height": str(FULL_SIZE),
                "fill": Styles.COLOR_BACKGROUND,
            },
        )

        defs = ET.SubElement(svg, "defs")
        wrapped = f'<root xmlns="http://www.w3.org/2000/svg">{piece_defs}</root>'
        try:
            wrapper_root = safe_fromstring(wrapped)
            for piece_elem in wrapper_root:
                defs.append(piece_elem)
        except ET.ParseError as e:
            logger.warning(f"Error parsing piece defs: {e}")

        # Draw squares
        for square in chess.SQUARES:
            file_idx = chess.square_file(square)
            rank_idx = chess.square_rank(square)

            if orientation:
                x = MARGIN + file_idx * SQUARE_SIZE
                y = MARGIN + (7 - rank_idx) * SQUARE_SIZE
            else:
                x = MARGIN + (7 - file_idx) * SQUARE_SIZE
                y = MARGIN + rank_idx * SQUARE_SIZE

            is_light = (file_idx + rank_idx) % 2 == 1
            fill_color = colors["light"] if is_light else colors["dark"]

            ET.SubElement(
                svg,
                "rect",
                {
                    "x": str(x),
                    "y": str(y),
                    "width": str(SQUARE_SIZE),
                    "height": str(SQUARE_SIZE),
                    "fill": fill_color,
                },
            )

            # Highlight last move squares
            if last_move and square in (last_from, last_to):
                ET.SubElement(
                    svg,
                    "rect",
                    {
                        "x": str(x),
                        "y": str(y),
                        "width": str(SQUARE_SIZE),
                        "height": str(SQUARE_SIZE),
                        "fill": Styles.COLOR_BOARD_HIGHLIGHT,
                        "opacity": "0.35",
                    },
                )

        # Draw coordinates
        if self._show_coordinates:
            coord_style = (
                f"font-size:10px;fill:{Styles.COLOR_TEXT_SECONDARY};font-family:sans-serif"
            )

            for i in range(8):
                file_letter = chess.FILE_NAMES[i if orientation else 7 - i]
                file_x = MARGIN + i * SQUARE_SIZE + SQUARE_SIZE // 2 - 3
                ET.SubElement(
                    svg,
                    "text",
                    {"x": str(file_x), "y": str(FULL_SIZE - 3), "style": coord_style},
                ).text = file_letter

                rank_number = str(8 - i if orientation else i + 1)
                rank_y = MARGIN + i * SQUARE_SIZE + SQUARE_SIZE // 2 + 4
                ET.SubElement(
                    svg, "text", {"x": "3", "y": str(rank_y), "style": coord_style}
                ).text = rank_number

        # Draw pieces
        for square in chess.SQUARES:
            piece = self.board.piece_at(square)
            if piece:
                file_idx = chess.square_file(square)
                rank_idx = chess.square_rank(square)

                if orientation:
                    x = MARGIN + file_idx * SQUARE_SIZE
                    y = MARGIN + (7 - rank_idx) * SQUARE_SIZE
                else:
                    x = MARGIN + (7 - file_idx) * SQUARE_SIZE
                    y = MARGIN + rank_idx * SQUARE_SIZE

                color_name = "white" if piece.color else "black"
                piece_type_name = chess.PIECE_NAMES[piece.piece_type]
                href = f"#{color_name}-{piece_type_name}"

                ET.SubElement(
                    svg,
                    "use",
                    {"href": href, "xlink:href": href, "transform": f"translate({x}, {y})"},
                )

        # Analysis mode: wash the board out slightly, then keep the arrow vivid
        # on top so the suggested move still reads at a glance.
        if self.dimmed:
            ET.SubElement(
                svg,
                "rect",
                {
                    "x": str(MARGIN),
                    "y": str(MARGIN),
                    "width": str(BOARD_SIZE),
                    "height": str(BOARD_SIZE),
                    "fill": "#000000",
                    "opacity": "0.10",
                },
            )

        if self.best_move_uci and self._show_best_move_arrow:
            self._draw_best_move_arrow(svg, MARGIN, SQUARE_SIZE)

        return ET.tostring(svg, encoding="utf-8")

    def _draw_best_move_arrow(self, svg_root, margin: int, square_size: int):
        """Append the best-move arrow for the current orientation."""
        try:
            from_sq = chess.parse_square(self.best_move_uci[:2])
            to_sq = chess.parse_square(self.best_move_uci[2:4])
        except ValueError:
            logger.warning("Invalid best-move UCI: %s", self.best_move_uci)
            return

        def center(square):
            file_idx = chess.square_file(square)
            rank_idx = chess.square_rank(square)
            if not self.is_flipped:
                return (
                    margin + file_idx * square_size + square_size / 2,
                    margin + (7 - rank_idx) * square_size + square_size / 2,
                )
            return (
                margin + (7 - file_idx) * square_size + square_size / 2,
                margin + rank_idx * square_size + square_size / 2,
            )

        x1, y1 = center(from_sq)
        x2, y2 = center(to_sq)
        self._add_arrow(
            svg_root, x1, y1, x2, y2, color=Styles.COLOR_ACCENT, opacity="0.4", width=14
        )

    def _add_arrow(self, svg_root, x1, y1, x2, y2, color=None, opacity="0.4", width=14):
        """Append an SVG arrow to the root element."""
        color = color or Styles.COLOR_ACCENT
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1:
            return

        # Shorten tail and head slightly so it doesn't cover pieces entirely
        shorten_tail = width * 0.8
        shorten_head = width * 1.8
        ux = dx / length
        uy = dy / length

        sx = x1 + ux * shorten_tail
        sy = y1 + uy * shorten_tail
        ex = x2 - ux * shorten_head
        ey = y2 - uy * shorten_head

        # Arrow head (triangle) - wider and proportional
        arrow_width = width * 1.8
        px = -uy * arrow_width
        py = ux * arrow_width

        points = (
            f"{x2 - ux*width*0.5},{y2 - uy*width*0.5} "
            f"{ex + px},{ey + py} "
            f"{ex - px},{ey - py}"
        )

        ET.SubElement(
            svg_root,
            "line",
            {
                "x1": str(sx),
                "y1": str(sy),
                "x2": str(ex),
                "y2": str(ey),
                "stroke": color,
                "stroke-width": str(width),
                "stroke-linecap": "butt",
                "opacity": opacity,
            },
        )
        ET.SubElement(
            svg_root,
            "polygon",
            {"points": points, "fill": color, "opacity": opacity},
        )

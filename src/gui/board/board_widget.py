import xml.etree.ElementTree as ET

import chess
import chess.svg
from defusedxml.ElementTree import fromstring as safe_fromstring
from PyQt6.QtCore import QByteArray, QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QGuiApplication, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from src.utils.logger import logger

from ..styles import Styles
from .eval_bar import EvalBarWidget


class PromotionDialog(QDialog):
    """Pawn promotion piece picker dialog."""

    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Promote pawn to...")
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.selected_piece = None

        self.setStyleSheet(Styles.get_dialog_surface_style())

        layout = QHBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        from src.gui.board.piece_themes import _load_theme_cached, get_current_theme_name

        pieces_svg = _load_theme_cached(get_current_theme_name())

        piece_map = {
            chess.QUEEN: "Q" if color == chess.WHITE else "q",
            chess.ROOK: "R" if color == chess.WHITE else "r",
            chess.BISHOP: "B" if color == chess.WHITE else "b",
            chess.KNIGHT: "N" if color == chess.WHITE else "n",
        }

        for piece_type, symbol in piece_map.items():
            btn = QPushButton()
            btn.setFixedSize(52, 52)
            g_content = pieces_svg.get(symbol, "")
            if g_content:
                svg_str = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 45">{g_content}</svg>'
                renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
                pixmap = QPixmap(42, 42)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                btn.setIcon(QIcon(pixmap))
                btn.setIconSize(pixmap.size())
            btn.setStyleSheet(Styles.get_icon_button_style())
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, pt=piece_type: self.select_piece(pt))
            layout.addWidget(btn)

        self.adjustSize()
        self._position_at_cursor()

    def _position_at_cursor(self):
        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos)
        if screen:
            sg = screen.geometry()
            x = max(
                sg.x(),
                min(cursor_pos.x() - self.width() // 2, sg.x() + sg.width() - self.width()),
            )
            y = max(
                sg.y(),
                min(cursor_pos.y() - self.height() // 2, sg.y() + sg.height() - self.height()),
            )
            self.move(x, y)
        else:
            self.move(cursor_pos.x() - self.width() // 2, cursor_pos.y() - self.height() // 2)

    def select_piece(self, piece_type):
        self.selected_piece = piece_type
        self.accept()


class BoardWidget(QWidget):
    move_made = pyqtSignal(str)  # Emits board FEN after any move is played

    def __init__(self):
        super().__init__()
        self.board = chess.Board()
        self.is_flipped = False  # False = White bottom, True = Black bottom

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
        self.overlay_widget.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )  # Let clicks pass through
        self.overlay_widget.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )  # Make background transparent
        self.overlay_layout = QGridLayout(self.overlay_widget)
        self.overlay_layout.setContentsMargins(0, 0, 0, 0)
        self.overlay_layout.setSpacing(0)

        self.board_layout.addWidget(self.overlay_widget, 0, 0)

        self.current_move_index = -1
        self.game_moves = []
        self.is_chess960 = False

        # Interactive play state (active on empty board when no game is loaded)
        self.interactive = True
        self.show_legal_moves = True
        self.selected_square = None
        self.legal_destinations = []

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
            if self.selected_square is not None and sq in self.legal_destinations:
                self.attempt_move(self.selected_square, sq)
            else:
                self.selected_square = None
                self.legal_destinations = []
                self.draw_interactive_overlays()

    def handle_move(self, x, y):
        if self.drag_start_pos is None:
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

        MARGIN = 15
        SQ = 45
        if svg_x < MARGIN or svg_x > 375 or svg_y < MARGIN or svg_y > 375:
            return None

        file_click = int((svg_x - MARGIN) // SQ)
        rank_click = int((svg_y - MARGIN) // SQ)

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
            piece
            and piece.piece_type == chess.PAWN
            and chess.square_rank(to_sq) in (0, 7)
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
            self.update_board()
            self.draw_interactive_overlays()
            self.move_made.emit(self.board.fen())

    def draw_interactive_overlays(self):
        """Draw selection highlight and legal-move dots."""
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
                c = QColor(Styles.COLOR_ACCENT)
                dot.setStyleSheet(
                    Styles.get_label_style(
                        size=24, color=f"rgba({c.red()},{c.green()},{c.blue()},0.5)"
                    )
                    + " "
                    + Styles.get_transparent_label_style()
                )
                r, col = self._sq_to_grid(sq)
                self.overlay_layout.addWidget(dot, r, col)

    def _sq_to_grid(self, square):
        rank = chess.square_rank(square)
        file = chess.square_file(square)
        if self.is_flipped:
            return rank, 7 - file
        return 7 - rank, file

    # ------------------------------------------------------------------ Historic / Free Position
    def load_fen(self, fen: str, flipped: bool = False):
        """Load a custom FEN for free-play exploration (landing page historic mode)."""
        self.interactive = True
        self.is_flipped = flipped
        self.board = chess.Board(fen)
        self.game_moves = []
        self.current_move_index = -1
        self.is_chess960 = False
        self.selected_square = None
        self.legal_destinations = []
        self.drag_start_sq = None
        self.drag_start_pos = None
        self.is_dragging = False
        if hasattr(self, "drag_piece_label"):
            self.drag_piece_label.hide()
        self.update_board()
        self.draw_interactive_overlays()

    # ------------------------------------------------------------------ Game Playback
    def load_game(self, game_analysis):
        self.interactive = False
        self.selected_square = None
        self.legal_destinations = []
        if hasattr(self, "drag_piece_label"):
            self.drag_piece_label.hide()
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
        if self.game_moves:
            self.board = chess.Board(self.game_moves[0].fen_before, chess960=self.is_chess960)
        else:
            self.board = chess.Board(chess960=self.is_chess960)

        cp = 0.0
        mate = None

        # Replay moves
        for i in range(move_index + 1):
            if i < len(self.game_moves):
                move = self.game_moves[i]
                self.board.push_uci(move.uci)

                if i == move_index:
                    if move.eval_after_mate is not None:
                        mate = move.eval_after_mate
                    elif move.eval_after_cp is not None:
                        cp = move.eval_after_cp

        self.update_board()
        self.draw_overlays(move_index)
        self.eval_bar.set_eval(cp, mate)

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

    def update_board(self):
        # Determine colors from configured theme
        from ...utils.config import ConfigManager
        from .piece_themes import get_piece_defs

        config = ConfigManager()
        board_theme_name = config.get("board_theme", "Green")
        piece_theme_name = config.get("piece_theme", "Standard")
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
        last_move = self.board.move_stack[-1] if self.board.move_stack else None
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
        coord_style = f"font-size:10px;fill:{Styles.COLOR_TEXT_SECONDARY};font-family:sans-serif"

        for i in range(8):
            file_letter = chess.FILE_NAMES[i if orientation else 7 - i]
            file_x = MARGIN + i * SQUARE_SIZE + SQUARE_SIZE // 2 - 3
            ET.SubElement(
                svg, "text", {"x": str(file_x), "y": str(FULL_SIZE - 3), "style": coord_style}
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

        return ET.tostring(svg, encoding="utf-8")

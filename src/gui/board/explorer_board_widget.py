"""
Explorer Board Widget - Interactive chessboard for the Opening Explorer.
Extends BoardWidget with click-to-move, best-move arrows, and book move overlays.
"""
import chess
from PyQt6.QtCore import QByteArray, QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton

from src.gui.board.board_widget import BoardWidget
from src.gui.styles import Styles


class PromotionDialog(QDialog):
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
            chess.QUEEN:  'Q' if color == chess.WHITE else 'q',
            chess.ROOK:   'R' if color == chess.WHITE else 'r',
            chess.BISHOP: 'B' if color == chess.WHITE else 'b',
            chess.KNIGHT: 'N' if color == chess.WHITE else 'n',
        }

        for piece_type, symbol in piece_map.items():
            btn = QPushButton()
            btn.setFixedSize(52, 52)
            g_content = pieces_svg.get(symbol, "")
            if g_content:
                svg_str = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 45">{g_content}</svg>'
                renderer = QSvgRenderer(QByteArray(svg_str.encode('utf-8')))
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
        from PyQt6.QtGui import QCursor, QGuiApplication
        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos)
        if screen:
            sg = screen.geometry()
            x = max(sg.x(), min(cursor_pos.x() - self.width() // 2, sg.x() + sg.width() - self.width()))
            y = max(sg.y(), min(cursor_pos.y() - self.height() // 2, sg.y() + sg.height() - self.height()))
            self.move(x, y)
        else:
            self.move(cursor_pos.x() - self.width() // 2, cursor_pos.y() - self.height() // 2)

    def select_piece(self, piece_type):
        self.selected_piece = piece_type
        self.accept()


class ExplorerBoardWidget(BoardWidget):
    """Interactive board for the Opening Explorer with click-to-move support."""

    move_made = pyqtSignal(str)  # emits new FEN

    def __init__(self):
        # Initialize before super().__init__() because BoardWidget.__init__
        # calls update_board() -> _generate_custom_board_svg() which accesses these
        self.best_move_uci = None
        self.show_legal_moves = True
        self.selected_square = None
        self.legal_destinations = []
        self.book_destinations = []
        self.last_move_classification = None

        super().__init__()
        # Attributes that aren't needed during initial board render
        self.selected_square = None
        self.legal_destinations = []

        # Drag and drop state
        self.drag_piece_label = QLabel(self.board_container)
        self.drag_piece_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.drag_piece_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.drag_piece_label.setStyleSheet(Styles.get_transparent_label_style())
        self.drag_piece_label.hide()
        self.is_dragging = False
        self.drag_start_sq = None
        self.drag_start_pos = None

        # Intercept clicks on the SVG layer
        self.svg_widget.installEventFilter(self)

    # ------------------------------------------------------------------ events
    def eventFilter(self, obj, event):
        if obj is self.svg_widget:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self.handle_press(event.position().x(), event.position().y())
                return True
            elif event.type() == QEvent.Type.MouseMove:
                if self.is_dragging or (event.buttons() & Qt.MouseButton.LeftButton):
                    self.handle_move(event.position().x(), event.position().y())
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                self.handle_release(event.position().x(), event.position().y())
                return True
        return super().eventFilter(obj, event)

    def handle_press(self, x, y):
        sq = self._get_square_from_coords(x, y)
        if sq is None:
            return

        piece = self.board.piece_at(sq)

        # Start drag if it's our piece
        if piece and piece.color == self.board.turn:
            self.selected_square = sq
            self.legal_destinations = [m.to_square for m in self.board.legal_moves if m.from_square == sq]
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
            if dx*dx + dy*dy > 25: # 5px threshold
                self.is_dragging = True
                self._start_drag_visuals()

        if self.is_dragging:
            sq_size = self.svg_widget.width() / 8
            self.drag_piece_label.resize(int(sq_size), int(sq_size))
            self.drag_piece_label.move(int(x - sq_size/2), int(y - sq_size/2))

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
        renderer = QSvgRenderer(QByteArray(svg_str.encode('utf-8')))
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

        return chess.square(file_idx, rank_idx)

    # ------------------------------------------------------------------ moves
    def attempt_move(self, from_sq, to_sq, promotion=None):
        piece = self.board.piece_at(from_sq)
        is_promo = (
            piece and piece.piece_type == chess.PAWN and
            chess.square_rank(to_sq) in (0, 7)
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

    # ------------------------------------------------------------------ overlay
    def draw_interactive_overlays(self):
        """Draw selection highlight, legal-move dots, and book-move dots."""
        # Clear
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
                    Styles.get_label_style(size=24, color=f"rgba({c.red()},{c.green()},{c.blue()},0.5)")
                    + " " + Styles.get_transparent_label_style()
                )
                r, c = self._sq_to_grid(sq)
                self.overlay_layout.addWidget(dot, r, c)

        # Draw classification badge on the last move's destination square
        if getattr(self, 'last_move_classification', None) and self.board.move_stack:
            last_move = self.board.peek()
            to_sq = last_move.to_square

            badge = QLabel()
            badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            badge.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

            # Fetch icon
            from src.utils.resources import ResourceManager
            icon = ResourceManager().get_icon(self.last_move_classification)
            if not icon.isNull():
                badge.setPixmap(icon.pixmap(32, 32))

            r, c = self._sq_to_grid(to_sq)
            badge.setStyleSheet(Styles.get_transparent_label_style())
            self.overlay_layout.addWidget(badge, r, c, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

    def _sq_to_grid(self, square):
        rank = chess.square_rank(square)
        file = chess.square_file(square)
        if self.is_flipped:
            return rank, 7 - file
        return 7 - rank, file

    # ------------------------------------------------------------------ public
    def load_fen(self, fen, chess960=False):
        """Load a FEN and reset all selections."""
        self.board = chess.Board(fen, chess960=chess960)
        self.selected_square = None
        self.legal_destinations = []
        self.best_move_uci = None
        self.update_board()
        self.draw_interactive_overlays()

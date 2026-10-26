"""Promotion piece picker shared by every board instance."""

import chess
from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QCursor, QGuiApplication, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QDialog, QHBoxLayout

from src.gui.components import Button, ButtonVariant
from src.gui.styles import Styles


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
            piece_label = chess.piece_name(piece_type).capitalize()
            btn = Button(
                variant=ButtonVariant.FILLED,
                icon_position="only",
                icon_size=42,
                tooltip=f"Promote to {piece_label}",
            )
            btn.setFixedSize(52, 52)
            btn.setAccessibleName(f"Promote to {piece_label}")
            g_content = pieces_svg.get(symbol, "")
            if g_content:
                svg_str = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 45">{g_content}</svg>'
                renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
                pixmap = QPixmap(42, 42)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                btn.set_icon_spec(QIcon(pixmap))
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

"""Visual previews for board and piece themes."""

import xml.etree.ElementTree as ET

from defusedxml.ElementTree import fromstring as safe_fromstring
from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtSvgWidgets import QSvgWidget

from ...board.piece_themes import get_piece_defs
from ...styles import Styles


def _svg_with_pieces(
    board_theme: str,
    piece_theme: str,
    squares: int,
    placements: list[tuple[str, int, int]],
) -> bytes:
    square = 45
    size = squares * square
    colors = Styles.get_board_colors(board_theme)
    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "xmlns:xlink": "http://www.w3.org/1999/xlink",
            "viewBox": f"0 0 {size} {size}",
            "width": str(size),
            "height": str(size),
        },
    )
    defs = ET.SubElement(svg, "defs")
    wrapped = f'<root xmlns="http://www.w3.org/2000/svg">{get_piece_defs(piece_theme)}</root>'
    try:
        for element in safe_fromstring(wrapped):
            defs.append(element)
    except ET.ParseError:
        pass

    for row in range(squares):
        for column in range(squares):
            fill = colors["light"] if (row + column) % 2 == 0 else colors["dark"]
            ET.SubElement(
                svg,
                "rect",
                {
                    "x": str(column * square),
                    "y": str(row * square),
                    "width": str(square),
                    "height": str(square),
                    "fill": fill,
                },
            )

    for symbol, column, row in placements:
        href = f"#{symbol}"
        ET.SubElement(
            svg,
            "use",
            {
                "href": href,
                "xlink:href": href,
                "transform": f"translate({column * square}, {row * square})",
            },
        )
    return ET.tostring(svg, encoding="utf-8")


def board_swatch(theme_name: str, size: int = 64) -> QPixmap:
    """A checkerboard swatch for a board theme."""
    colors = Styles.get_board_colors(theme_name)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    cell = size / 4
    for row in range(4):
        for column in range(4):
            color = colors["light"] if (row + column) % 2 == 0 else colors["dark"]
            painter.fillRect(
                int(column * cell),
                int(row * cell),
                int(cell) + 1,
                int(cell) + 1,
                QColor(color),
            )
    painter.end()
    return pixmap


def piece_theme_preview(
    piece_theme: str,
    board_theme: str = "Green",
    size: int = 96,
) -> QPixmap:
    """A 2x2 board preview showing four pieces from a theme."""
    svg = _svg_with_pieces(
        board_theme,
        piece_theme,
        squares=2,
        placements=[
            ("white-king", 0, 0),
            ("black-queen", 1, 0),
            ("white-knight", 0, 1),
            ("black-pawn", 1, 1),
        ],
    )
    renderer = QSvgRenderer(QByteArray(svg))
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    return QPixmap.fromImage(image)


class BoardThemePreview(QSvgWidget):
    """Live 4x4 board preview for the selected board and piece themes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(QSize(220, 220))
        self.setMaximumSize(QSize(220, 220))
        self._board_theme = "Green"
        self._piece_theme = "Standard"
        self.refresh()

    def set_themes(self, board_theme: str, piece_theme: str) -> None:
        self._board_theme = board_theme
        self._piece_theme = piece_theme
        self.refresh()

    def refresh(self) -> None:
        svg = _svg_with_pieces(
            self._board_theme,
            self._piece_theme,
            squares=4,
            placements=[
                ("black-rook", 0, 0),
                ("black-knight", 1, 0),
                ("black-bishop", 2, 0),
                ("black-queen", 3, 0),
                ("white-rook", 0, 3),
                ("white-knight", 1, 3),
                ("white-bishop", 2, 3),
                ("white-queen", 3, 3),
            ],
        )
        self.load(QByteArray(svg))

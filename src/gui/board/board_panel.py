"""Board area with the captured-piece and clock rows hugging the board."""

from PyQt6.QtWidgets import QSizePolicy, QWidget

NORMAL_ROW_H = 44
COMPACT_ROW_H = 36
ROW_GAP = 4


class BoardPanel(QWidget):
    """Lay out the board between its two captured-piece/clock rows.

    ``Board`` centers a square board inside a possibly wider/taller
    rectangle.  Placing the rows in the outer layout therefore left a large
    dead gap whenever the board was width- or height-limited.  This container
    positions the rows against the board's actual geometry instead.
    """

    def __init__(self, board_widget, white_row, black_row, parent=None):
        super().__init__(parent)
        self.board_widget = board_widget
        self.white_row = white_row
        self.black_row = black_row
        self._flipped = False
        self._compact = False
        self.row_height = NORMAL_ROW_H
        self._laying_out = False

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        for widget in (board_widget, white_row, black_row):
            widget.setParent(self)
            widget.show()
        self.board_widget.board_side_changed.connect(self._on_board_side_changed)

    def set_compact(self, compact: bool) -> None:
        if compact == self._compact:
            return
        self._compact = compact
        self.row_height = COMPACT_ROW_H if compact else NORMAL_ROW_H
        self.white_row.set_compact(compact)
        self.black_row.set_compact(compact)
        self._layout_children()

    def set_flipped(self, flipped: bool) -> None:
        self._flipped = flipped
        self._layout_children()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_children()

    def showEvent(self, event):
        super().showEvent(event)
        self._layout_children()

    def _on_board_side_changed(self, _side: int) -> None:
        self._layout_children()

    def _layout_children(self) -> None:
        if self._laying_out:
            return
        self._laying_out = True
        try:
            width = max(0, self.width())
            height = max(0, self.height())
            row_h = self.row_height
            board_height = max(0, height - 2 * (row_h + ROW_GAP))
            if width <= 0 or board_height <= 0:
                return

            self.board_widget.setGeometry(0, row_h + ROW_GAP, width, board_height)
            # Keep the board square calculation in sync before reading the
            # rendered board rectangle.  The side-change signal may fire here,
            # but the guard above prevents recursion.
            self.board_widget._enforce_square_board()

            side = self.board_widget.board_container.width()
            if side <= 0:
                return
            board_x = self.board_widget.board_container.x()
            board_y = (
                self.board_widget.y() + self.board_widget.board_container.y()
            )

            if self._flipped:
                top_row, bottom_row = self.white_row, self.black_row
            else:
                top_row, bottom_row = self.black_row, self.white_row

            top_row.setGeometry(
                board_x, max(0, board_y - ROW_GAP - row_h), side, row_h
            )
            bottom_row.setGeometry(board_x, board_y + side + ROW_GAP, side, row_h)
            top_row.raise_()
            bottom_row.raise_()
        finally:
            self._laying_out = False

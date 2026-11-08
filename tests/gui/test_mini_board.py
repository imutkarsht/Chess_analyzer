"""Shared mini-board rendering and geometry."""

import chess
from PyQt6.QtGui import QImage

from src.gui.board import (
    MiniBoardConfig,
    MiniBoardWidget,
    render_mini_board_pixmap,
)

_AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


def _image(fen: str, **config) -> QImage:
    return render_mini_board_pixmap(
        fen, MiniBoardConfig(size=72, **config)
    ).toImage()


def test_last_move_highlight_and_orientation_change_the_render(qapp):
    plain = _image(_AFTER_E4)
    highlighted = _image(_AFTER_E4, last_move_uci="e2e4")
    flipped = _image(
        _AFTER_E4,
        last_move_uci="e2e4",
        orientation=chess.BLACK,
    )

    assert not plain.isNull()
    assert plain.size().width() == 72
    assert highlighted != plain
    assert flipped != highlighted


def test_pre_move_fen_advances_to_the_same_position(qapp):
    advanced = _image(
        chess.STARTING_FEN,
        last_move_uci="e2e4",
        fen_before_move=True,
    )
    final = _image(_AFTER_E4, last_move_uci="e2e4")

    assert advanced == final


def test_invalid_fen_returns_a_null_pixmap(qapp):
    pixmap = render_mini_board_pixmap("not a fen")

    assert pixmap.isNull()


def test_chess960_position_renders(qapp):
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w HAha - 0 1"

    pixmap = render_mini_board_pixmap(
        fen, MiniBoardConfig(size=72, chess960=True)
    )

    assert not pixmap.isNull()


def test_widget_geometry_includes_padding_and_border(qapp, qtbot):
    widget = MiniBoardWidget(
        chess.STARTING_FEN,
        MiniBoardConfig(size=100, padding=1, border_width=1),
    )
    qtbot.addWidget(widget)

    assert widget.width() == 104
    assert widget.height() == 104

    widget.set_config(
        MiniBoardConfig(size=80, show_border=False, border_radius=0)
    )
    assert widget.width() == 80
    assert widget.config.size == 80

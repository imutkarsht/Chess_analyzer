"""Shared engine-lines widget: stable rows, content height, click contract."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel

from src.backend.analysis.engine_line import EngineLine
from src.gui.engine_lines import EngineLinesConfig, EngineLinesWidget
from src.gui.engine_lines.widget import EngineLineRow


def _widget(qtbot, **overrides):
    config = EngineLinesConfig(
        visible_lines=2,
        row_height=40,
        row_spacing=4,
        max_lines=3,
        empty_text="Enable Engine Lines",
        **overrides,
    )
    widget = EngineLinesWidget(config)
    qtbot.addWidget(widget)
    widget.show()
    return widget


def _line(rank=1, cp=104, pv=("b3b4", "a7a5"), san="12. Qb3 a5") -> EngineLine:
    return EngineLine(rank=rank, depth=17, cp=cp, pv_uci=pv, pv_san=san)


def test_panel_shrinks_to_a_single_row_when_empty(qtbot):
    widget = _widget(qtbot)

    assert widget.height() == 40 + 16
    assert widget.minimumHeight() == widget.maximumHeight()


def test_panel_grows_to_the_lines_it_shows_and_scrolls_beyond_the_cap(qtbot):
    widget = _widget(qtbot)

    widget.set_lines([_line()])
    assert widget.height() == 40 + 16

    widget.set_lines([_line(1), _line(2, 57, ("e1g1",), "12. O-O")])
    assert widget.height() == 2 * 40 + 4 + 16

    # The row pool is fixed; a fourth line is clipped instead of adding widgets.
    widget.set_lines([_line(1), _line(2), _line(3), _line(4)])
    assert len(widget.findChildren(EngineLineRow)) == 3
    assert len(widget.lines) == 3


def test_click_emits_the_first_move_of_the_row(qtbot):
    widget = _widget(qtbot)
    widget.set_lines([_line(), _line(2, 57, ("e1g1",), "12. O-O")])
    clicked = []
    widget.line_clicked.connect(clicked.append)

    qtbot.mouseClick(widget.findChildren(EngineLineRow)[0], Qt.MouseButton.LeftButton)

    assert clicked == ["b3b4"]


def test_clearing_restores_the_empty_message(qtbot):
    widget = _widget(qtbot)
    widget.set_lines([_line()])
    empty = widget.findChild(QLabel, "EngineLinesEmpty")

    widget.set_empty_text("Analysing position…")
    widget.clear()

    assert empty.text() == "Analysing position…"
    assert empty.isHidden() is False
    assert widget.lines == []

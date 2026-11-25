# SPDX-License-Identifier: GPL-3.0-only
"""Explorer controls expose useful tooltips and accessible names."""

from unittest.mock import MagicMock

from PyQt6.QtWidgets import QVBoxLayout, QWidget

from src.gui.analysis.moves.controls import MoveControls
from src.gui.analysis.moves.view import MoveListEntry, MoveListView
from src.gui.views.explorer.book_row import BookRowWidget
from src.gui.views.explorer.ui_mixin import ExplorerUiMixin


class _ChromeHost(ExplorerUiMixin, QWidget):
    """Bare host for the Explorer chrome builders."""

    def __init__(self):
        super().__init__()
        self.classify_enabled = False
        self._flip_board = MagicMock()
        self._copy_fen = MagicMock()
        self._copy_pgn = MagicMock()
        self.on_classify_toggled = MagicMock()
        self.on_legal_moves_toggled = MagicMock()
        self.on_engine_toggled = MagicMock()
        self._toggle_book = MagicMock()


def test_explorer_chrome_controls_have_tooltips(qtbot):
    panel = _ChromeHost()
    qtbot.addWidget(panel)
    layout = QVBoxLayout(panel)
    panel._build_header_bar(layout)
    panel._build_toggles(layout)
    panel._build_book_section(layout)

    for control in (
        panel.btn_flip,
        panel.btn_copy_fen,
        panel.btn_copy_pgn,
        panel.chk_classify,
        panel.chk_legal,
        panel.chk_engine,
        panel.chk_cache,
        panel.book_toggle,
        panel.lichess_attribution,
    ):
        assert control.toolTip()


def test_explorer_move_controls_have_named_tooltips(qtbot):
    controls = MoveControls(variant="explorer")
    qtbot.addWidget(controls)

    for button in (
        controls.btn_first,
        controls.btn_prev,
        controls.btn_next,
        controls.btn_last,
    ):
        assert button.toolTip()
        assert button.accessibleName() == button.toolTip()


def test_explorer_move_rows_do_not_repeat_the_move_text(qtbot):
    view = MoveListView(variant="explorer")
    qtbot.addWidget(view)
    view.set_entries([MoveListEntry("e4"), MoveListEntry("e5")])

    assert view.table.item(0, 1).toolTip() == ""
    assert view.table.item(0, 2).toolTip() == ""


def test_book_row_widget_exposes_play_tooltip(qtbot):
    row = BookRowWidget("Nf3")
    qtbot.addWidget(row)

    assert row.toolTip() == "Play Nf3"

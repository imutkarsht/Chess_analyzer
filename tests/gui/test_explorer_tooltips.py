# SPDX-License-Identifier: GPL-3.0-only
"""Explorer move controls stay accessible without noisy per-move tooltips."""

from src.gui.analysis.moves.controls import MoveControls
from src.gui.analysis.moves.view import MoveListEntry, MoveListView


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

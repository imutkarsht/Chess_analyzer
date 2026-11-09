"""Shared move-list table behaviour for both page variants."""

from PyQt6.QtCore import Qt

from src.gui.analysis.move_list_view import MoveListEntry, MoveListView


def test_explorer_variant_renders_plain_items_and_pending(qapp):
    view = MoveListView(variant="explorer")
    entries = [
        MoveListEntry(san="e4"),
        MoveListEntry(san="e5", classification="Best"),
        MoveListEntry(san="Nf3"),
    ]

    view.set_entries(entries)

    assert view.table.rowCount() == 2
    assert view.table.item(0, 1).text() == "e4"
    assert view.table.item(0, 1).data(Qt.ItemDataRole.UserRole) == 0
    assert view.table.item(0, 2).text() == "e5"
    assert view.move_widgets == {}

    view.set_pending(0, True)

    assert view.table.item(0, 1).text() == "~ e4 ~"
    assert view.entries[0].classification == "Pending"


def test_explorer_variant_truncates_after_navigation_and_emits_state(qapp):
    view = MoveListView(variant="explorer")
    view.set_entries(
        [MoveListEntry("e4"), MoveListEntry("e5"), MoveListEntry("Nf3")]
    )
    states = []
    view.state_changed.connect(lambda index, total: states.append((index, total)))

    view.set_current_index(1)
    view.append_entry(MoveListEntry("Nc6"))

    assert [entry.san for entry in view.entries] == ["e4", "e5", "Nc6"]
    assert view.current_index == 2
    assert states[-1] == (2, 3)


def test_analysis_variant_uses_cell_widgets_and_think_time(qapp):
    view = MoveListView(variant="analysis")
    view.set_entries(
        [
            MoveListEntry("e4", move_number=1, time_spent=2.0),
            MoveListEntry("e5", classification="Blunder", move_number=1),
        ],
        max_seconds=10.0,
    )

    assert view.table.rowCount() == 1
    assert set(view.move_widgets) == {0, 1}
    assert view.think_bars == list(view.move_widgets.values())
    assert view.move_widgets[0]._time_label.text()


def test_analysis_selection_repaints_only_old_and_new_rows(qapp):
    view = MoveListView(variant="analysis")
    view.set_entries([MoveListEntry(f"m{i}") for i in range(8)])
    view.set_current_index(0)

    calls = []
    for index, widget in view.move_widgets.items():
        original = widget.set_state
        widget.set_state = (
            lambda selected, row_active, i=index, fn=original: (
                calls.append(i),
                fn(selected, row_active),
            )
        )

    view.set_current_index(1)

    assert set(calls) == {0, 1}


def test_analysis_entry_update_does_not_repaint_every_cell(qapp):
    view = MoveListView(variant="analysis")
    view.set_entries([MoveListEntry(f"m{i}") for i in range(8)])
    view.set_current_index(0)

    calls = []
    view._apply_selection = lambda: calls.append("selection")
    view.update_entry(5, classification="Blunder")

    assert calls == []
    assert view.entries[5].classification == "Blunder"


def test_batch_update_refreshes_each_changed_cell_once(qapp):
    view = MoveListView(variant="analysis")
    view.set_entries([MoveListEntry(f"m{i}") for i in range(6)])
    calls = []
    view._refresh_entry_cell = lambda index: calls.append(index)

    view.update_entries(
        {
            0: {"classification": "Best"},
            2: {"classification": "Blunder"},
        }
    )

    assert calls == [0, 2]


def test_plain_update_changes_only_its_item(qapp, monkeypatch):
    view = MoveListView(variant="explorer")
    view.set_entries([MoveListEntry("e4"), MoveListEntry("e5")])
    rendered = []
    monkeypatch.setattr(view, "_render_plain", lambda: rendered.append(True))

    view.set_pending(1, True)

    assert rendered == []
    assert view.table.item(0, 2).text() == "~ e5 ~"
    assert view.entries[1].classification == "Pending"


def test_row_number_click_selects_first_move_of_row(qapp):
    view = MoveListView(variant="explorer")
    view.set_entries([MoveListEntry("e4"), MoveListEntry("e5")])
    selected = []
    view.move_selected.connect(selected.append)

    view._on_table_clicked(0, 0)

    assert selected == [0]

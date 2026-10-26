"""The sortable list component shared by settings pages."""

from PyQt6.QtCore import QPointF

from src.gui.components import SortableItem, SortableItemList


def test_move_item_reorders_and_emits(qapp):
    widget = SortableItemList()
    widget.set_items(
        [
            SortableItem("one", "One"),
            SortableItem("two", "Two"),
            SortableItem("three", "Three"),
        ]
    )
    changes = []
    widget.order_changed.connect(changes.append)

    widget.move_item(0, 2)

    assert widget.keys() == ["two", "three", "one"]
    assert changes == [["two", "three", "one"]]
    widget.deleteLater()


class _DropEvent:
    def __init__(self, source, position):
        self._source = source
        self._position = position
        self.accepted = False
        self.drop_action = None

    def source(self):
        return self._source

    def position(self):
        return self._position

    def setDropAction(self, action):
        self.drop_action = action

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.accepted = False


def test_drop_event_moves_row_without_deleting_it(qapp, qtbot):
    widget = SortableItemList()
    qtbot.addWidget(widget)
    widget.resize(400, 300)
    widget.set_items(
        [
            SortableItem("one", "One"),
            SortableItem("two", "Two"),
            SortableItem("three", "Three"),
        ]
    )
    widget.show()
    qapp.processEvents()

    last_rect = widget.visualRect(widget.model().index(2, 0))
    event = _DropEvent(
        widget,
        QPointF(last_rect.center().x(), last_rect.bottom()),
    )
    widget._drag_source_row = 0
    widget.dropEvent(event)

    assert event.accepted is True
    assert widget.keys() == ["two", "three", "one"]
    assert widget.count() == 3


def test_autoscroll_moves_the_list_during_drag(qapp, qtbot):
    widget = SortableItemList()
    qtbot.addWidget(widget)
    widget.resize(400, 300)
    widget.set_items(
        [SortableItem(str(i), f"Item {i}") for i in range(12)]
    )
    widget.set_visible_rows(3)
    widget.show()
    qapp.processEvents()

    bar = widget.verticalScrollBar()
    bar.setValue(0)
    widget._autoscroll_delta = 14
    widget._autoscroll_step()

    assert bar.value() > 0


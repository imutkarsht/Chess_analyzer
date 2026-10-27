"""Behavior tests for the shared pagination bar."""

from src.gui.components.pagination_bar import PaginationBar


def test_page_label_and_edge_disabled_states(qtbot):
    bar = PaginationBar(page=0, total_pages=3)
    qtbot.addWidget(bar)

    assert bar.label.text() == "Page 1 of 3"
    assert not bar.prev_btn.isEnabled()
    assert bar.next_btn.isEnabled()

    bar.set_page(2, 3)

    assert bar.label.text() == "Page 3 of 3"
    assert bar.prev_btn.isEnabled()
    assert not bar.next_btn.isEnabled()


def test_page_label_can_include_the_total_count(qtbot):
    bar = PaginationBar()
    qtbot.addWidget(bar)

    bar.set_page(1, 3, total_items=25)

    assert bar.label.text() == "Page 2 of 3 (25 total)"


def test_clicks_emit_navigation_signals(qtbot):
    bar = PaginationBar(page=1, total_pages=3)
    qtbot.addWidget(bar)
    events = []
    bar.prev_clicked.connect(lambda: events.append("prev"))
    bar.next_clicked.connect(lambda: events.append("next"))

    bar.prev_btn.click()
    bar.next_btn.click()

    assert events == ["prev", "next"]


def test_compatibility_aliases_point_at_the_same_widgets(qtbot):
    bar = PaginationBar()
    qtbot.addWidget(bar)

    assert bar.btn_prev is bar.prev_btn
    assert bar.btn_next_page is bar.next_btn
    assert bar.lbl_page_info is bar.label

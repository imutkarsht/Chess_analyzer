"""Behavior tests for the shared pagination state and bar."""

from src.gui.components import (
    Button,
    ButtonVariant,
    PaginationBar,
    PaginationSize,
    PaginationState,
    PaginationStyle,
)


def test_state_clamps_slices_and_recomputes_pages():
    state = PaginationState(page_size=10, total_items=25)
    assert (state.total_pages, state.start_index, state.end_index) == (3, 0, 10)
    assert state.range_text() == "1–10 of 25"
    assert len(state.slice(list(range(25)))) == 10

    assert state.set_page(99) is True
    assert (state.page, state.start_index, state.end_index) == (2, 20, 25)
    assert state.has_next is False
    assert state.range_text() == "21–25 of 25"

    # Shrinking the data set pulls the page back into range.
    state.set_total_items(3)
    assert state.page == 0
    state.set_page_size(2)
    assert state.total_pages == 2
    state.set_page(1)
    assert state.end_index == 3


def test_state_navigation_reports_change():
    state = PaginationState(page_size=5, total_items=12)
    assert state.previous() is False
    assert state.next() is True
    assert state.next() is True
    assert state.next() is False
    assert state.page == 2


def test_bar_clicks_update_state_and_emit_page_changed(qtbot):
    state = PaginationState(page_size=10, total_items=25)
    bar = PaginationBar(state)
    qtbot.addWidget(bar)
    pages: list[int] = []
    bar.page_changed.connect(pages.append)

    assert bar.label.text() == "Page 1 of 3"
    assert not bar.prev_btn.isEnabled()

    bar.next_btn.click()
    bar.prev_btn.click()
    bar.prev_btn.click()  # already on page 1: no change, no emit

    assert pages == [1, 0]
    assert state.page == 0


def test_numbered_bar_marks_current_page_and_hides_at_one_page(qtbot):
    state = PaginationState(page_size=10, total_items=25)
    bar = PaginationBar(
        state,
        style=PaginationStyle.NUMBERED,
        size=PaginationSize.PAGE,
        hide_when_single_page=True,
    )
    qtbot.addWidget(bar)

    numbers = [b for b in bar.findChildren(Button) if b.text().isdigit()]
    assert [b.text() for b in numbers] == ["1", "2", "3"]
    assert numbers[0].variant is ButtonVariant.PRIMARY

    bar.set_page(2)
    assert [b for b in bar.findChildren(Button) if b.variant is ButtonVariant.PRIMARY][0].text() == "3"

    bar.set_page(0, total_items=4)
    assert bar.isHidden()


def test_legacy_set_page_and_aliases(qtbot):
    bar = PaginationBar(PaginationState(page_size=10), show_total=True)
    qtbot.addWidget(bar)
    bar.set_page(1, 3, total_items=25)

    assert bar.label.text() == "Page 2 of 3 (25 total)"
    assert bar.btn_prev_page is bar.prev_btn
    assert bar.lbl_page_info is bar.label
    assert bar.visible_items(list(range(25))) == list(range(10, 20))

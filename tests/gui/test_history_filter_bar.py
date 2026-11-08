"""History filter command bar, tokens, and disclosure panel."""

from src.gui.components import FilterChip
from src.gui.views.history_filter_bar import HistoryFilterBar


def _bar(qtbot) -> HistoryFilterBar:
    bar = HistoryFilterBar()
    qtbot.addWidget(bar)
    bar.show()
    return bar


def test_filter_panel_is_progressive_disclosure(qtbot):
    bar = _bar(qtbot)

    assert bar.panel.isHidden()
    assert not bar.btn_filters.isChecked()

    bar.btn_filters.click()

    assert not bar.panel.isHidden()
    assert bar.btn_filters.isChecked()


def test_active_filters_become_removeable_tokens_with_a_count(qtbot):
    bar = _bar(qtbot)
    bar.set_result_count(26)

    bar.result_filter.set_current_value("win")
    bar.analysis_filter.set_value("analyzed", emit=True)

    chips = [
        chip
        for chip in bar.findChildren(FilterChip)
        if not chip.isHidden()
    ]
    assert [chip.body.text() for chip in chips] == [
        "Result: Wins",
        "Analysis: Analyzed",
    ]
    assert bar.btn_filters.text() == "Filters · 2"
    assert bar.token_count_label.text() == "26 games · 2 filters"
    assert not bar.token_row.isHidden()


def test_chips_are_hidden_while_the_panel_is_open(qtbot):
    bar = _bar(qtbot)
    bar.result_filter.set_current_value("win")
    bar.result_filter.setFocus()
    bar.set_panel_open(False)
    assert not bar.token_row.isHidden()

    bar.set_panel_open(True)

    assert bar.panel.isVisible()
    assert bar.token_row.isHidden()


def test_chip_body_reopens_its_filter_and_close_removes_it(qtbot):
    bar = _bar(qtbot)
    bar.analysis_filter.set_value("analyzed", emit=True)
    bar.set_panel_open(False)
    chip = bar.findChild(FilterChip)
    assert chip is not None

    chip.body.click()
    assert not bar.panel.isHidden()
    assert bar.token_row.isHidden()

    bar.set_panel_open(False)
    chip.close_button.click()
    assert bar.analysis_filter.value() == ""
    assert bar.btn_filters.text() == "Filters"


def test_clear_filters_clears_search_and_filters_but_keeps_sort(qtbot):
    bar = _bar(qtbot)
    bar.search_input.setText("ruy")
    bar.source_filter.set_current_value("lichess")
    bar.analysis_filter.set_value("paused", emit=True)
    bar.sort_dropdown.set_current_value("oldest")
    changes = []
    bar.filters_changed.connect(lambda: changes.append(True))

    bar.reset_filters()

    assert bar.search_input.text() == ""
    assert bar.source_filter.current_value() == ""
    assert bar.analysis_filter.value() == ""
    assert bar.sort_dropdown.current_value() == "oldest"
    assert changes == [True]

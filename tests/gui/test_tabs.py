"""Shared tab component: page sync, selection, and appearance contracts."""

import pytest
from PyQt6.QtWidgets import QLabel

from src.gui.components import TabAppearance, Tabs, TabVariant


def _tabs(qtbot, **kwargs):
    widget = Tabs(**kwargs)
    qtbot.addWidget(widget)
    return widget


def test_pages_follow_the_selected_tab(qtbot):
    tabs = _tabs(qtbot, variant=TabVariant.SEGMENTED)
    first, second = QLabel("one"), QLabel("two")
    tabs.add_tab("One", first)
    tabs.add_tab("Two", second)

    assert tabs.pages.currentWidget() is first

    tabs.set_current_index(1)

    assert tabs.pages.currentWidget() is second


def test_current_changed_fires_once_per_selection(qtbot):
    tabs = _tabs(qtbot)
    tabs.add_tab("One")
    tabs.add_tab("Two")
    seen: list[int] = []
    tabs.current_changed.connect(seen.append)

    tabs.set_current_index(1)
    tabs.set_current_index(1)

    assert seen == [1]


def test_bar_only_mode_leaves_pages_hidden(qtbot):
    tabs = _tabs(qtbot, variant=TabVariant.UNDERLINE)
    tabs.add_tab("Boards")
    tabs.add_tab("Pieces")

    assert tabs.pages.isHidden()
    assert tabs.page(0) is None
    assert tabs.current_index() == 0


@pytest.mark.parametrize(
    ("first_page", "second_page"),
    [(True, False), (False, True)],
)
def test_mixing_page_backed_and_bar_only_tabs_is_rejected(
    qtbot, first_page, second_page
):
    tabs = _tabs(qtbot)
    tabs.add_tab("First", QLabel() if first_page else None)

    with pytest.raises(ValueError):
        tabs.add_tab("Second", QLabel() if second_page else None)

    # The rejected tab must not leave a half-added tab behind.
    assert tabs.count() == 1


def test_removing_a_tab_keeps_the_remaining_pages_aligned(qtbot):
    tabs = _tabs(qtbot)
    pages = [QLabel(name) for name in ("one", "two", "three")]
    for name, page in zip(("One", "Two", "Three"), pages, strict=True):
        tabs.add_tab(name, page)

    tabs.remove_tab(1)

    assert [tabs.tab_text(i) for i in range(tabs.count())] == ["One", "Three"]
    assert tabs.pages.count() == 2
    assert tabs.page(1) is pages[2]
    assert tabs.pages.indexOf(pages[1]) == -1


def test_appearance_changes_keep_tabs_and_selection(qtbot):
    tabs = _tabs(qtbot, variant=TabVariant.UNDERLINE)
    tabs.add_tab("One", QLabel())
    tabs.add_tab("Two", QLabel())
    tabs.set_current_index(1)

    tabs.set_appearance(TabAppearance.for_variant(TabVariant.SEGMENTED))

    assert tabs.appearance.variant is TabVariant.SEGMENTED
    assert tabs.count() == 2
    assert tabs.pages.currentIndex() == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"padding": (1, 2, 3)},
        {"padding": (1, 2, 3, -4)},
        {"active_style": "glow"},
        {"font_size": 12, "unknown_option": True},
    ],
)
def test_invalid_appearance_options_are_rejected(qtbot, overrides):
    with pytest.raises((TypeError, ValueError)):
        Tabs(**overrides)


def test_conflicting_variant_and_appearance_are_rejected(qtbot):
    appearance = TabAppearance.for_variant(TabVariant.SEGMENTED)

    with pytest.raises(ValueError):
        Tabs(TabVariant.UNDERLINE, appearance=appearance)


def test_segmented_selector_keeps_its_key_contract(qtbot):
    from src.gui.dialogs.load_game.online_fetch_panel import SegmentedSelector

    selector = SegmentedSelector([("a", "Alpha"), ("b", "Beta")], "a")
    qtbot.addWidget(selector)
    emitted: list[str] = []
    selector.valueChanged.connect(emitted.append)

    selector.setValue("b")

    assert selector.value() == "b"
    assert emitted == []  # programmatic updates must not look like user input

    selector.tabs.set_current_index(0)

    assert selector.value() == "a"
    assert emitted == ["a"]

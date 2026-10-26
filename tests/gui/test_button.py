"""Central Button component: variants, sizes, loading and selection."""

from pathlib import Path

import pytest

from src.gui.components import Button, ButtonSize, ButtonVariant

# Purpose-built widgets that are not buttons (swatches, star rating, graph nodes)
# or segmented chip controls whose checked look is customized per card.
RAW_BUTTON_ALLOWLIST = {
    "src/gui/analysis/move_cell_widget.py",
    "src/gui/analysis/variation_graph.py",
    "src/gui/components/star_rating_widget.py",
    "src/gui/views/metrics/accuracy_trend_card.py",
    "src/gui/views/metrics/ending_distribution_card.py",
    "src/gui/views/metrics/time_management_card.py",
    "src/gui/views/metrics/openings_list_card.py",
    "src/gui/views/settings/board_pieces_settings.py",
}


def test_no_raw_push_or_tool_buttons_outside_the_central_component():
    repo_root = Path(__file__).resolve().parents[2]
    gui_root = repo_root / "src" / "gui"
    offenders = []
    for path in gui_root.rglob("*.py"):
        relative = path.relative_to(repo_root).as_posix()
        if relative == "src/gui/components/button.py" or relative in RAW_BUTTON_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        if "QPushButton(" in text or "QToolButton(" in text:
            offenders.append(relative)

    assert offenders == []


def _button(qtbot, text="", **kwargs):
    button = Button(text, **kwargs)
    qtbot.addWidget(button)
    return button


def test_click_runs_the_handler(qtbot):
    calls = []
    button = _button(qtbot, "Run", on_click=lambda: calls.append(True))

    button.click()

    assert calls == [True]


def test_loading_disables_input_and_restores_it(qtbot):
    calls = []
    button = _button(qtbot, "Save", on_click=lambda: calls.append(True))

    button.set_loading(True)

    assert button.is_loading()
    assert not button.isEnabled()
    button.click()
    assert calls == []

    button.set_loading(False)

    assert button.isEnabled()
    assert not button.is_loading()
    button.click()
    assert calls == [True]


def test_loading_keeps_a_previously_disabled_button_disabled(qtbot):
    button = _button(qtbot, "Save")
    button.setEnabled(False)

    button.set_loading(True)
    button.set_loading(False)

    assert not button.isEnabled()


def test_icon_only_button_is_square_and_hides_text(qtbot):
    button = _button(
        qtbot,
        "Delete",
        size=ButtonSize.SM,
        icon_position="only",
        icon="fa5s.trash",
        tooltip="Delete",
    )

    assert button.text() == ""
    assert button.width() == button.height() == 28
    assert button.toolTip() == "Delete"


def test_checkable_button_toggles(qtbot):
    button = _button(qtbot, "Toggle", checkable=True)

    assert not button.isChecked()

    button.click()

    assert button.isChecked()


def test_variant_and_size_changes_preserve_state(qtbot):
    button = _button(qtbot, "Load", checkable=True)
    button.setChecked(True)

    button.set_variant(ButtonVariant.OUTLINED)
    button.set_size(ButtonSize.LG)

    assert button.variant is ButtonVariant.OUTLINED
    assert button.size is ButtonSize.LG
    assert button.text() == "Load"
    assert button.isChecked()


def test_invalid_variant_and_icon_position_are_rejected(qtbot):
    with pytest.raises(ValueError):
        Button(variant="banana")
    with pytest.raises(ValueError):
        Button(icon_position="middle")

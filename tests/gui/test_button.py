"""Central Button component: variants, sizes, loading and selection."""

import ast
from pathlib import Path

import pytest
from PyQt6.QtGui import QIcon

from src.gui.components import Button, ButtonSize, ButtonVariant

# Purpose-built widgets that are not buttons (swatches, star rating, graph nodes).
RAW_BUTTON_ALLOWLIST = {
    "src/gui/analysis/move_cell_widget.py",
    "src/gui/analysis/variation_graph.py",
    "src/gui/components/star_rating_widget.py",
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


def test_central_buttons_are_not_restyled_or_reiconed_manually():
    """Button owns its QSS/icon; callers must use refresh_styles/set_icon_spec."""
    repo_root = Path(__file__).resolve().parents[2]
    gui_root = repo_root / "src" / "gui"
    factories = {"Button", "create_button", "create_icon_button"}
    overrides = {"setStyleSheet", "setIcon", "setIconSize"}
    offenders = []

    for path in gui_root.rglob("*.py"):
        relative = path.relative_to(repo_root).as_posix()
        if relative == "src/gui/components/button.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))

        button_names: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if not (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id in factories
            ):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            button_names.update(ast.unparse(target) for target in targets)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in overrides:
                continue
            if ast.unparse(node.func.value) in button_names:
                offenders.append(
                    f"{relative}:{node.lineno} calls {node.func.attr} on a Button"
                )

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


def test_refresh_styles_reapplies_the_icon(qtbot):
    button = _button(qtbot, "Coach", variant=ButtonVariant.TONAL, icon="fa5s.magic")
    button.setIcon(QIcon())

    button.refresh_styles()

    assert not button.icon().isNull()


def test_accent_signal_refreshes_buttons_automatically(qtbot):
    from src.gui.theme import ThemeManager

    button = _button(qtbot, "Coach", variant=ButtonVariant.TONAL, icon="fa5s.magic")
    button.setIcon(QIcon())

    ThemeManager.instance().accent_changed.emit("#123456")

    assert not button.icon().isNull()
    with pytest.raises(ValueError):
        Button(variant="banana")
    with pytest.raises(ValueError):
        Button(icon_position="middle")

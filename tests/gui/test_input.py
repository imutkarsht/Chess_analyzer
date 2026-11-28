"""Central input components: states, affordances, and the single-source guard."""

import ast
from pathlib import Path

from PyQt6.QtWidgets import QLineEdit

from scripts.hygiene_rules import RAW_INPUT_ALLOWLIST, RAW_INPUT_CLASSES
from src.gui.components import Input, TextArea

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def test_no_raw_text_widgets_outside_the_central_component():
    offenders = []
    for path in SRC.rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        if relative in RAW_INPUT_ALLOWLIST:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in RAW_INPUT_CLASSES
            ):
                offenders.append(f"{relative}:{node.lineno} constructs {node.func.id}")

    assert offenders == []


def test_invalid_state_is_a_property_not_a_stylesheet_swap(qtbot):
    field = Input()
    qtbot.addWidget(field)

    field.set_invalid()

    assert field.is_invalid()
    assert field.property("invalid") == "true"
    assert "invalid" not in field.styleSheet().replace('[invalid="true"]', "")

    field.clear_invalid()
    assert field.property("invalid") == "false"


def test_password_reveal_toggles_echo_mode_and_keeps_the_value(qtbot):
    field = Input(password=True)
    qtbot.addWidget(field)
    field.setText("gsk_secret")

    assert field.echoMode() is QLineEdit.EchoMode.Password
    field.toggle_password_visibility()
    assert field.echoMode() is QLineEdit.EchoMode.Normal
    field.toggle_password_visibility()
    assert field.echoMode() is QLineEdit.EchoMode.Password
    assert field.text() == "gsk_secret"


def test_clear_affordance_appears_only_with_text(qtbot):
    field = Input(clearable=True)
    qtbot.addWidget(field)

    clear_action = field._clear_action
    assert clear_action is not None
    assert not clear_action.isVisible()

    field.setText("sicilian")
    assert clear_action.isVisible()

    clear_action.trigger()
    assert field.text() == ""
    assert not clear_action.isVisible()


def test_textarea_variants_pick_the_right_surface(qtbot):
    code = TextArea(variant="code")
    flat = TextArea(variant="flat", readonly=True)
    qtbot.addWidget(code)
    qtbot.addWidget(flat)

    # Variant styling lives in the global QSS matrix; the widget publishes
    # the property that selects it.
    assert code.property("textAreaVariant") == "code"
    assert flat.property("textAreaVariant") == "flat"
    assert flat.isReadOnly()

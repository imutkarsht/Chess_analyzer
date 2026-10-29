"""Central input components: states, affordances, and the single-source guard."""

import ast
from pathlib import Path

from PyQt6.QtWidgets import QLineEdit

from src.gui.components import Input, TextArea

# Widgets that legitimately own a raw editor: the central component itself, the
# painted date field's inner editor, and the canvas rename overlay.
RAW_INPUT_ALLOWLIST = {
    "src/gui/components/input.py",
    "src/gui/components/date_picker.py",
    "src/gui/analysis/variation_graph.py",
}

_RAW_CLASSES = {"QLineEdit", "QTextEdit", "QPlainTextEdit", "QSpinBox", "QDoubleSpinBox"}


def test_no_raw_text_widgets_outside_the_central_component():
    repo_root = Path(__file__).resolve().parents[2]
    offenders = []
    for path in (repo_root / "src" / "gui").rglob("*.py"):
        relative = path.relative_to(repo_root).as_posix()
        if relative in RAW_INPUT_ALLOWLIST:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in _RAW_CLASSES
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

    assert "monospace" in code.styleSheet()
    assert "background-color: transparent" in flat.styleSheet()
    assert flat.isReadOnly()

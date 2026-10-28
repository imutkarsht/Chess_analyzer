"""The shared `Select` dropdown: state, signals, popup, and compat surface."""

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from src.gui.components.select import Select, SelectOption


def test_placeholder_state_and_programmatic_selection(qtbot):
    select = Select(["Alpha", "Beta"], placeholder="Choose one")
    qtbot.addWidget(select)

    assert select.current_index() == -1
    assert select.current_text() == ""
    assert select.settingValue() is None

    values: list[object] = []
    texts: list[str] = []
    select.valueChanged.connect(values.append)
    select.currentTextChanged.connect(texts.append)

    select.set_current_index(1)

    assert select.current_text() == "Beta"
    assert select.settingValue() == "Beta"
    assert values == ["Beta"]
    assert texts == ["Beta"]

    select.show()
    select.showPopup()
    assert [row.index for row in select._popup.rows] == [-1, 0, 1]
    QTest.mouseClick(select._popup.rows[0], Qt.MouseButton.LeftButton)

    assert select.current_index() == -1
    assert select.settingValue() is None
    assert values == ["Beta", None]


def test_set_options_preserves_the_selected_value(qtbot):
    select = Select([("One", 1), ("Two", 2)], value=2)
    qtbot.addWidget(select)

    select.set_options([("Two", 2), ("Three", 3)])

    assert select.current_value() == 2
    assert [option.label for option in select.options()] == ["Two", "Three"]


def test_clicking_a_popup_row_selects_and_closes(qtbot):
    select = Select(["One", "Two", "Three"])
    qtbot.addWidget(select)
    select.show()

    select.showPopup()
    popup = select._popup
    assert select.is_open() is True
    assert [row.index for row in popup.rows] == [0, 1, 2]
    assert popup.highlight() == 0

    activated: list[int] = []
    select.activated.connect(activated.append)
    QTest.mouseClick(popup.rows[2], Qt.MouseButton.LeftButton)

    assert select.current_index() == 2
    assert select.is_open() is False
    assert activated == [2]


def test_popup_keyboard_navigation_and_escape(qtbot):
    select = Select(["One", "Two", "Three"])
    qtbot.addWidget(select)
    select.show()

    select.showPopup()
    popup = select._popup
    QTest.keyClick(popup, Qt.Key.Key_Down)
    QTest.keyClick(popup, Qt.Key.Key_Enter)

    assert select.current_index() == 1
    assert select.is_open() is False

    select.showPopup()
    QTest.keyClick(select._popup, Qt.Key.Key_Escape)
    assert select.is_open() is False
    assert select.current_index() == 1


def test_combobox_compatible_api_and_custom_values(qtbot):
    select = Select(
        [SelectOption("128 MB", 128)],
        allow_custom=True,
    )
    qtbot.addWidget(select)

    select.addItem("System", userData="system")
    select.insertItem(0, "Light", userData="light")

    assert select.count() == 3
    assert select.findData("system") == 2
    assert select.findText("Light") == 0

    select.setCurrentText("System")
    assert select.currentData() == "system"
    select.setItemText(2, "System theme")
    assert select.itemText(2) == "System theme"

    select.setSettingValue(96)
    assert select.current_value() == 96
    assert select.findValue(96) == 3

    select.set_options([SelectOption("Never", None), SelectOption("7 days", 7)])
    select.setSettingValue(None)
    assert select.current_value() is None

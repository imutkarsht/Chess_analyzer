"""Behavior tests for the shared segmented chip control."""

from src.gui.components.segmented_control import SegmentedControl


def _control(qtbot):
    control = SegmentedControl(
        options=[("10G", "10"), ("20G", "20"), ("All", "all")],
        value="20",
    )
    qtbot.addWidget(control)
    return control


def test_selecting_a_chip_updates_value_and_emits(qtbot):
    control = _control(qtbot)
    changes = []
    control.valueChanged.connect(changes.append)

    control.button("10").click()

    assert control.value() == "10"
    assert changes == ["10"]
    assert control.button("10").isChecked()
    assert not control.button("20").isChecked()


def test_selecting_the_active_chip_does_not_emit(qtbot):
    control = _control(qtbot)
    changes = []
    control.valueChanged.connect(changes.append)

    control.button("20").click()

    assert control.value() == "20"
    assert changes == []
    assert control.button("20").isChecked()


def test_set_value_without_emit_only_moves_the_checked_state(qtbot):
    control = _control(qtbot)
    changes = []
    control.valueChanged.connect(changes.append)

    control.set_value("all", emit=False)

    assert control.value() == "all"
    assert changes == []
    assert control.button("all").isChecked()
    assert not control.button("20").isChecked()


def test_set_value_with_emit_reports_a_real_change_only(qtbot):
    control = _control(qtbot)
    changes = []
    control.valueChanged.connect(changes.append)

    control.set_value("10", emit=True)
    control.set_value("10", emit=True)

    assert changes == ["10"]

"""Behavioural tests for the shared date picker and calendar popup."""

import pytest
from PyQt6.QtCore import QDate, QRect, QSize
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from src.gui.components.controls.date_picker import DatePicker, _CalendarPopup
from src.gui.theme import ThemeManager
from src.gui.theme.palette import LIGHT


@pytest.fixture
def host(qtbot):
    window = QWidget()
    window.resize(800, 600)
    layout = QVBoxLayout(window)
    layout.setContentsMargins(20, 20, 20, 20)
    qtbot.addWidget(window)
    window.show()
    return window


@pytest.fixture
def picker(qtbot, host):
    widget = DatePicker(host, label="Date", initial_date=QDate(2026, 10, 28))
    host.layout().addWidget(widget)
    qtbot.addWidget(widget)
    yield widget
    widget.close_calendar()


def _cell(picker: DatePicker, date: QDate):
    popup = picker._popup
    assert popup is not None
    return next(cell for cell in popup._cells if cell._date == date)


def test_defaults_typing_and_signals(qtbot, host, picker):
    assert picker.date() == QDate(2026, 10, 28)
    assert picker._edit.text() == "10/28/2026"

    emitted = []
    picker.dateChanged.connect(emitted.append)
    picker.set_date(QDate(2026, 11, 2))
    assert emitted == [QDate(2026, 11, 2)]
    assert picker._edit.text() == "11/02/2026"

    picker.set_date(QDate(2026, 11, 2))
    assert len(emitted) == 1

    clearable = DatePicker(
        host, label="Date", initial_date=QDate(2026, 1, 5), clearable=True
    )
    qtbot.addWidget(clearable)
    cleared = []
    clearable.cleared.connect(lambda: cleared.append(True))
    clearable.clear()
    assert clearable.date() is None
    assert clearable._edit.text() == ""
    assert cleared == [True]


def test_typed_dates_commit_and_invalid_input_reverts(picker):
    picker._edit.setText("2026-11-05")
    picker._commit_text()
    assert picker.date() == QDate(2026, 11, 5)

    picker._edit.setText("not-a-date")
    picker._commit_text()
    assert picker.date() == QDate(2026, 11, 5)
    assert picker._edit.text() == "11/05/2026"
    assert picker._invalid is True

    picker._clear_invalid()
    assert picker._invalid is False


def test_range_clamps_and_rejects_out_of_range_input(picker):
    picker.set_range(QDate(2026, 10, 10), QDate(2026, 10, 20))

    picker._edit.setText("2026-10-05")
    picker._commit_text()
    assert picker._invalid is True
    assert picker.date() == QDate(2026, 10, 20)

    picker.set_date(QDate(2026, 9, 1))
    assert picker.date() == QDate(2026, 10, 10)
    picker.set_date(QDate(2026, 11, 1))
    assert picker.date() == QDate(2026, 10, 20)


def test_popup_opens_and_selecting_a_day_updates_the_field(picker):
    picker.open_calendar()
    popup = picker._popup

    assert picker.is_calendar_open is True
    assert popup is not None and popup.isVisible()
    assert popup._header_btn.text().startswith("October 2026")
    assert _cell(picker, QDate(2026, 10, 28))._selected is True

    _cell(picker, QDate(2026, 10, 20)).click()

    assert picker.date() == QDate(2026, 10, 20)
    assert popup.isVisible() is False
    assert picker.is_calendar_open is False


def test_disabled_picker_does_not_open_and_closes_an_open_popup(picker):
    picker.setEnabled(False)
    picker.open_calendar()
    assert picker.is_calendar_open is False

    picker.setEnabled(True)
    picker.open_calendar()
    assert picker._popup.isVisible() is True

    picker.setEnabled(False)
    assert picker._popup.isVisible() is False


def test_hiding_the_field_closes_the_popup(picker):
    picker.open_calendar()
    assert picker._popup.isVisible() is True

    picker.hide()
    assert picker._popup.isVisible() is False
    assert picker.is_calendar_open is False


def test_keyboard_navigation_and_selection(picker):
    picker.open_calendar()
    popup = picker._popup
    popup._focused_date = QDate(2026, 10, 15)

    popup._move_focus(1)
    assert popup._focused_date == QDate(2026, 10, 16)
    popup._move_focus(7)
    assert popup._focused_date == QDate(2026, 10, 23)

    popup._select_focused()
    assert picker.date() == QDate(2026, 10, 23)
    assert popup.isVisible() is False

    picker.set_range(QDate(2026, 10, 1), QDate(2026, 10, 23))
    picker.open_calendar()
    popup._focused_date = QDate(2026, 10, 23)
    popup._move_focus(1)
    assert popup._focused_date == QDate(2026, 10, 23)


def test_month_navigation_and_month_year_view(picker):
    picker.open_calendar()
    popup = picker._popup

    popup._next_btn.click()
    assert popup._header_btn.text().startswith("November 2026")
    popup._prev_btn.click()
    assert popup._header_btn.text().startswith("October 2026")

    popup._show_month_page()
    assert popup._stack.currentIndex() == 1
    assert popup._year_label.text() == "2026"
    assert popup._month_buttons[1].text() == "February"

    popup._select_month(1)
    assert popup._stack.currentIndex() == 0
    assert popup._header_btn.text().startswith("February 2026")

    popup._show_month_page()
    popup._change_year(1)
    assert popup._year_label.text() == "2027"


def test_out_of_range_days_are_disabled(picker):
    picker.set_range(QDate(2026, 10, 10), QDate(2026, 10, 20))
    picker.open_calendar()

    assert _cell(picker, QDate(2026, 10, 9)).isEnabled() is False
    assert _cell(picker, QDate(2026, 10, 10)).isEnabled() is True
    assert _cell(picker, QDate(2026, 10, 21)).isEnabled() is False

    _cell(picker, QDate(2026, 10, 9)).click()
    assert picker.date() == QDate(2026, 10, 20)
    assert picker._popup.isVisible() is True


def test_popup_placement_flips_and_clamps():
    available = QRect(0, 0, 900, 600)
    size = QSize(344, 400)

    below = _CalendarPopup._popup_position(
        QRect(100, 100, 220, 52), size, available
    )
    assert below.x() == 100 and below.y() == 158

    above = _CalendarPopup._popup_position(
        QRect(100, 500, 220, 52), size, available
    )
    assert above.y() == 94

    clamped_right = _CalendarPopup._popup_position(
        QRect(700, 100, 220, 52), size, available
    )
    assert clamped_right.x() == 547

    clamped_left = _CalendarPopup._popup_position(
        QRect(-50, 100, 220, 52), size, available
    )
    assert clamped_left.x() == 8

    tight = _CalendarPopup._popup_position(
        QRect(100, 260, 220, 52), QSize(344, 580), available
    )
    assert tight.y() == 11


def test_theme_change_restyles_field_and_popup(picker, monkeypatch):
    picker.open_calendar()
    popup = picker._popup
    dark_sheet = popup._panel.styleSheet()

    monkeypatch.setattr(ThemeManager, "palette", classmethod(lambda cls: LIGHT))
    picker._on_theme_changed()

    assert popup._panel.styleSheet() != dark_sheet
    assert LIGHT.surface in popup._panel.styleSheet()
    assert LIGHT.text_primary in picker._edit.styleSheet()
    assert picker._label_widget is not None
    assert "color:" in picker._label_widget.styleSheet()


def test_read_only_picker_keeps_typing_disabled_but_calendar_available(
    qtbot, host
):
    widget = DatePicker(
        host,
        label="Date",
        initial_date=QDate(2026, 10, 28),
        editable=False,
    )
    qtbot.addWidget(widget)

    assert widget._edit.isReadOnly() is True
    widget._edit.setText("2026-11-01")
    widget._commit_text()
    assert widget.date() == QDate(2026, 10, 28)

    widget.open_calendar()
    assert widget._popup.isVisible() is True
    widget.close_calendar()


def test_load_game_picker_does_not_allow_future_dates(qtbot):
    from src.gui.dialogs.load_game.online_fetch_panel import OnlineFetchPanel

    panel = OnlineFetchPanel()
    qtbot.addWidget(panel)
    picker = panel.date_picker

    today = QDate.currentDate()
    assert picker.maximum() == today

    picker.set_date(today.addDays(1))
    assert picker.date() == today

    picker.open_calendar()
    tomorrow = today.addDays(1)
    if tomorrow.month() == today.month():
        cell = _cell(picker, tomorrow)
        assert cell.isEnabled() is False
    picker.close_calendar()

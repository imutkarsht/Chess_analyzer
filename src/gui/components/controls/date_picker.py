"""Shared outlined date picker with a custom calendar popup.

The field is painted instead of QSS-styled so the floating label can sit in a
gap cut out of the outline, matching the notification-style references used
across the app. The popup is a real ``Qt.Popup`` window built from a custom
grid rather than ``QCalendarWidget``, which keeps its chrome, sizing, and colors
fully controlled by the app theme.

Used by the Load Game dialog and intended as the single date entry point for
future screens.
"""

from __future__ import annotations

from enum import IntEnum

from PyQt6.QtCore import (
    QDate,
    QEvent,
    QLocale,
    QPoint,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
)
from PyQt6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.components.controls.button import Button, ButtonSize, ButtonVariant
from src.gui.styles import Styles
from src.gui.theme import ThemeManager

_FIELD_HEIGHT = 44
_COMPACT_FIELD_HEIGHT = 38
_LABEL_OFFSET = 14
_CELL = 40
_PANEL_WIDTH = 324
_POPUP_MARGIN = 10
_POPUP_GAP = 6
_POPUP_EDGE = 8


class Weekday(IntEnum):
    """Qt day numbers, kept readable where the grid is offset."""

    MONDAY = 1
    SUNDAY = 7


def _first_day_of_week(value: Qt.DayOfWeek | int | None) -> int:
    raw = value if value is not None else QLocale.system().firstDayOfWeek()
    day = int(getattr(raw, "value", raw))
    return day if Weekday.MONDAY <= day <= Weekday.SUNDAY else int(Weekday.SUNDAY)


def _within_range(
    date: QDate, minimum: QDate | None, maximum: QDate | None
) -> bool:
    return not (
        (minimum is not None and date < minimum)
        or (maximum is not None and date > maximum)
    )


class _DayCell(QAbstractButton):
    """One painted calendar cell (blank, in-month, selected, or disabled)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._date: QDate | None = None
        self._selected = False
        self._today = False
        self._focused = False
        self.setFixedSize(_CELL, _CELL)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_day(
        self,
        date: QDate | None,
        *,
        selected: bool,
        today: bool,
        focused: bool,
        enabled: bool,
    ) -> None:
        self._date = date
        self._selected = selected
        self._today = today
        self._focused = focused
        self.setEnabled(enabled)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if enabled
            else Qt.CursorShape.ArrowCursor
        )
        if date is not None:
            self.setAccessibleName(
                QLocale.system().toString(date, QLocale.FormatType.LongFormat)
            )
        self.update()

    def clear_day(self) -> None:
        self._date = None
        self._selected = self._today = self._focused = False
        self.setEnabled(False)
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self._date is None:
            return

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            bounds = QRectF(self.rect()).adjusted(1, 1, -1, -1)
            centre = bounds.center()
            radius = min(bounds.width(), bounds.height()) / 2 - 1

            enabled = self.isEnabled()
            hovered = self.underMouse() and enabled

            if self._selected and enabled:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(Styles.COLOR_SURFACE_LIGHT))
                painter.drawEllipse(centre, radius, radius)
                pen = QPen(QColor(Styles.COLOR_ACCENT))
                pen.setWidthF(1.2)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(centre, radius, radius)
            elif (self._focused or hovered) and enabled:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(Styles.COLOR_SURFACE_LIGHT))
                painter.drawEllipse(centre, radius, radius)

            if not enabled:
                color = Styles.COLOR_TEXT_MUTED
            elif self._today and not self._selected:
                color = Styles.COLOR_ACCENT
            else:
                color = Styles.COLOR_TEXT_PRIMARY

            font = QFont(self.font())
            font.setPixelSize(13)
            font.setWeight(QFont.Weight.Medium)
            painter.setFont(font)
            painter.setPen(QColor(color))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                str(self._date.day()),
            )
        finally:
            painter.end()


class _CalendarPopup(QFrame):
    """Frameless calendar panel anchored to a :class:`DatePicker`."""

    dateSelected = pyqtSignal(QDate)
    clearRequested = pyqtSignal()
    closed = pyqtSignal()

    def __init__(
        self,
        *,
        minimum: QDate | None = None,
        maximum: QDate | None = None,
        first_day_of_week: Qt.DayOfWeek | int | None = None,
        show_today: bool = True,
        clearable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Calendar")

        self._minimum = minimum
        self._maximum = maximum
        self._first_dow = _first_day_of_week(first_day_of_week)
        self._show_today = show_today
        self._clearable = clearable
        self._date: QDate | None = None
        self._focused_date: QDate | None = None
        self._view = QDate.currentDate()
        self._was_visible = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            _POPUP_MARGIN, _POPUP_MARGIN, _POPUP_MARGIN, _POPUP_MARGIN
        )
        outer.setSpacing(0)

        self._panel = QFrame(self)
        self._panel.setObjectName("DatePickerPopup")
        self._panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._panel.setGraphicsEffect(ThemeManager.drop_shadow(2))
        outer.addWidget(self._panel)

        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        self._stack = QStackedWidget(self._panel)
        self._stack.addWidget(self._build_day_page())
        self._stack.addWidget(self._build_month_page())
        panel_layout.addWidget(self._stack)

        self.refresh_theme()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_day_page(self) -> QWidget:
        page = QWidget()
        page.setFixedWidth(_PANEL_WIDTH)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(2)

        self._header_btn = Button(
            "",
            ButtonVariant.GHOST,
            ButtonSize.MD,
            font_size=17,
            font_weight=600,
            text_color=Styles.COLOR_TEXT_PRIMARY,
            on_click=self._show_month_page,
        )
        self._header_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        header.addWidget(self._header_btn)
        header.addStretch(1)

        self._prev_btn = Button(
            variant=ButtonVariant.GHOST,
            size=ButtonSize.MD,
            icon="fa5s.chevron-left",
            icon_position="only",
            icon_size=18,
            tooltip="Previous month",
            on_click=lambda: self._change_month(-1),
        )
        self._next_btn = Button(
            variant=ButtonVariant.GHOST,
            size=ButtonSize.MD,
            icon="fa5s.chevron-right",
            icon_position="only",
            icon_size=18,
            tooltip="Next month",
            on_click=lambda: self._change_month(1),
        )
        for button in (self._prev_btn, self._next_btn):
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            header.addWidget(button)

        layout.addLayout(header)

        weekdays = QHBoxLayout()
        weekdays.setContentsMargins(0, 0, 0, 0)
        weekdays.setSpacing(0)
        self._weekday_labels: list[QLabel] = []
        for _ in range(7):
            label = QLabel()
            label.setObjectName("DatePickerWeekday")
            label.setFixedSize(_CELL, 24)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            weekdays.addWidget(label)
            self._weekday_labels.append(label)
        self._refresh_weekday_labels()
        layout.addLayout(weekdays)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)
        self._cells: list[_DayCell] = []
        for index in range(42):
            cell = _DayCell()
            cell.clicked.connect(
                lambda _checked=False, target=cell: self._on_cell_clicked(target)
            )
            grid.addWidget(cell, index // 7, index % 7)
            self._cells.append(cell)
        layout.addLayout(grid)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 4, 0, 0)
        footer.setSpacing(8)
        footer.addStretch(1)
        self._today_btn = Button(
            "Today",
            ButtonVariant.LINK,
            ButtonSize.SM,
            on_click=self._select_today,
        )
        self._clear_btn = Button(
            "Clear",
            ButtonVariant.LINK,
            ButtonSize.SM,
            on_click=self.clearRequested.emit,
        )
        for button in (self._today_btn, self._clear_btn):
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            footer.addWidget(button)
        layout.addLayout(footer)

        return page

    def _build_month_page(self) -> QWidget:
        page = QWidget()
        page.setFixedWidth(_PANEL_WIDTH)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(2)

        self._back_btn = Button(
            variant=ButtonVariant.GHOST,
            size=ButtonSize.MD,
            icon="fa5s.arrow-left",
            icon_position="only",
            icon_size=16,
            tooltip="Back to calendar",
            on_click=self._show_day_page,
        )
        self._prev_year_btn = Button(
            variant=ButtonVariant.GHOST,
            size=ButtonSize.MD,
            icon="fa5s.chevron-left",
            icon_position="only",
            icon_size=18,
            tooltip="Previous year",
            on_click=lambda: self._change_year(-1),
        )
        self._next_year_btn = Button(
            variant=ButtonVariant.GHOST,
            size=ButtonSize.MD,
            icon="fa5s.chevron-right",
            icon_position="only",
            icon_size=18,
            tooltip="Next year",
            on_click=lambda: self._change_year(1),
        )
        self._year_label = QLabel()
        self._year_label.setObjectName("DatePickerYear")
        self._year_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._year_label.setFixedWidth(64)

        for button in (self._back_btn, self._prev_year_btn, self._next_year_btn):
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        header.addWidget(self._back_btn)
        header.addStretch(1)
        header.addWidget(self._prev_year_btn)
        header.addWidget(self._year_label)
        header.addWidget(self._next_year_btn)
        header.addStretch(1)
        layout.addLayout(header)

        months = QGridLayout()
        months.setContentsMargins(0, 4, 0, 0)
        months.setHorizontalSpacing(6)
        months.setVerticalSpacing(6)
        self._month_buttons: list[Button] = []
        for index in range(12):
            button = Button(
                "",
                ButtonVariant.GHOST,
                ButtonSize.SM,
                checkable=True,
                on_click=lambda _checked=False, month=index: self._select_month(month),
            )
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setFixedHeight(34)
            months.addWidget(button, index // 3, index % 3)
            self._month_buttons.append(button)
        layout.addLayout(months)
        layout.addStretch(1)

        return page

    # ------------------------------------------------------------------
    # Public state
    # ------------------------------------------------------------------
    def set_date(self, date: QDate | None) -> None:
        self._date = date
        reference = date if date is not None and date.isValid() else QDate.currentDate()
        self._view = QDate(reference.year(), reference.month(), 1)
        self._focused_date = None
        self._refresh()

    def set_range(self, minimum: QDate | None, maximum: QDate | None) -> None:
        self._minimum = minimum
        self._maximum = maximum
        self._refresh()

    def refresh_theme(self) -> None:
        self._panel.setStyleSheet(Styles.get_date_picker_popup_qss())
        self._header_btn.set_text_color(Styles.COLOR_TEXT_PRIMARY)
        for cell in getattr(self, "_cells", []):
            cell.update()
        self.update()

    # ------------------------------------------------------------------
    # Navigation and selection
    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        self._header_btn.setText(self._month_year_text(self._view))
        self._year_label.setText(str(self._view.year()))
        self._refresh_grid()
        self._refresh_month_buttons()
        self._refresh_footer()

    def _refresh_footer(self) -> None:
        self._today_btn.setVisible(self._show_today)
        self._clear_btn.setVisible(self._clearable)

    def _refresh_weekday_labels(self) -> None:
        locale = QLocale.system()
        for column, label in enumerate(self._weekday_labels):
            day = (self._first_dow - 1 + column) % 7 + 1
            label.setText(
                locale.dayName(day, QLocale.FormatType.NarrowFormat).upper()
            )

    def _month_year_text(self, date: QDate) -> str:
        locale = QLocale.system()
        month = locale.standaloneMonthName(
            date.month(), QLocale.FormatType.LongFormat
        )
        return f"{month} {date.year()}  ▾"

    def _refresh_grid(self) -> None:
        first = self._view
        offset = (first.dayOfWeek() - self._first_dow) % 7
        days = first.daysInMonth()
        today = QDate.currentDate()

        for index, cell in enumerate(self._cells):
            day_number = index - offset + 1
            if 1 <= day_number <= days:
                date = QDate(first.year(), first.month(), day_number)
                cell.set_day(
                    date,
                    selected=date == self._date,
                    today=date == today,
                    focused=date == self._focused_date,
                    enabled=self._in_range(date),
                )
            else:
                cell.clear_day()

    def _refresh_month_buttons(self) -> None:
        locale = QLocale.system()
        current = self._view
        for index, button in enumerate(self._month_buttons):
            button.setText(
                locale.standaloneMonthName(
                    index + 1, QLocale.FormatType.LongFormat
                )
            )
            button.setChecked(index + 1 == current.month())

    def _in_range(self, date: QDate) -> bool:
        return _within_range(date, self._minimum, self._maximum)

    def _clamp_view(self, date: QDate) -> QDate:
        if self._minimum is not None and date < QDate(
            self._minimum.year(), self._minimum.month(), 1
        ):
            return QDate(self._minimum.year(), self._minimum.month(), 1)
        if self._maximum is not None and date > QDate(
            self._maximum.year(), self._maximum.month(), 1
        ):
            return QDate(self._maximum.year(), self._maximum.month(), 1)
        return QDate(date.year(), date.month(), 1)

    def _change_month(self, delta: int) -> None:
        target = self._clamp_view(self._view.addMonths(delta))
        if target == self._view:
            return
        self._view = target
        self._focused_date = None
        self._refresh()

    def _change_year(self, delta: int) -> None:
        target = QDate(self._view.year() + delta, self._view.month(), 1)
        target = self._clamp_view(target)
        self._view = target
        self._focused_date = None
        self._refresh()

    def _select_month(self, month_index: int) -> None:
        self._view = self._clamp_view(
            QDate(self._view.year(), month_index + 1, 1)
        )
        self._focused_date = None
        self._refresh()
        self._show_day_page()

    def _show_month_page(self) -> None:
        self._stack.setCurrentIndex(1)
        self._refresh()

    def _show_day_page(self) -> None:
        self._stack.setCurrentIndex(0)
        self._refresh()

    def _on_cell_clicked(self, cell: _DayCell) -> None:
        if cell._date is not None and cell.isEnabled():
            self._focused_date = cell._date
            self.dateSelected.emit(cell._date)
            self.close()

    def _select_today(self) -> None:
        today = QDate.currentDate()
        if self._in_range(today):
            self._focused_date = today
            self.dateSelected.emit(today)
            self.close()

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------
    def _move_focus(self, days: int) -> None:
        if self._focused_date is None:
            self._focused_date = self._date or self._view
        target = self._focused_date.addDays(days)
        if not self._in_range(target):
            return
        self._focused_date = target
        self._view = QDate(target.year(), target.month(), 1)
        self._refresh()

    def _move_focus_month(self, months: int) -> None:
        if self._focused_date is None:
            self._focused_date = self._date or self._view
        target = self._focused_date.addMonths(months)
        if not self._in_range(target):
            return
        self._focused_date = target
        self._view = QDate(target.year(), target.month(), 1)
        self._refresh()

    def _move_focus_week_edge(self, to_end: bool) -> None:
        if self._focused_date is None:
            return
        offset = (self._focused_date.dayOfWeek() - self._first_dow) % 7
        delta = (6 - offset) if to_end else -offset
        self._move_focus(delta)

    def _select_focused(self) -> None:
        if self._focused_date is not None and self._in_range(self._focused_date):
            self.dateSelected.emit(self._focused_date)
            self.close()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self._stack.currentIndex() == 1:
            if event.key() == Qt.Key.Key_Escape:
                self._show_day_page()
                event.accept()
                return
            super().keyPressEvent(event)
            return

        handlers = {
            Qt.Key.Key_Left: lambda: self._move_focus(-1),
            Qt.Key.Key_Right: lambda: self._move_focus(1),
            Qt.Key.Key_Up: lambda: self._move_focus(-7),
            Qt.Key.Key_Down: lambda: self._move_focus(7),
            Qt.Key.Key_PageUp: lambda: self._move_focus_month(-1),
            Qt.Key.Key_PageDown: lambda: self._move_focus_month(1),
            Qt.Key.Key_Home: lambda: self._move_focus_week_edge(False),
            Qt.Key.Key_End: lambda: self._move_focus_week_edge(True),
        }
        if event.key() in handlers:
            handlers[event.key()]()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._select_focused()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Placement
    # ------------------------------------------------------------------
    @staticmethod
    def _popup_position(
        anchor: QRect, size: QSize, available: QRect
    ) -> QPoint:
        """Place below the field, flip above when needed, then clamp horizontally."""
        x = max(
            available.left() + _POPUP_EDGE,
            min(
                anchor.left(),
                available.right() - size.width() - _POPUP_EDGE,
            ),
        )
        below = anchor.bottom() + 1 + _POPUP_GAP
        above = anchor.top() - size.height() - _POPUP_GAP
        if below + size.height() <= available.bottom() - _POPUP_EDGE:
            y = below
        elif above >= available.top() + _POPUP_EDGE:
            y = above
        else:
            y = max(
                available.top() + _POPUP_EDGE,
                available.bottom() - size.height() - _POPUP_EDGE,
            )
        return QPoint(x, y)

    def show_for(self, field: QWidget) -> None:
        self.adjustSize()
        self._was_visible = True

        anchor = QRect(field.mapToGlobal(QPoint(0, 0)), field.size())
        screen = QGuiApplication.screenAt(anchor.center()) or QGuiApplication.primaryScreen()
        available = screen.availableGeometry()
        self.move(self._popup_position(anchor, self.sizeHint(), available))
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.PopupFocusReason)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        self._was_visible = True

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().hideEvent(event)
        if self._was_visible:
            self._was_visible = False
            self.closed.emit()


class DatePicker(QWidget):
    """Outlined, editable date field with a calendar popup.

    ``dateChanged`` emits a valid ``QDate`` whenever the selection changes.
    ``cleared`` fires when an optional empty state is selected. The field is
    theme-aware and repaints the label notch itself so it can sit on any parent
    surface without relying on a background-coloured label hack.
    """

    dateChanged = pyqtSignal(QDate)
    cleared = pyqtSignal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        label: str = "",
        initial_date: QDate | None = None,
        date_format: str = "MM/dd/yyyy",
        placeholder: str | None = None,
        minimum: QDate | None = None,
        maximum: QDate | None = None,
        clearable: bool = False,
        first_day_of_week: Qt.DayOfWeek | int | None = None,
        show_today: bool = True,
        compact: bool = False,
        editable: bool = True,
    ) -> None:
        super().__init__(parent)
        self._label_text = label
        self._date = initial_date or QDate.currentDate()
        self._date_format = date_format
        self._placeholder = placeholder or date_format.upper()
        self._minimum = minimum
        self._maximum = maximum
        self._clearable = clearable
        self._first_dow = _first_day_of_week(first_day_of_week)
        self._show_today = show_today
        self._compact = compact
        self._editable = editable
        self._field_height = _COMPACT_FIELD_HEIGHT if compact else _FIELD_HEIGHT
        self._focused = False
        self._hover = False
        self._invalid = False
        self._popup_open = False
        self._popup: _CalendarPopup | None = None

        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(self._field_height + (_LABEL_OFFSET if label else 0))
        self._edit = QLineEdit(self)
        self.setFocusProxy(self._edit)
        self.setAccessibleName(label or "Date")

        self._label_widget: QLabel | None = None
        if label:
            self._label_widget = QLabel(label, self)
            self._label_widget.setObjectName("DatePickerFieldLabel")
            self._label_widget.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
            )

        self._edit.setPlaceholderText(self._placeholder)
        self._edit.setFrame(False)
        self._edit.setReadOnly(not editable)
        self._edit.installEventFilter(self)
        self._edit.returnPressed.connect(self._commit_text)
        self._edit.editingFinished.connect(self._commit_text)
        self._edit.textEdited.connect(self._on_text_edited)

        self._icon = Button(
            variant=ButtonVariant.GHOST,
            size=ButtonSize.SM,
            icon="fa5s.calendar-alt",
            icon_position="only",
            icon_size=18,
            tooltip="Choose date",
            on_click=self._toggle_popup,
            parent=self,
        )
        self._icon.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        manager = ThemeManager.instance()
        manager.theme_changed.connect(self._on_theme_changed)
        manager.accent_changed.connect(self._on_theme_changed)

        self._apply_theme()
        self._set_edit_text()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def date(self) -> QDate | None:
        return self._date

    def set_date(self, date: QDate | None, *, emit: bool = True) -> None:
        if date is not None and not date.isValid():
            date = None
        if date is not None:
            date = self._clamp(date)
        if date == self._date:
            self._set_edit_text()
            return
        self._date = date
        self._invalid = False
        self._set_edit_text()
        self.update()
        if emit:
            if date is None:
                self.cleared.emit()
            else:
                self.dateChanged.emit(date)

    def setDate(self, date: QDate | None) -> None:  # noqa: N802 - Qt-style alias
        self.set_date(date)

    def clear(self) -> None:
        self.set_date(None)

    def open_calendar(self) -> None:
        """Open the calendar popup (no-op when disabled or already open)."""
        self._open_popup()

    def close_calendar(self) -> None:
        self._close_popup()

    @property
    def is_calendar_open(self) -> bool:
        return self._popup_open

    def set_range(
        self, minimum: QDate | None = None, maximum: QDate | None = None
    ) -> None:
        self._minimum = minimum
        self._maximum = maximum
        if self._date is not None:
            self.set_date(self._clamp(self._date), emit=False)
        if self._popup is not None:
            self._popup.set_range(minimum, maximum)

    def set_placeholder(self, text: str) -> None:
        self._placeholder = text
        self._edit.setPlaceholderText(text)

    def minimum(self) -> QDate | None:
        return self._minimum

    def maximum(self) -> QDate | None:
        return self._maximum

    # ------------------------------------------------------------------
    # Painting and geometry
    # ------------------------------------------------------------------
    def _surface_rect(self) -> QRectF:
        offset = _LABEL_OFFSET if self._label_text else 0
        return QRectF(
            1,
            offset,
            max(1, self.width() - 2),
            max(1, self.height() - offset - 1),
        )

    def _border_state(self) -> tuple[str, float]:
        if self._invalid:
            return Styles.COLOR_BLUNDER, 2.0
        if self._focused or self._popup_open:
            return Styles.COLOR_ACCENT, 2.0
        if self._hover and self.isEnabled():
            return Styles.COLOR_BORDER_LIGHT, 1.0
        return Styles.COLOR_BORDER, 1.0

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            color, width = self._border_state()
            rect = self._surface_rect().adjusted(
                width / 2, width / 2, -width / 2, -width / 2
            )

            fill = QColor(
                Styles.COLOR_SURFACE if self.isEnabled() else Styles.COLOR_SURFACE_LIGHT
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, 8, 8)

            path = QPainterPath()
            path.addRoundedRect(rect, 8, 8)
            if self._label_widget is not None and self._label_widget.width() > 0:
                label_rect = QRectF(
                    self._label_widget.x(),
                    rect.top() - width,
                    self._label_widget.width(),
                    width * 2,
                )
                notch = QPainterPath()
                notch.addRect(label_rect)
                path = path.subtracted(notch)

            pen = QPen(QColor(color))
            pen.setWidthF(width)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
        finally:
            painter.end()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        box = self._surface_rect()
        left = int(box.left() + 13)
        right = int(box.right() - 8 - 28)
        top = int(box.top() + (9 if self._label_text else 3))
        height = int(box.height() - (9 if self._label_text else 6))
        self._edit.setGeometry(left, top, max(20, right - left), max(16, height))
        self._icon.move(
            int(box.right() - 8 - 28), int(box.center().y() - 14)
        )
        if self._label_widget is not None:
            self._label_widget.adjustSize()
            self._label_widget.move(
                12, int(box.top() - self._label_widget.height() / 2) - 3
            )
            self._label_widget.raise_()

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt override
        return QSize(220, self.height())

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def enterEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().enterEvent(event)
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().leaveEvent(event)
        self._hover = False
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.MouseButton.LeftButton:
            self._open_popup()
            return
        super().mousePressEvent(event)

    def eventFilter(self, obj, event):  # noqa: N802 - Qt override
        if obj is self._edit:
            if event.type() == QEvent.Type.FocusIn:
                self._focused = True
                self._update_label_style()
                self.update()
            elif event.type() == QEvent.Type.FocusOut:
                self._focused = False
                self._update_label_style()
                self.update()
            elif event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Escape:
                    if self._popup_open:
                        self._close_popup()
                    else:
                        self._revert_text()
                    return True
                if event.key() == Qt.Key.Key_F4 or (
                    event.key() == Qt.Key.Key_Down
                    and event.modifiers() & Qt.KeyboardModifier.AltModifier
                ):
                    self._open_popup()
                    return True
        return super().eventFilter(obj, event)

    def changeEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.type() == QEvent.Type.EnabledChange:
            if not self.isEnabled() and self._popup_open:
                self._close_popup()
            self._icon.setEnabled(self.isEnabled())
            self._update_label_style()
            self.update()
        super().changeEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self._popup_open:
            self._close_popup()
        super().hideEvent(event)

    # ------------------------------------------------------------------
    # Popup
    # ------------------------------------------------------------------
    def _ensure_popup(self) -> _CalendarPopup:
        if self._popup is None:
            self._popup = _CalendarPopup(
                minimum=self._minimum,
                maximum=self._maximum,
                first_day_of_week=self._first_dow,
                show_today=self._show_today,
                clearable=self._clearable,
                parent=self,
            )
            self._popup.dateSelected.connect(self._on_popup_date)
            self._popup.clearRequested.connect(self._on_popup_clear)
            self._popup.closed.connect(self._on_popup_closed)
        return self._popup

    def _open_popup(self) -> None:
        if not self.isEnabled() or self._popup_open:
            return
        popup = self._ensure_popup()
        popup.set_date(self._date)
        popup.set_range(self._minimum, self._maximum)
        self._popup_open = True
        self._update_label_style()
        self.update()
        popup.show_for(self)

    def _close_popup(self) -> None:
        if self._popup is not None and self._popup.isVisible():
            self._popup.close()

    def _toggle_popup(self) -> None:
        if self._popup_open:
            self._close_popup()
        else:
            self._open_popup()

    def _on_popup_date(self, date: QDate) -> None:
        self.set_date(date)
        self._edit.setFocus()

    def _on_popup_clear(self) -> None:
        if self._clearable:
            self.set_date(None)
            self._close_popup()
            self._edit.setFocus()

    def _on_popup_closed(self) -> None:
        self._popup_open = False
        self._update_label_style()
        self.update()

    # ------------------------------------------------------------------
    # Text handling
    # ------------------------------------------------------------------
    def _candidate_formats(self) -> list[str]:
        formats = [
            self._date_format,
            "MM/dd/yyyy",
            "M/d/yyyy",
            "yyyy-MM-dd",
            QLocale.system().dateFormat(QLocale.FormatType.ShortFormat),
        ]
        unique: list[str] = []
        for fmt in formats:
            if fmt and fmt not in unique:
                unique.append(fmt)
        return unique

    def _parse_text(self, text: str) -> QDate | None:
        for fmt in self._candidate_formats():
            date = QDate.fromString(text, fmt)
            if date.isValid():
                return date
        return None

    def _on_text_edited(self, _text: str) -> None:
        if self._invalid:
            self._invalid = False
        self.update()

    def _commit_text(self) -> None:
        if not self._editable:
            return
        text = self._edit.text().strip()
        if not text:
            if self._clearable:
                self.set_date(None)
            else:
                self._revert_text()
            return

        date = self._parse_text(text)
        if date is None or not self._in_range(date):
            self._flag_invalid()
            self._revert_text()
            return

        self._invalid = False
        self.set_date(date)
        self.update()

    def _flag_invalid(self) -> None:
        self._invalid = True
        self.update()
        QTimer.singleShot(1200, self._clear_invalid)

    def _clear_invalid(self) -> None:
        if self._invalid:
            self._invalid = False
            self.update()

    def _revert_text(self) -> None:
        self._set_edit_text()

    def _set_edit_text(self) -> None:
        text = self._date.toString(self._date_format) if self._date is not None else ""
        self._edit.setText(text)

    def _clamp(self, date: QDate) -> QDate:
        if self._minimum is not None and date < self._minimum:
            return self._minimum
        if self._maximum is not None and date > self._maximum:
            return self._maximum
        return date

    def _in_range(self, date: QDate) -> bool:
        return _within_range(date, self._minimum, self._maximum)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------
    def _apply_theme(self) -> None:
        p = ThemeManager.palette()
        self._edit.setStyleSheet(
            Styles.get_date_picker_input_qss(
                font_size=13 if self._compact else 14
            )
        )
        palette = self._edit.palette()
        palette.setColor(QPalette.ColorRole.Text, QColor(p.text_primary))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(p.text_muted))
        self._edit.setPalette(palette)
        self._update_label_style()
        self.update()

    def _update_label_style(self) -> None:
        """Retint the floating label; accent while focused or open."""
        if self._label_widget is None:
            return
        if not self.isEnabled():
            color = Styles.COLOR_TEXT_MUTED
        elif self._focused or self._popup_open:
            color = Styles.COLOR_ACCENT
        else:
            color = Styles.COLOR_TEXT_SECONDARY
        self._label_widget.setStyleSheet(
            f"""
            QLabel#DatePickerFieldLabel {{
                background: transparent;
                color: {color};
                font-size: 11px;
                font-weight: 500;
                padding: 2px 4px;
            }}
            """
        )
        self._label_widget.adjustSize()

    def _on_theme_changed(self, *_args) -> None:
        self._apply_theme()
        if self._popup is not None:
            self._popup.refresh_theme()

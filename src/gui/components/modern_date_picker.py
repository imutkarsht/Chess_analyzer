"""
Modern Date Picker Widget - A modern, dark-mode desktop date picker with clean calendar popup.
"""
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QCalendarWidget, QMenu, QWidgetAction
)
from PyQt6.QtCore import pyqtSignal, Qt, QDate
from PyQt6.QtGui import QIcon
from ..styles import Styles

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False


class ModernDatePicker(QWidget):
    """A sleek desktop date picker with custom calendar popup."""

    dateChanged = pyqtSignal(QDate)

    def __init__(self, parent=None, initial_date: QDate = None):
        super().__init__(parent)
        self._current_date = initial_date or QDate.currentDate()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Line edit displaying clean formatted date e.g. "2026-07-24"
        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.display.setCursor(Qt.CursorShape.PointingHandCursor)
        self.display.setText(self._current_date.toString("yyyy-MM-dd"))
        self.display.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-top-left-radius: 8px;
                border-bottom-left-radius: 8px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 500;
                padding-left: 12px;
                height: 38px;
                selection-background-color: transparent;
            }}
            QLineEdit:focus {{
                border-color: {Styles.COLOR_ACCENT};
            }}
        """)

        # Add calendar icon on the left
        if HAS_QTAWESOME:
            cal_icon = qta.icon("fa5s.calendar-alt", color=Styles.COLOR_TEXT_SECONDARY)
            self.display.addAction(cal_icon, QLineEdit.ActionPosition.LeadingPosition)

        # Calendar button on the right
        self.cal_btn = QPushButton()
        self.cal_btn.setFixedSize(38, 38)
        self.cal_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if HAS_QTAWESOME:
            self.cal_btn.setIcon(qta.icon("fa5s.chevron-down", color=Styles.COLOR_TEXT_SECONDARY))
        else:
            self.cal_btn.setText("📅")

        self.cal_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-left: none;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_SURFACE};
                border-color: {Styles.COLOR_ACCENT};
            }}
        """)

        layout.addWidget(self.display, 1)
        layout.addWidget(self.cal_btn)

        # Connect click handlers
        self.display.mousePressEvent = lambda e: self.show_calendar()
        self.cal_btn.clicked.connect(self.show_calendar)

    def show_calendar(self):
        """Open custom popup menu containing styled QCalendarWidget."""
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 10px;
                padding: 6px;
            }}
        """)

        calendar = QCalendarWidget()
        calendar.setGridVisible(False)
        calendar.setSelectedDate(self._current_date)
        calendar.setNavigationBarVisible(True)

        calendar.setStyleSheet(f"""
            QCalendarWidget QWidget {{
                background-color: {Styles.COLOR_SURFACE};
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 12px;
            }}
            QCalendarWidget QAbstractItemView:enabled {{
                color: {Styles.COLOR_TEXT_PRIMARY};
                background-color: {Styles.COLOR_SURFACE};
                selection-background-color: {Styles.COLOR_ACCENT};
                selection-color: white;
                border-radius: 6px;
            }}
            QCalendarWidget QToolButton {{
                color: {Styles.COLOR_TEXT_PRIMARY};
                background-color: transparent;
                border: none;
                font-weight: bold;
                padding: 4px;
            }}
            QCalendarWidget QToolButton:hover {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border-radius: 4px;
            }}
            QCalendarWidget QMenu {{
                background-color: {Styles.COLOR_SURFACE};
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
            QCalendarWidget QSpinBox {{
                color: {Styles.COLOR_TEXT_PRIMARY};
                background-color: {Styles.COLOR_SURFACE_LIGHT};
            }}
        """)

        def on_date_selected(date):
            self.setDate(date)
            menu.close()

        calendar.clicked.connect(on_date_selected)

        action = QWidgetAction(menu)
        action.setDefaultWidget(calendar)
        menu.addAction(action)

        pos = self.mapToGlobal(self.rect().bottomLeft())
        menu.exec(pos)

    def date(self) -> QDate:
        return self._current_date

    def setDate(self, date: QDate):
        if date != self._current_date:
            self._current_date = date
            self.display.setText(date.toString("yyyy-MM-dd"))
            self.dateChanged.emit(date)

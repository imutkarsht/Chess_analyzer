"""
Modern Date Picker Widget - An ultra-sleek, unified desktop date picker with custom calendar popup.
"""
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QCalendarWidget, QMenu, QWidgetAction, QFrame, QPushButton, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import pyqtSignal, Qt, QDate
from PyQt6.QtGui import QColor
from ..styles import Styles

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False


class ModernDatePicker(QFrame):
    """An ultra-sleek, unified desktop date picker component."""

    dateChanged = pyqtSignal(QDate)

    def __init__(self, parent=None, initial_date: QDate = None):
        super().__init__(parent)
        self._current_date = initial_date or QDate.currentDate()
        self.setObjectName("DatePickerContainer")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(38)

        # Outer unified layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        # 1. Calendar Leading Icon
        self.icon_label = QLabel()
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        if HAS_QTAWESOME:
            self.icon_label.setPixmap(qta.icon("fa5s.calendar-alt", color=Styles.COLOR_TEXT_SECONDARY).pixmap(15, 15))
        else:
            self.icon_label.setText("📅")
            self.icon_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 13px; background: transparent; border: none;")
        layout.addWidget(self.icon_label)

        # 2. Date Text Label
        self.date_label = QLabel(self._current_date.toString("yyyy-MM-dd"))
        self.date_label.setStyleSheet(f"""
            QLabel {{
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 600;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(self.date_label, 1)

        # 3. Trailing Chevron Indicator
        self.chevron_label = QLabel()
        self.chevron_label.setStyleSheet("background: transparent; border: none;")
        if HAS_QTAWESOME:
            self.chevron_label.setPixmap(qta.icon("fa5s.chevron-down", color=Styles.COLOR_TEXT_MUTED).pixmap(12, 12))
        else:
            self.chevron_label.setText("▼")
            self.chevron_label.setStyleSheet(f"color: {Styles.COLOR_TEXT_MUTED}; font-size: 10px; background: transparent; border: none;")
        layout.addWidget(self.chevron_label)

        self._apply_container_style()

    def _apply_container_style(self):
        self.setStyleSheet(f"""
            QFrame#DatePickerContainer {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 8px;
            }}
            QFrame#DatePickerContainer:hover {{
                background-color: {Styles.COLOR_SURFACE};
                border-color: {Styles.COLOR_ACCENT};
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.show_calendar()
        super().mousePressEvent(event)

    def show_calendar(self):
        """Open custom styled calendar popup menu."""
        menu = QMenu(self)
        menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.FramelessWindowHint)
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 12px;
                padding: 8px;
            }}
        """)

        # Main popup layout box
        box = QWidget()
        box.setStyleSheet(f"background-color: {Styles.COLOR_SURFACE}; border-radius: 12px;")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(4, 4, 4, 4)
        box_layout.setSpacing(8)

        # Styled QCalendarWidget
        calendar = QCalendarWidget()
        calendar.setGridVisible(False)
        calendar.setSelectedDate(self._current_date)
        calendar.setNavigationBarVisible(True)
        calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)

        calendar.setStyleSheet(f"""
            QCalendarWidget {{
                background-color: {Styles.COLOR_SURFACE};
                border: none;
            }}
            QCalendarWidget QWidget#qt_calendar_navigationbar {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                border-radius: 8px;
                padding: 4px;
            }}
            QCalendarWidget QToolButton {{
                color: {Styles.COLOR_TEXT_PRIMARY};
                background-color: transparent;
                border: none;
                border-radius: 4px;
                font-weight: 700;
                font-size: 13px;
                padding: 4px 8px;
            }}
            QCalendarWidget QToolButton:hover {{
                background-color: {Styles.COLOR_SURFACE};
                color: {Styles.COLOR_ACCENT};
            }}
            QCalendarWidget QToolButton::menu-indicator {{
                image: none;
                width: 0px;
            }}
            QCalendarWidget QAbstractItemView:enabled {{
                color: {Styles.COLOR_TEXT_PRIMARY};
                background-color: {Styles.COLOR_SURFACE};
                selection-background-color: {Styles.COLOR_ACCENT};
                selection-color: {Styles.COLOR_TEXT_PRIMARY};
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
                outline: none;
            }}
            QCalendarWidget QAbstractItemView:disabled {{
                color: {Styles.COLOR_TEXT_MUTED};
            }}
            QCalendarWidget QSpinBox {{
                color: {Styles.COLOR_TEXT_PRIMARY};
                background-color: {Styles.COLOR_SURFACE};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 4px;
                font-size: 12px;
            }}
        """)

        box_layout.addWidget(calendar)

        # Bottom Bar: "Today" shortcut button
        today_btn = QPushButton("Today")
        today_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        today_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_ACCENT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border-color: {Styles.COLOR_ACCENT};
            }}
        """)

        def on_today_clicked():
            today = QDate.currentDate()
            calendar.setSelectedDate(today)
            on_date_selected(today)

        today_btn.clicked.connect(on_today_clicked)
        box_layout.addWidget(today_btn, 0, Qt.AlignmentFlag.AlignRight)

        def on_date_selected(date):
            self.setDate(date)
            menu.close()

        calendar.clicked.connect(on_date_selected)

        action = QWidgetAction(menu)
        action.setDefaultWidget(box)
        menu.addAction(action)

        pos = self.mapToGlobal(self.rect().bottomLeft())
        menu.exec(pos)

    def date(self) -> QDate:
        return self._current_date

    def setDate(self, date: QDate):
        if date != self._current_date:
            self._current_date = date
            self.date_label.setText(date.toString("yyyy-MM-dd"))
            self.dateChanged.emit(date)

# SPDX-License-Identifier: GPL-3.0-only
"""Text input, textarea, select, and date-picker QSS."""

from __future__ import annotations

from src.gui.theme import ThemeManager


class _InputMixin:
    MONO_FONT_FAMILY = "'SF Mono', 'JetBrains Mono', 'Consolas', monospace"

    @classmethod
    def get_date_picker_input_qss(cls, *, font_size: int = 14) -> str:
        """Transparent editor that sits inside the painted date-picker field."""
        p = ThemeManager.palette()
        return f"""
            QLineEdit {{
                background: transparent;
                border: none;
                color: {p.text_primary};
                font-size: {font_size}px;
                selection-background-color: {p.accent};
                selection-color: {cls.COLOR_ON_ACCENT};
            }}
            QLineEdit:disabled {{
                color: {p.text_muted};
            }}
        """

    @classmethod
    def get_date_picker_popup_qss(cls) -> str:
        """Panel, weekday, and year labels for the calendar popup."""
        p = ThemeManager.palette()
        return f"""
            QFrame#DatePickerPopup {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 14px;
            }}
            QLabel#DatePickerWeekday {{
                color: {p.text_muted};
                background: transparent;
                font-size: 11px;
                font-weight: 600;
            }}
            QLabel#DatePickerYear {{
                color: {p.text_primary};
                background: transparent;
                font-size: 16px;
                font-weight: 600;
            }}
        """

    @classmethod
    def get_select_popup_style(cls):
        """Chrome for :class:`~src.gui.components.controls.select.Select`'s popup.

        The panel background and border are painted by the component (a
        translucent top-level window), so this only styles the scroll area.
        """
        p = ThemeManager.palette()
        return f"""
            QFrame#SelectPopup QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QFrame#SelectPopup QWidget#SelectPopupContent {{
                background-color: transparent;
            }}
            QFrame#SelectPopup QScrollBar:vertical {{
                background-color: transparent;
                width: 8px;
                margin: 2px;
                border-radius: 4px;
            }}
            QFrame#SelectPopup QScrollBar::handle:vertical {{
                background-color: {p.border_light};
                min-height: 24px;
                border-radius: 4px;
            }}
            QFrame#SelectPopup QScrollBar::handle:vertical:hover {{
                background-color: {p.text_muted};
            }}
            QFrame#SelectPopup QScrollBar::add-line:vertical,
            QFrame#SelectPopup QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QFrame#SelectPopup QScrollBar::add-page:vertical,
            QFrame#SelectPopup QScrollBar::sub-page:vertical {{
                background-color: transparent;
            }}
        """

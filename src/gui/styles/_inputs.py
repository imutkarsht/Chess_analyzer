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
    def get_input_qss(
        cls,
        *,
        selector: str = "QLineEdit",
        variant: str = "default",
        height: int = 34,
        font_size: int = 13,
        padding_h: int = 10,
        radius: int = 8,
        monospace: bool = False,
    ) -> str:
        """Chrome for every single-line editor in the app.

        Rendering is driven by :class:`~src.gui.components.controls.input.Input`; this
        generator is the only place the look is defined. Variants change only
        the resting surface (``search`` is the filled filter bar); hover,
        focus, disabled and invalid states stay identical everywhere so a
        field never behaves differently depending on which panel hosts it.

        ``selector`` lets the numeric editors reuse the exact same rules.
        """
        p = ThemeManager.palette()
        background = p.surface_light if variant == "search" else p.surface
        family = f"font-family: {cls.MONO_FONT_FAMILY};" if monospace else ""
        return f"""
            {selector} {{
                background-color: {background};
                border: 1px solid {p.border};
                border-radius: {radius}px;
                padding: 0 {padding_h}px;
                color: {p.text_primary};
                font-size: {font_size}px;
                {family}
                selection-background-color: {p.accent};
                selection-color: {cls.COLOR_ON_ACCENT};
                min-height: {height}px;
                max-height: {height}px;
            }}
            {selector}:hover {{
                border-color: {p.border_light};
            }}
            {selector}:focus {{
                border-color: {p.accent};
            }}
            {selector}:disabled {{
                background-color: {p.surface_light};
                color: {p.text_muted};
                border-color: {p.border};
            }}
            {selector}[invalid="true"],
            {selector}[invalid="true"]:hover,
            {selector}[invalid="true"]:focus {{
                border-color: {cls.COLOR_BLUNDER};
            }}
        """

    @classmethod
    def get_textarea_qss(
        cls,
        *,
        variant: str = "default",
        font_size: int = 13,
        padding: int = 12,
        radius: int = 8,
    ) -> str:
        """Chrome for every multi-line editor.

        ``code`` is the monospace variant (PGN, logs); ``flat`` is the
        borderless read-only prose surface used inside existing cards.
        """
        p = ThemeManager.palette()
        if variant == "flat":
            background, border = "transparent", "none"
            padding_value, color = 0, p.text_secondary
        else:
            background, border = p.surface, f"1px solid {p.border}"
            padding_value, color = padding, p.text_primary
        family = (
            f"font-family: {cls.MONO_FONT_FAMILY};"
            if variant == "code"
            else ""
        )
        interaction = ""
        if variant != "flat":
            interaction = f"""
            QTextEdit:hover {{
                border-color: {p.border_light};
            }}
            QTextEdit:focus {{
                border-color: {p.accent};
            }}
            QTextEdit[invalid="true"],
            QTextEdit[invalid="true"]:hover,
            QTextEdit[invalid="true"]:focus {{
                border-color: {cls.COLOR_BLUNDER};
            }}
            QTextEdit:disabled {{
                color: {p.text_muted};
            }}
            """
        return f"""
            QTextEdit {{
                background-color: {background};
                border: {border};
                border-radius: {radius}px;
                padding: {padding_value}px;
                color: {color};
                font-size: {font_size}px;
                {family}
                selection-background-color: {p.accent};
                selection-color: {cls.COLOR_ON_ACCENT};
            }}
            {interaction}
            QScrollBar:vertical {{
                background-color: transparent;
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {p.border};
                min-height: 24px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {p.border_light};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background-color: transparent;
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

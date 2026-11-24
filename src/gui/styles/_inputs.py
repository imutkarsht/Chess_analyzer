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



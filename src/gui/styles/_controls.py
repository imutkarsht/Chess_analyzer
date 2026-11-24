# SPDX-License-Identifier: GPL-3.0-only
"""Checkbox, radio, slider, theme-card, and related control QSS."""

from __future__ import annotations

from src.gui.theme import ThemeManager


class _ControlsMixin:
    @classmethod
    def get_board_swatch_button_style(cls):
        p = ThemeManager.palette()
        return f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {p.border};
                border-radius: 8px;
                padding: 2px;
            }}
            QPushButton:hover {{
                border-color: {p.text_muted};
            }}
            QPushButton:checked {{
                border: 2px solid {p.accent};
            }}
        """

    @classmethod
    def get_theme_card_button_style(cls):
        p = ThemeManager.palette()
        return f"""
            QToolButton {{
                background-color: {p.surface_card};
                color: {p.text_primary};
                border: 1px solid {p.border};
                border-radius: 10px;
                padding: 6px;
                font-size: 11px;
                font-weight: 600;
            }}
            QToolButton:hover {{
                border-color: {p.text_muted};
            }}
            QToolButton:checked {{
                border: 2px solid {p.accent};
            }}
        """


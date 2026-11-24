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

    @classmethod
    def get_nav_list_style(cls):
        p = ThemeManager.palette()
        return f"""
            QListWidget {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                padding: 11px 14px;
                margin: 1px 0;
                border-radius: 8px;
                color: {p.text_secondary};
                font-size: 15px;
                font-weight: 500;
            }}
            QListWidget::item:hover {{
                background-color: {p.surface_light};
                color: {p.text_primary};
            }}
            QListWidget::item:selected {{
                background-color: {p.surface_light};
                color: {p.accent};
                border-left: 2px solid {p.accent};
                font-weight: 600;
            }}
        """

    @classmethod
    def get_group_box_style(cls):
        p = ThemeManager.palette()
        return f"""
            QGroupBox {{
                font-size: 17px;
                font-weight: 600;
                color: {p.text_primary};
                border: none;
                border-radius: 0;
                margin-top: 18px;
                padding: 6px 0 0 0;
                background-color: transparent;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 0px;
                padding: 0 0 6px 0;
                color: {p.text_primary};
            }}
        """

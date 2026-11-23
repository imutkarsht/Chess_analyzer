# SPDX-License-Identifier: GPL-3.0-only
"""Checkbox, radio, slider, theme-card, and related control QSS."""

from __future__ import annotations

from src.gui.theme import ThemeManager


class _ControlsMixin:
    @classmethod
    def get_checkbox_style(cls, tick_path):
        p = ThemeManager.palette()
        return f"""
            QCheckBox {{
                color: {p.text_primary};
                font-weight: 600;
                font-size: 12px;
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 8px;
                padding: 6px 12px;
                spacing: 8px;
            }}
            QCheckBox:hover {{
                background-color: {p.surface_light};
                border-color: {p.border_light};
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {p.border};
                border-radius: 4px;
                background-color: {p.surface_light};
            }}
            QCheckBox::indicator:hover {{
                border-color: {p.accent};
            }}
            QCheckBox::indicator:checked {{
                background-color: {p.accent};
                border-color: {p.accent};
                image: url('{tick_path}');
            }}
        """

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
    def get_settings_checkbox_style(cls, tick_path):
        """Borderless checkbox style for settings rows.

        Checked and unchecked states share the same box (size, radius, border)
        so toggles read as one control in every card.
        """
        p = ThemeManager.palette()
        return cls._flat_checkbox_style(
            tick_path, text_color=p.text_primary, font_size=13
        )

    @classmethod
    def get_compact_checkbox_style(cls, tick_path):
        """Dense flat checkbox used by Explorer and feedback panels."""
        p = ThemeManager.palette()
        return cls._flat_checkbox_style(
            tick_path, text_color=p.text_secondary, font_size=12
        )

    @classmethod
    def _flat_checkbox_style(cls, tick_path, *, text_color: str, font_size: int):
        p = ThemeManager.palette()
        return f"""
            QCheckBox {{
                color: {text_color};
                font-weight: 500;
                font-size: {font_size}px;
                background: transparent;
                border: none;
                padding: 0px;
                spacing: 8px;
            }}
            QCheckBox:hover {{
                color: {p.text_primary};
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid {p.border_light};
                border-radius: 4px;
                background-color: {p.surface};
            }}
            QCheckBox::indicator:hover {{
                border-color: {p.accent};
            }}
            QCheckBox::indicator:checked {{
                background-color: {p.accent};
                border-color: {p.accent};
                image: url('{tick_path}');
            }}
            QCheckBox::indicator:checked:hover {{
                background-color: {p.accent_hover};
                border-color: {p.accent_hover};
            }}
            QCheckBox::indicator:disabled {{
                border-color: {p.border};
                background-color: {p.surface_light};
            }}
        """

    @classmethod
    def get_radio_group_style(cls):
        p = ThemeManager.palette()
        return f"""
            QRadioButton {{
                color: {p.text_primary};
                font-size: 13px;
                spacing: 8px;
                padding: 4px 0;
            }}
            QRadioButton::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid {p.border};
                border-radius: 10px;
                background: {p.surface_light};
            }}
            QRadioButton::indicator:checked {{
                background: {p.accent};
                border-color: {p.accent};
            }}
            QRadioButton::indicator:hover {{
                border-color: {p.accent};
            }}
        """

    @classmethod
    def get_slider_style(cls):
        p = ThemeManager.palette()
        return f"""
            QSlider::groove:horizontal {{
                height: 6px;
                background: {p.border};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {p.accent};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {p.text_primary};
                width: 16px;
                height: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {p.accent_hover};
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

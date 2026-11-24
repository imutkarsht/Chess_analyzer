# SPDX-License-Identifier: GPL-3.0-only
"""Global theme, cards, frames, dialogs, badges, and transparent helpers."""

from __future__ import annotations

from src.gui.theme import ThemeManager


class _SurfaceMixin:
    @classmethod
    def get_theme(cls):
        p = ThemeManager.palette()
        return f"""
            QMainWindow, QWidget {{
                background-color: {p.background};
                color: {p.text_primary};
                font-family: 'SF Pro', 'Inter', 'Segoe UI', 'Roboto', sans-serif;
                font-size: 14px;
            }}

            QFrame, QSplitter::handle {{
                background-color: {p.surface};
            }}

            QSplitter::handle {{
                width: 3px;
                background-color: {p.border};
            }}
            QSplitter::handle:hover {{
                background-color: {p.accent};
            }}

            QTableWidget {{
                background-color: {p.surface};
                gridline-color: transparent;
                border: 1px solid {p.border};
                border-radius: 8px;
                selection-background-color: {p.highlight};
                selection-color: {p.text_primary};
            }}

            QTableWidget::item {{
                color: {p.text_primary};
                padding: 10px 8px;
                border-bottom: 1px solid {p.surface_light};
            }}

            QTableWidget::item:hover {{
                background-color: {p.surface_light};
            }}

            QTableWidget::item:selected {{
                background-color: {p.highlight};
                border-left: 3px solid {p.accent};
            }}

            QHeaderView::section {{
                background-color: {p.surface_light};
                color: {p.text_primary};
                padding: 8px;
                border: none;
                border-bottom: 2px solid {p.accent};
                font-weight: 600;
                font-size: 13px;
            }}

            QListWidget {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 8px;
                padding: 6px;
            }}

            QListWidget::item {{
                padding: 10px 12px;
                border-radius: 6px;
                margin: 2px 0;
            }}

            QListWidget::item:hover {{
                background-color: {p.surface_light};
            }}

            QListWidget::item:selected {{
                background-color: {p.accent};
                color: white;
            }}

            QLabel {{
                color: {p.text_primary};
                background: transparent;
            }}

            QScrollBar:vertical {{
                border: none;
                background: {p.background};
                width: 8px;
                margin: 4px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {p.border};
                min-height: 30px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {p.border_light};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}

            QScrollBar:horizontal {{
                border: none;
                background: {p.background};
                height: 8px;
                margin: 2px 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: {p.border};
                min-width: 30px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {p.border_light};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}

            QToolTip {{
                background-color: {p.surface_light};
                color: {p.text_primary};
                border: 1px solid {p.border};
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
            }}
        """

    @classmethod
    def get_badge_style(cls, size=11):
        p = ThemeManager.palette()
        return f"""
            QLabel {{
                color: {p.text_muted};
                font-size: {size}px;
                font-family: monospace;
                font-weight: 600;
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 6px;
                padding: 2px 6px;
            }}
        """

    @classmethod
    def get_eval_badge_style(cls, bg_color, text_color):
        return f"""
            QLabel {{
                background-color: {bg_color};
                color: {text_color};
                border-radius: 6px;
                padding: 3px 8px;
                font-weight: bold;
                font-family: monospace;
                font-size: 12px;
            }}
        """

    @classmethod
    def get_result_badge_style(cls, color, font_size=12, padding="2px 8px", border_radius=4):
        p = ThemeManager.palette()
        return f"""
            QLabel {{
                color: {color};
                font-weight: bold;
                font-size: {font_size}px;
                padding: {padding};
                background-color: {p.surface_light};
                border: 1px solid {p.border};
                border-radius: {border_radius}px;
            }}
        """

    @classmethod
    def get_card_style(cls, border_radius=12):
        p = ThemeManager.palette()
        return f"""
            QFrame {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: {border_radius}px;
            }}
            QFrame QLabel {{
                background: transparent;
                border: none;
            }}
            QFrame:hover {{
                border: 1px solid {p.accent};
                background-color: {p.surface_light};
            }}
        """

    @classmethod
    def get_frame_style(cls, border_radius=12, hover_accent=True, object_name=None):
        p = ThemeManager.palette()
        selector = f"QFrame#{object_name}" if object_name else "QFrame"
        hover_style = (
            f"""
            {selector}:hover {{
                border: 1px solid {p.accent};
            }}
        """
            if hover_accent
            else ""
        )

        return f"""
            {selector} {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: {border_radius}px;
            }}
            {selector} QLabel {{
                background: transparent;
                border: none;
            }}
            {hover_style}
        """

    @classmethod
    def get_dialog_surface_style(cls):
        p = ThemeManager.palette()
        return f"""
            background-color: {p.surface};
            border: 1px solid {p.border};
            border-radius: 12px;
        """

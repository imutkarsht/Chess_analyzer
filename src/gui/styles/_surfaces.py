# SPDX-License-Identifier: GPL-3.0-only
"""Global theme, cards, frames, dialogs, badges, and transparent helpers."""

from __future__ import annotations

from src.gui.theme import ThemeManager


class _SurfaceMixin:
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
    def get_dialog_surface_style(cls):
        p = ThemeManager.palette()
        return f"""
            background-color: {p.surface};
            border: 1px solid {p.border};
            border-radius: 12px;
        """

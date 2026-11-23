# SPDX-License-Identifier: GPL-3.0-only
"""Progress-bar and think-time-bar QSS."""

from __future__ import annotations

from src.gui.theme import ThemeManager


class _ProgressMixin:
    @classmethod
    def get_progress_bar_style(cls):
        p = ThemeManager.palette()
        return f"""
            QProgressBar {{
                border: 2px solid {p.border};
                border-radius: 5px;
                background-color: {p.surface};
                text-align: center;
                color: {p.text_primary};
                font-size: 12px;
                font-weight: bold;
                min-height: 22px;
            }}
            QProgressBar::chunk {{
                background-color: {p.accent};
                border-radius: 3px;
            }}
        """

    @classmethod
    def get_thin_progress_bar_style(cls):
        """Slim accent-only bar for update and splash progress."""
        p = ThemeManager.palette()
        return f"""
            QProgressBar {{
                border: none;
                border-radius: 3px;
                background-color: {p.surface_light};
            }}
            QProgressBar::chunk {{
                background-color: {p.accent};
                border-radius: 3px;
            }}
        """

    @classmethod
    def get_think_time_bar_style(cls, colour, track, ratio):
        return f"""
            QLabel {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {colour},
                    stop:{ratio:.4f} {colour},
                    stop:{ratio:.4f} {track},
                    stop:1 {track}
                );
                border: none;
                border-radius: 1px;
            }}
        """

# SPDX-License-Identifier: GPL-3.0-only
"""Progress-bar and think-time-bar QSS."""

from __future__ import annotations


class _ProgressMixin:
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

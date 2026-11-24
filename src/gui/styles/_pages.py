# SPDX-License-Identifier: GPL-3.0-only
"""Analysis-page QSS: board chrome, variation graph, captured pieces, clocks."""

from __future__ import annotations


class _PagesMixin:
    CAPTURED_PIECES_STYLE = """
        QLabel {
            font-size: 16px;
            font-weight: bold;
            padding: 2px;
        }
    """

    @classmethod
    def get_captured_pieces_style(cls):
        return f"""
            QFrame {{
                background: transparent;
                border: none;
                padding: 0px;
            }}
            {cls.CAPTURED_PIECES_STYLE}
        """

    @classmethod
    def get_digital_clock_style(cls, bg, fg, border, compact=True):
        font_size = 16 if compact else 18
        padding = "3px 8px" if compact else "4px 10px"
        radius = 6 if compact else 7
        return f"""
            QLabel {{
                color: {fg};
                background-color: {bg};
                font-family: 'Courier New', 'Monospace', monospace;
                font-size: {font_size}px;
                font-weight: bold;
                padding: {padding};
                border-radius: {radius}px;
                border: 1px solid {border};
            }}
        """

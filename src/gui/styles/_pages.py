# SPDX-License-Identifier: GPL-3.0-only
"""Analysis-page QSS: board chrome, variation graph, captured pieces, clocks."""

from __future__ import annotations

from src.gui.theme import ThemeManager


class _PagesMixin:
    @classmethod
    def get_board_controls_style(cls):
        p = ThemeManager.palette()
        return f"""
            QWidget#BoardControls {{
                background: transparent;
                border: none;
                border-top: 1px solid {p.border};
            }}
        """

    @classmethod
    def get_variation_graph_style(cls):
        p = ThemeManager.palette()
        return f"""
            QFrame#VariationGraph {{
                background-color: {p.surface_light};
                border: 1px solid {p.border};
                border-radius: 8px;
            }}
            QFrame#VariationGraph QLabel {{
                background: transparent;
                border: none;
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
        """

    @classmethod
    def get_variation_node_style(cls, color, active=False, ghost=False):
        p = ThemeManager.palette()
        if ghost:
            background = p.surface
            border = f"1px dashed {color}"
            text = p.text_muted
        elif active:
            background = p.accent_subtle
            border = f"2px solid {color}"
            text = p.text_primary
        else:
            background = p.surface_card
            border = f"1px solid {color}"
            text = p.text_primary
        return f"""
            QPushButton {{
                background-color: {background};
                color: {text};
                border: {border};
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
                padding: 0px 4px;
            }}
            QPushButton:hover {{
                background-color: {p.accent_subtle};
            }}
        """

    @classmethod
    def get_variation_branch_chip_style(cls, color, active=False):
        p = ThemeManager.palette()
        background = p.accent_subtle if active else p.surface_card
        return f"""
            QFrame#BranchChip {{
                background-color: {background};
                border: 1px solid {color};
                border-radius: 6px;
            }}
            QFrame#BranchChip QLabel {{
                color: {p.text_primary if active else p.text_secondary};
                background: transparent;
                border: none;
                font-size: 10px;
                font-weight: 600;
            }}
            QFrame#BranchChip QToolButton {{
                color: {p.text_muted};
                background: transparent;
                border: none;
                font-size: 11px;
                padding: 0px;
            }}
            QFrame#BranchChip QToolButton:hover {{
                color: {p.text_primary};
            }}
        """

    @classmethod
    def get_variation_badge_style(cls):
        p = ThemeManager.palette()
        return f"""
            QToolButton {{
                background-color: {p.accent_subtle};
                color: {p.accent};
                border: 1px solid {p.accent};
                border-radius: 5px;
                font-size: 10px;
                font-weight: 700;
                padding: 0px;
            }}
            QToolButton:hover {{
                background-color: {p.accent};
                color: #FFFFFF;
            }}
        """

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

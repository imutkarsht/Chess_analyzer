# SPDX-License-Identifier: GPL-3.0-only
"""Explorer, import, batch, move-list, and game-card table QSS."""

from __future__ import annotations

from src.gui.theme import ThemeManager


class _TableMixin:
    @classmethod
    def get_explorer_table_style(cls):
        p = ThemeManager.palette()
        return f"""
            QTableWidget {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 8px;
                gridline-color: transparent;
                font-size: 14px;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
                border-bottom: 1px solid {p.surface_light};
            }}
            QTableWidget::item:hover {{
                background-color: {p.surface_light};
            }}
            QTableWidget::item:selected {{
                background-color: {p.highlight};
                color: {p.text_primary};
                border-left: 3px solid {p.accent};
            }}
            QHeaderView::section {{
                background-color: {p.surface_light};
                color: {p.text_secondary};
                padding: 6px;
                border: none;
                border-bottom: 2px solid {p.accent};
                font-weight: 600;
                font-size: 13px;
            }}
        """

    @classmethod
    def get_import_action_bar_style(cls):
        p = ThemeManager.palette()
        return f"""
            QFrame#ImportActionBar {{
                background-color: transparent;
                border-top: 1px solid {p.border};
            }}
        """

    @classmethod
    def get_batch_selection_bar_style(cls):
        p = ThemeManager.palette()
        return f"""
            QFrame#BatchSelectionBar {{
                background-color: {p.surface_light};
                border: 1px solid {p.border};
                border-radius: 10px;
            }}
            QFrame#BatchSelectionBar QLabel {{
                background: transparent;
                border: none;
            }}
        """

    @classmethod
    def get_batch_queue_card_style(cls):
        p = ThemeManager.palette()
        return f"""
            QFrame#BatchQueueCard {{
                background-color: {p.surface_card};
                border: 1px solid {p.border};
                border-left: 3px solid {p.accent};
                border-radius: 12px;
            }}
            QFrame#BatchQueueCard QLabel {{
                background: transparent;
                border: none;
            }}
        """

    @classmethod
    def get_batch_stat_tile_style(cls):
        p = ThemeManager.palette()
        return f"""
            QFrame#BatchStatTile {{
                background-color: {p.surface_light};
                border: 1px solid {p.border};
                border-radius: 8px;
            }}
            QFrame#BatchStatTile QLabel {{
                background: transparent;
                border: none;
            }}
        """

    @classmethod
    def get_batch_current_game_style(cls):
        p = ThemeManager.palette()
        return f"""
            QFrame#BatchCurrentGame {{
                background-color: {p.surface_light};
                border: 1px solid {p.accent};
                border-radius: 10px;
            }}
            QFrame#BatchCurrentGame QLabel {{
                background: transparent;
                border: none;
            }}
        """

    @classmethod
    def get_batch_up_next_style(cls):
        p = ThemeManager.palette()
        return f"""
            QListWidget#BatchUpNextList {{
                background-color: {p.surface_light};
                border: 1px solid {p.border};
                border-radius: 8px;
                outline: none;
            }}
            QListWidget#BatchUpNextList::item {{
                background: transparent;
                border-bottom: 1px solid {p.border};
                padding: 0px;
            }}
            QListWidget#BatchUpNextList::item:selected {{
                background-color: {p.surface};
            }}
            QListWidget#BatchUpNextList::item:hover {{
                background-color: {p.surface};
            }}
        """

    @classmethod
    def get_filter_chip_style(cls):
        p = ThemeManager.palette()
        return f"""
            QFrame#FilterChip {{
                background-color: {p.surface_light};
                border: 1px solid {p.border};
                border-radius: 8px;
            }}
            QFrame#FilterChip:hover {{
                background-color: {p.surface};
                border-color: {p.accent};
            }}
        """

    @classmethod
    def get_history_filter_panel_style(cls):
        p = ThemeManager.palette()
        return f"""
            QFrame#HistoryFilterPanel {{
                background-color: {p.surface_card};
                border: 1px solid {p.border};
                border-radius: 10px;
            }}
            QFrame#HistoryFilterPanel QLabel {{
                background: transparent;
                border: none;
            }}
        """

    @classmethod
    def get_import_table_style(cls):
        p = ThemeManager.palette()
        return f"""
            QTableView {{
                background-color: {p.background};
                color: {p.text_primary};
                border: none;
                gridline-color: transparent;
                font-size: 13px;
                selection-background-color: {p.accent_subtle};
                selection-color: {p.text_primary};
            }}
            QTableView QWidget#qt_scrollarea_viewport {{
                background-color: {p.background};
            }}
            QTableView::item {{
                padding: 0 10px;
                border-bottom: 1px solid {p.border};
            }}
            QTableView::item:hover {{
                background-color: {p.surface_light};
            }}
            QTableView::item:selected {{
                background-color: {p.accent_subtle};
                color: {p.text_primary};
            }}
            QHeaderView::section {{
                background-color: {p.background};
                color: {p.text_secondary};
                padding: 0 10px;
                border: none;
                border-bottom: 1px solid {p.border};
                font-weight: 600;
                font-size: 12px;
            }}
            QTableCornerButton::section {{
                background-color: {p.background};
                border: none;
            }}
            QTableView QScrollBar:vertical {{
                background: transparent;
                width: 10px;
                margin: 0;
            }}
            QTableView QScrollBar::handle:vertical {{
                background: {p.border};
                border-radius: 5px;
                min-height: 24px;
            }}
            QTableView QScrollBar::handle:vertical:hover {{
                background: {p.text_muted};
            }}
            QTableView QScrollBar::add-line:vertical,
            QTableView QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QTableView QScrollBar::add-page:vertical,
            QTableView QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """

    @classmethod
    def get_move_list_card_style(cls):
        p = ThemeManager.palette()
        return f"""
            QFrame#MoveListCard {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 12px;
            }}
        """

    @classmethod
    def get_move_list_table_style(cls):
        p = ThemeManager.palette()
        return f"""
            QTableWidget {{
                background: transparent;
                border: none;
                gridline-color: transparent;
                font-size: 13px;
                selection-background-color: transparent;
            }}
            QTableWidget QWidget#qt_scrollarea_viewport {{
                background: transparent;
            }}
            QTableWidget::item {{
                padding: 0px 0px 0px 10px;
                border: none;
                border-bottom: 1px solid {p.surface_light};
            }}
            QTableWidget::item:hover {{
                background: transparent;
            }}
            QTableWidget::item:selected {{
                background: transparent;
                color: {p.text_primary};
            }}
            QHeaderView {{
                background: transparent;
            }}
            QHeaderView::section {{
                background: transparent;
                color: {p.text_secondary};
                padding: 8px 10px 8px 12px;
                border: none;
                border-bottom: 1px solid {p.border};
                font-weight: 600;
                font-size: 11px;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 4px 2px 4px 0px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {p.border};
                min-height: 20px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {p.border_light};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                background: none;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """

    @classmethod
    def get_game_card_style(cls, border_radius=10, compact=False, selected=False):
        p = ThemeManager.palette()
        hover_bg = f"background-color: {p.surface};" if compact else ""
        card_padding = "10px 14px" if compact else "8px 14px"
        background = p.surface_light if selected else p.surface_card
        border = p.accent if selected else p.border
        return f"""
            QFrame#GameCard {{
                background-color: {background};
                border: 1px solid {border};
                border-radius: {border_radius}px;
                padding: {card_padding};
            }}
            QFrame#GameCard:hover {{
                {hover_bg}
                border-color: {p.accent};
            }}
            QFrame#GameCard QLabel {{
                background: transparent;
                border: none;
            }}
        """

    @classmethod
    def get_book_row_style(cls):
        p = ThemeManager.palette()
        return f"""
            QWidget#BookRow {{
                border-bottom: 1px solid {p.border};
            }}
            QWidget#BookRow QLabel {{
                background: transparent;
                border: none;
            }}
            QWidget#BookRow:hover {{
                background-color: {p.surface_light};
            }}
        """

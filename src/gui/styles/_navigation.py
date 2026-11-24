# SPDX-License-Identifier: GPL-3.0-only
"""Tabs, sidebar, menus, scroll areas, splitters, and layout chrome."""

from __future__ import annotations

from src.gui.styles._base import ON_ACCENT
from src.gui.theme import ThemeManager


class _NavigationMixin:
    @classmethod
    def get_tabs_style(
        cls,
        *,
        variant: str = "underline",
        spacing: int = 24,
        padding: tuple[int, int, int, int] = (8, 18, 10, 18),
        font_size: int = 15,
        font_weight: int = 600,
        radius: int = 8,
        track: bool = False,
        track_padding: int = 4,
        active_style: str = "filled",
        indicator_size: int = 3,
        accent: str | None = None,
    ) -> str:
        """Stylesheet for ``src.gui.components.controls.tabs.Tabs``.

        One generator backs both looks: ``underline`` draws an accent bar under
        the active label, ``segmented`` renders button-like segments that either
        sit in a rounded ``#TabTrack`` container or float as detached pills.
        Rules are scoped to ``#TabTrack`` so a nested tab bar inside a page can
        never inherit an outer bar's look.

        The underline uses the palette accent unless ``accent`` is passed;
        ``active_style="accent"`` also tints the active label, while the default
        ``"underline"`` keeps it in the primary text color.
        """
        p = ThemeManager.palette()
        top, right, bottom, left = padding
        font = f"font-size: {font_size}px; font-weight: {font_weight};"

        if variant == "underline":
            indicator = accent or p.accent
            selected_text = indicator if active_style == "accent" else p.text_primary
            return f"""
                #TabTrack {{
                    background: transparent;
                    border: none;
                }}
                #TabTrack QTabBar {{
                    background: transparent;
                }}
                #TabTrack QTabBar::tab {{
                    background: transparent;
                    color: {p.text_secondary};
                    padding: {top}px {right}px {bottom}px {left}px;
                    margin-right: {spacing}px;
                    border: none;
                    border-bottom: {indicator_size}px solid transparent;
                    border-radius: 0;
                    {font}
                }}
                #TabTrack QTabBar::tab:last {{
                    margin-right: 0;
                }}
                #TabTrack QTabBar::tab:selected {{
                    color: {selected_text};
                    border-bottom: {indicator_size}px solid {indicator};
                }}
                #TabTrack QTabBar::tab:hover:!selected {{
                    color: {p.text_primary};
                }}
                #TabTrack QTabBar::tab:disabled {{
                    color: {p.text_muted};
                }}
            """

        track_rule = """
            #TabTrack {
                background: transparent;
                border: none;
            }
        """
        if track:
            # The active pill is inset by the track padding, so the container
            # radius has to grow by that amount or the corners look pinched.
            track_rule = f"""
                #TabTrack {{
                    background-color: {p.surface};
                    border: 1px solid {p.border};
                    border-radius: {radius + track_padding}px;
                }}
            """
            base_background = "transparent"
            base_border = "1px solid transparent"
        else:
            base_background = p.surface
            base_border = f"1px solid {p.border}"

        selected_border = (accent or p.accent) if active_style == "outline" else p.border_light
        selected_background = p.surface_light
        selected_text = p.text_primary
        if active_style == "accent":
            selected_background = accent or p.accent
            selected_border = selected_background
            selected_text = ON_ACCENT
        return f"""
            {track_rule}
            #TabTrack QTabBar {{
                background: transparent;
            }}
            #TabTrack QTabBar::tab {{
                background-color: {base_background};
                color: {p.text_secondary};
                padding: {top}px {right}px {bottom}px {left}px;
                margin-right: {spacing}px;
                border: {base_border};
                border-radius: {radius}px;
                {font}
            }}
            #TabTrack QTabBar::tab:last {{
                margin-right: 0;
            }}
            #TabTrack QTabBar::tab:selected {{
                background-color: {selected_background};
                color: {selected_text};
                border-color: {selected_border};
            }}
            #TabTrack QTabBar::tab:hover:!selected {{
                background-color: {p.surface_light};
                color: {p.text_primary};
            }}
            #TabTrack QTabBar::tab:disabled {{
                color: {p.text_muted};
            }}
        """

    @classmethod
    def get_header_bar_style(cls):
        p = ThemeManager.palette()
        return f"""
            QWidget {{
                background-color: {p.surface};
                border-bottom: 1px solid {p.border};
            }}
            QWidget QLabel {{
                background: transparent;
                border: none;
            }}
        """

    @classmethod
    def get_header_bar_ext_style(cls, bg_color=None):
        p = ThemeManager.palette()
        bg = bg_color or p.surface
        return f"""
            QFrame {{
                background-color: {bg};
                border-bottom: 1px solid {p.border};
            }}
            QFrame QLabel {{
                background: transparent;
                border: none;
            }}
        """

    @classmethod
    def get_pagination_bar_style(cls):
        p = ThemeManager.palette()
        return f"""
            QWidget#PaginationBar {{
                background-color: {p.surface};
                border-top: 1px solid {p.border};
            }}
        """

    @classmethod
    def get_scroll_area_style(cls):
        p = ThemeManager.palette()
        return f"""
            QScrollArea {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 8px;
            }}
            QScrollBar:vertical {{
                background-color: {p.background};
                width: 10px;
                margin: 0px 0px 0px 0px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {p.border_light};
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """

    @classmethod
    def get_transparent_scroll_area_style(cls):
        p = ThemeManager.palette()
        return f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: transparent;
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {p.border};
                min-height: 24px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {p.border_light};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """

    @classmethod
    def get_splitter_style(cls):
        p = ThemeManager.palette()
        return f"""
            QSplitter {{ background-color: {p.background}; }}
            QSplitter::handle {{ background-color: {p.border}; }}
        """

    @classmethod
    def get_divider_style(cls):
        p = ThemeManager.palette()
        return f"""
            QFrame {{
                background-color: {p.border};
                max-height: 1px;
                border: none;
            }}
        """

    @classmethod
    def apply_background(cls, widget, kind: str = "background") -> None:
        """Apply a page background without cascading into child labels.

        A bare ``background-color`` set on a container also styles every child
        widget and overrides the global transparent-label rule. The property
        selector in the theme template targets only the container itself.
        """
        widget.setProperty("appBackground", kind)
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()

    @classmethod
    def get_sidebar_style(cls):
        p = ThemeManager.palette()
        return f"""
            #Sidebar {{
                background-color: {p.surface};
                border-right: 1px solid {p.border};
            }}
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 10px;
                padding: 12px 16px;
                text-align: left;
                font-size: 14px;
                font-weight: 500;
                color: {p.text_secondary};
            }}
            QPushButton:hover {{
                background-color: {p.surface_light};
                color: {p.text_primary};
            }}
            QPushButton:checked {{
                background-color: {p.accent_subtle};
                color: {p.text_primary};
                border-left: 3px solid {p.accent};
                border-radius: 0px 10px 10px 0px;
                padding-left: 13px;
                font-weight: 600;
            }}
        """

    @classmethod
    def get_menu_style(cls):
        p = ThemeManager.palette()
        return f"""
            QMenu {{
                background-color: {p.surface_card};
                border: 1px solid {p.border};
                border-radius: 8px;
                padding: 6px;
                font-size: 12px;
            }}
            QMenu::item {{
                padding: 7px 14px;
                border-radius: 6px;
                color: {p.text_primary};
                font-size: 12px;
                font-weight: 500;
            }}
            QMenu::item:selected {{
                background-color: {p.surface_light};
            }}
            QMenu::item:disabled {{
                color: {p.text_muted};
            }}
        """

    @classmethod
    def get_list_widget_style(cls):
        p = ThemeManager.palette()
        return f"""
            QListWidget {{
                background-color: {p.background};
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                background-color: {p.background};
                border: none;
                border-bottom: 1px solid {p.surface_light};
                padding: 0px;
                margin: 0px;
            }}
            QListWidget::item:hover {{
                background-color: {p.surface};
            }}
        """

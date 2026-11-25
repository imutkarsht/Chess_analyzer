# SPDX-License-Identifier: GPL-3.0-only
"""Tabs, sidebar, menus, scroll areas, splitters, and layout chrome."""

from __future__ import annotations

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
            selected_text = cls.on_accent_for(selected_background)
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
    def apply_transparent(cls, widget, *, borderless: bool = True) -> None:
        """Mark a container transparent through the global QSS property rules.

        A declaration-only ``setStyleSheet("background: transparent")`` on a
        container acts as a wildcard rule for every descendant and overrides
        the application stylesheet for child buttons and inputs. Property
        rules only match the widget that carries them, so descendants keep
        their own styling.
        """
        widget.setProperty("transparent", "full" if borderless else "background")
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()


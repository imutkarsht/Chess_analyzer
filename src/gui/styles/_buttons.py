# SPDX-License-Identifier: GPL-3.0-only
"""Button QSS for every variant and size."""

from __future__ import annotations

from src.gui.theme import ThemeManager


class _ButtonMixin:
    _BUTTON_SIZES = {
        "xs": {"font": 11, "pad_v": 1, "pad_h": 7, "radius": 4, "weight": 600},
        "sm": {"font": 12, "pad_v": 4, "pad_h": 10, "radius": 6, "weight": 600},
        "md": {"font": 13, "pad_v": 8, "pad_h": 16, "radius": 6, "weight": 600},
        "lg": {"font": 14, "pad_v": 10, "pad_h": 22, "radius": 8, "weight": 600},
    }

    @classmethod
    def get_button_qss(
        cls,
        *,
        variant: str = "primary",
        size: str = "md",
        accent: str | None = None,
        align: str | None = None,
        danger: bool = False,
        text_color: str | None = None,
        font_size: int | None = None,
        font_weight: int | None = None,
    ) -> str:
        """Stylesheet for :class:`src.gui.components.controls.button.Button`.

        One generator for every button in the app, so hover/pressed/checked/
        disabled states stay identical everywhere and follow the live palette.
        ``danger`` recolors any variant with the destructive tone; the
        ``danger`` variant is the outlined red look on its own.
        """
        p = ThemeManager.palette()
        acc = accent or p.accent
        danger_color = cls.COLOR_BLUNDER
        on_acc = cls.COLOR_ON_ACCENT
        spec = cls._BUTTON_SIZES.get(size, cls._BUTTON_SIZES["md"])

        if variant == "primary":
            bg, fg, border = acc, on_acc, acc
            hover = (p.accent_hover, on_acc, p.accent_hover)
            pressed = (acc, on_acc, acc)
            checked = (p.accent_hover, on_acc, p.accent_hover)
            disabled_bg = p.border
        elif variant == "filled":
            bg, fg, border = p.surface_light, p.text_primary, p.border
            hover = (p.surface, p.text_primary, acc)
            pressed = (p.accent_subtle, p.text_primary, acc)
            checked = (p.accent_subtle, p.text_primary, acc)
            disabled_bg = p.surface_light
        elif variant == "outlined":
            bg, fg, border = "transparent", acc, acc
            # Tint instead of filling: the accent-coloured icon must stay visible.
            hover = (p.accent_subtle, acc, acc)
            pressed = (p.accent_subtle, acc, acc)
            checked = (p.accent_subtle, acc, acc)
            disabled_bg = "transparent"
        elif variant == "tonal":
            # Soft accent action: reads as AI/feature-level without competing
            # with a solid primary button on the same screen. The label uses
            # primary ink because accent-on-accent-subtle fails contrast for
            # red/orange accents (the tint already carries the accent cue).
            bg, fg, border = p.accent_subtle, p.text_primary, p.accent_subtle
            hover = (p.surface_light, p.text_primary, acc)
            pressed = (p.accent_subtle, p.text_primary, acc)
            checked = (p.accent_subtle, p.text_primary, acc)
            disabled_bg = p.surface_light
        elif variant == "hollow":
            bg, fg, border = "transparent", p.text_primary, p.border
            hover = (p.surface_light, p.text_primary, acc)
            pressed = (p.accent_subtle, p.text_primary, acc)
            checked = (p.accent_subtle, p.text_primary, acc)
            disabled_bg = "transparent"
        elif variant == "ghost":
            bg, fg, border = "transparent", p.text_secondary, "transparent"
            hover = (p.surface_light, p.text_primary, "transparent")
            pressed = (p.accent_subtle, p.text_primary, "transparent")
            checked = (p.accent_subtle, p.text_primary, "transparent")
            disabled_bg = "transparent"
        elif variant == "danger":
            # Neutral resting surface keeps destructive actions from shouting;
            # the red label/icon carries the intent and the border reddens on hover.
            bg, fg, border = p.surface_light, danger_color, p.border
            hover = (p.surface, danger_color, danger_color)
            pressed = (p.accent_subtle, danger_color, danger_color)
            checked = (p.accent_subtle, danger_color, danger_color)
            disabled_bg = p.surface_light
        elif variant == "segment":
            # Compact chip used inside SegmentedControl. The checked state is a
            # raised card; unchecked chips stay quiet until hover.
            bg, fg, border = "transparent", p.text_secondary, "transparent"
            hover = (p.surface_light, p.text_primary, "transparent")
            pressed = (p.surface_light, p.text_primary, "transparent")
            checked = (p.surface_card, p.text_primary, p.border)
            disabled_bg = "transparent"
        else:  # link
            bg, fg, border = "transparent", p.text_secondary, "transparent"
            hover = ("transparent", acc, "transparent")
            pressed = ("transparent", acc, "transparent")
            checked = ("transparent", acc, "transparent")
            disabled_bg = "transparent"

        if danger and variant != "danger":
            fg = danger_color
            border = danger_color
            if variant == "primary":
                # Solid destructive button: white label/icon on the red fill.
                bg = danger_color
                fg = on_acc
                hover = ("#B01020", on_acc, "#B01020")
                pressed = ("#900010", on_acc, "#900010")
                checked = ("#B01020", on_acc, "#B01020")
            elif variant in ("filled", "tonal"):
                hover = (p.surface, danger_color, danger_color)
                pressed = (p.surface_light, danger_color, danger_color)
                checked = (p.surface_light, danger_color, danger_color)
            elif variant in ("ghost", "link"):
                border = "transparent"
                hover = (p.surface_light, danger_color, "transparent")
                pressed = (p.accent_subtle, danger_color, "transparent")
                checked = (p.accent_subtle, danger_color, "transparent")
            else:  # outlined / hollow
                hover = (p.surface_light, danger_color, danger_color)
                pressed = (p.accent_subtle, danger_color, danger_color)
                checked = (p.accent_subtle, danger_color, danger_color)

        align_rule = f"text-align: {align};" if align else ""
        if text_color:
            fg = text_color
        font_px = font_size if font_size is not None else spec['font']
        font_pt_weight = font_weight if font_weight is not None else spec['weight']
        return f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: {spec['radius']}px;
                padding: {spec['pad_v']}px {spec['pad_h']}px;
                font-size: {font_px}px;
                font-weight: {font_pt_weight};
                {align_rule}
            }}
            QPushButton:hover {{
                background-color: {hover[0]};
                color: {hover[1]};
                border-color: {hover[2]};
            }}
            QPushButton:pressed {{
                background-color: {pressed[0]};
                color: {pressed[1]};
                border-color: {pressed[2]};
            }}
            QPushButton:checked {{
                background-color: {checked[0]};
                color: {checked[1]};
                border-color: {checked[2]};
            }}
            QPushButton:disabled {{
                background-color: {disabled_bg};
                color: {p.text_muted};
                border-color: {p.border if variant in ("filled", "hollow") else "transparent"};
            }}
        """

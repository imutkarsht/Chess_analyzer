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
        acc = cls.readable_color(accent, p.surface) if accent else p.ui_accent
        danger_fill = cls.COLOR_DANGER_FILL
        danger_text = cls.COLOR_DANGER_TEXT
        danger_subtle = cls.rgba(danger_text, 0.12)
        danger_subtle_hover = cls.rgba(danger_text, 0.18)
        danger_subtle_pressed = cls.rgba(danger_text, 0.24)
        on_acc = cls.on_accent_for(acc)
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
            # Soft destructive action: a red wash carries the intent without
            # pretending to be a neutral field. Solid red is reserved for the
            # final confirmation (primary + danger).
            bg, fg, border = danger_subtle, danger_text, "transparent"
            hover = (danger_subtle_hover, danger_text, "transparent")
            pressed = (danger_subtle_pressed, danger_text, "transparent")
            checked = (danger_subtle_pressed, danger_text, "transparent")
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
            fg = danger_text
            border = danger_text
            if variant == "primary":
                # Solid destructive button: high-contrast ink on the red fill.
                on_danger = cls.on_accent_for(danger_fill)
                bg = danger_fill
                fg = on_danger
                border = danger_fill
                hover = (p.danger_hover, on_danger, p.danger_hover)
                pressed = (p.danger_pressed, on_danger, p.danger_pressed)
                checked = (p.danger_hover, on_danger, p.danger_hover)
            elif variant in ("filled", "tonal"):
                bg = danger_subtle
                border = "transparent"
                hover = (danger_subtle_hover, danger_text, "transparent")
                pressed = (danger_subtle_pressed, danger_text, "transparent")
                checked = (danger_subtle_pressed, danger_text, "transparent")
            elif variant in ("ghost", "link"):
                border = "transparent"
                hover = (danger_subtle, danger_text, "transparent")
                pressed = (danger_subtle_hover, danger_text, "transparent")
                checked = (danger_subtle_hover, danger_text, "transparent")
            else:  # outlined / hollow
                bg = "transparent"
                hover = (danger_subtle, danger_text, danger_text)
                pressed = (danger_subtle_hover, danger_text, danger_text)
                checked = (danger_subtle_hover, danger_text, danger_text)

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

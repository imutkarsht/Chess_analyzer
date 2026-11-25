# SPDX-License-Identifier: GPL-3.0-only
"""Accent-tinted palette builders for the Light and Dark themes.

Tint is a modifier, not a standalone theme. The active light/dark palette is
rebuilt from the live accent colour so the window, cards, borders, and text
pick up a controlled amount of the accent without losing contrast.
"""

from __future__ import annotations

from dataclasses import replace

from src.gui.theme.palette import DARK, LIGHT, ThemePalette


def _parse(hex_color: str) -> tuple[int, int, int] | None:
    value = hex_color.lstrip("#")
    if len(value) != 6:
        return None
    try:
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    except ValueError:
        return None


def _mix(base: str, tint: str, ratio: float) -> str:
    """Mix ``tint`` into ``base`` by ``ratio`` (0..1) in sRGB."""
    base_rgb = _parse(base)
    tint_rgb = _parse(tint)
    if base_rgb is None or tint_rgb is None:
        return base
    ratio = max(0.0, min(1.0, ratio))
    red, green, blue = (
        round(base_rgb[index] + (tint_rgb[index] - base_rgb[index]) * ratio)
        for index in range(3)
    )
    return f"#{red:02X}{green:02X}{blue:02X}"


def _build_tinted(base: ThemePalette, accent: str, ratios: dict[str, float]) -> ThemePalette:
    return replace(
        base.with_accent(accent),
        **{
            field: _mix(getattr(base, field), accent, ratio)
            for field, ratio in ratios.items()
        },
    )


def build_tinted_dark_palette(accent: str) -> ThemePalette:
    """Derive the tinted dark palette from the live accent colour."""
    return _build_tinted(
        DARK,
        accent,
        {
            # Dark surfaces absorb more accent before they lose their depth.
            "background": 0.10,
            "surface": 0.13,
            "surface_light": 0.17,
            "surface_card": 0.15,
            "border": 0.30,
            "border_light": 0.38,
            "highlight": 0.22,
            "text_primary": 0.04,
            "text_secondary": 0.08,
            "text_muted": 0.10,
            "board_highlight": 0.25,
        },
    )


def build_tinted_light_palette(accent: str) -> ThemePalette:
    """Derive the tinted light palette from the live accent colour."""
    return _build_tinted(
        LIGHT,
        accent,
        {
            # Light surfaces need a visible but clean pastel tint.
            "background": 0.10,
            "surface": 0.08,
            "surface_light": 0.12,
            "surface_card": 0.08,
            "border": 0.28,
            "border_light": 0.34,
            "highlight": 0.16,
            "text_primary": 0.02,
            "text_secondary": 0.03,
            "text_muted": 0.03,
            "board_highlight": 0.25,
        },
    )


__all__ = ["build_tinted_dark_palette", "build_tinted_light_palette"]

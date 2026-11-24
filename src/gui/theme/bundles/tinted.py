# SPDX-License-Identifier: GPL-3.0-only
"""Tinted theme: the dark palette with the accent colour mixed into every surface.

The palette is rebuilt from the live accent colour (``palette_factory``), so
switching the accent recolours the whole chrome while keeping the dark
structure. Text stays light with a whisper of tint; borders and highlights get
progressively more accent so controls remain legible.
"""

from __future__ import annotations

from dataclasses import replace

from src.gui.theme.bundle import ThemeBundle
from src.gui.theme.palette import DARK, ThemePalette


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
    r, g, b = (
        round(base_rgb[i] + (tint_rgb[i] - base_rgb[i]) * ratio) for i in range(3)
    )
    return f"#{r:02X}{g:02X}{b:02X}"


def build_tinted_palette(accent: str) -> ThemePalette:
    """Derive the tinted dark palette from the live accent colour."""
    base = DARK.with_accent(accent)
    return replace(
        base,
        # Surfaces absorb a little accent so the whole window reads as tinted.
        background=_mix(DARK.background, accent, 0.10),
        surface=_mix(DARK.surface, accent, 0.13),
        surface_light=_mix(DARK.surface_light, accent, 0.17),
        surface_card=_mix(DARK.surface_card, accent, 0.15),
        # Borders and highlights carry the tint more strongly.
        border=_mix(DARK.border, accent, 0.30),
        border_light=_mix(DARK.border_light, accent, 0.38),
        highlight=_mix(DARK.highlight, accent, 0.22),
        # Text keeps contrast; only a faint tint to avoid a cold grey.
        text_primary=_mix(DARK.text_primary, accent, 0.04),
        text_secondary=_mix(DARK.text_secondary, accent, 0.08),
        text_muted=_mix(DARK.text_muted, accent, 0.10),
        # Board highlight follows the accent family for a cohesive look.
        board_highlight=_mix(DARK.board_highlight, accent, 0.25),
    )


TINTED_BUNDLE = ThemeBundle(
    id="tinted",
    display_name="Tinted",
    palette=build_tinted_palette(DARK.accent),
    mode="dark",
    palette_factory=build_tinted_palette,
)

__all__ = ["TINTED_BUNDLE", "build_tinted_palette"]

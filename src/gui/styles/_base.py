# SPDX-License-Identifier: GPL-3.0-only
"""Palette metaclass and shared style constants."""

from __future__ import annotations

from src.gui.theme import ThemeManager, color_math
from src.gui.theme.palette import BOARD_THEMES

ON_ACCENT = "#FFFFFF"


class _StylesMeta(type):
    # ═══════════════════════════════════════════════════════════════
    #  COLOUR MATH
    # ═══════════════════════════════════════════════════════════════
    @staticmethod
    def rgba(color: str, alpha: float) -> str:
        """Return a QSS ``rgba()`` string for an opaque hex colour."""
        return color_math.rgba(color, alpha)

    @staticmethod
    def blend_hex(color_a: str, color_b: str, ratio: float) -> str:
        """Linear blend between two hex colours (ratio 0..1)."""
        return color_math.blend_hex(color_a, color_b, ratio)

    @staticmethod
    def contrast_ratio(foreground: str, background: str) -> float:
        return color_math.contrast_ratio(foreground, background)

    @classmethod
    def readable_color(
        cls, color: str, background: str, minimum: float = 4.5
    ) -> str:
        """Blend ``color`` toward the opposite end of the surface until readable."""
        return color_math.readable_color(color, background, minimum)

    @staticmethod
    def on_accent_for(color: str) -> str:
        """Pick black or white ink for text placed on ``color``."""
        return color_math.on_color(color)

    # ═══════════════════════════════════════════════════════════════
    #  CORE PALETTE
    # ═══════════════════════════════════════════════════════════════
    @property
    def COLOR_BACKGROUND(cls):
        return ThemeManager.palette().background

    @property
    def COLOR_SURFACE(cls):
        return ThemeManager.palette().surface

    @property
    def COLOR_SURFACE_LIGHT(cls):
        return ThemeManager.palette().surface_light

    @property
    def COLOR_SURFACE_CARD(cls):
        return ThemeManager.palette().surface_card

    @property
    def COLOR_TEXT_PRIMARY(cls):
        return ThemeManager.palette().text_primary

    @property
    def COLOR_TEXT_SECONDARY(cls):
        return ThemeManager.palette().text_secondary

    @property
    def COLOR_TEXT_MUTED(cls):
        return ThemeManager.palette().text_muted

    @property
    def COLOR_ACCENT(cls):
        return ThemeManager.palette().ui_accent

    @property
    def COLOR_ACCENT_HOVER(cls):
        return ThemeManager.palette().accent_hover

    @property
    def COLOR_ACCENT_SUBTLE(cls):
        return ThemeManager.palette().accent_subtle

    @property
    def COLOR_ON_ACCENT(cls):
        return ThemeManager.palette().on_accent

    @property
    def COLOR_BORDER(cls):
        return ThemeManager.palette().border

    @property
    def COLOR_BORDER_LIGHT(cls):
        return ThemeManager.palette().border_light

    @property
    def COLOR_HIGHLIGHT(cls):
        return ThemeManager.palette().highlight

    @property
    def COLOR_PIECE_WHITE(cls):
        return ThemeManager.palette().piece_white

    @property
    def COLOR_PIECE_BLACK(cls):
        return ThemeManager.palette().piece_black

    @property
    def COLOR_BOARD_HIGHLIGHT(cls):
        return ThemeManager.palette().board_highlight

    @property
    def COLOR_BRANCH_1(cls):
        return ThemeManager.palette().branch_colors[0]

    @property
    def COLOR_BRANCH_2(cls):
        return ThemeManager.palette().branch_colors[1]

    @property
    def COLOR_BRANCH_3(cls):
        return ThemeManager.palette().branch_colors[2]

    @property
    def COLOR_BRANCH_4(cls):
        return ThemeManager.palette().branch_colors[3]

    @classmethod
    def get_branch_color(cls, index: int) -> str:
        colors = ThemeManager.palette().branch_colors
        return colors[index % len(colors)]

    # ═══════════════════════════════════════════════════════════════
    #  MOVE CLASSIFICATION COLORS
    # ═══════════════════════════════════════════════════════════════
    @property
    def COLOR_BRILLIANT(cls):
        return ThemeManager.get_class_color("Brilliant")

    @property
    def COLOR_GREAT(cls):
        return ThemeManager.get_class_color("Great")

    @property
    def COLOR_BEST(cls):
        return ThemeManager.get_class_color("Best")

    @property
    def COLOR_EXCELLENT(cls):
        return ThemeManager.get_class_color("Excellent")

    @property
    def COLOR_GOOD(cls):
        return ThemeManager.get_class_color("Good")

    @property
    def COLOR_INACCURACY(cls):
        return ThemeManager.get_class_color("Inaccuracy")

    @property
    def COLOR_MISTAKE(cls):
        return ThemeManager.get_class_color("Mistake")

    @property
    def COLOR_BLUNDER(cls):
        return ThemeManager.get_class_color("Blunder")

    @property
    def COLOR_MISS(cls):
        return ThemeManager.get_class_color("Miss")

    @property
    def COLOR_BOOK(cls):
        return ThemeManager.get_class_color("Book")

    # ═══════════════════════════════════════════════════════════════
    #  SEMANTIC COLORS
    # ═══════════════════════════════════════════════════════════════
    @property
    def COLOR_RESULT_WIN(cls):
        return "#4FA859"

    @property
    def COLOR_RESULT_DRAW(cls):
        return "#8E9AA6"

    @property
    def COLOR_RESULT_LOSS(cls):
        return "#2F3640"

    @property
    def COLOR_DANGER_TEXT(cls):
        """Destructive text tint that stays readable on the current surface."""
        return cls.readable_color(cls.COLOR_BLUNDER, cls.COLOR_SURFACE)

    @property
    def COLOR_DANGER_FILL(cls):
        """Solid destructive fill that keeps white text readable."""
        color = cls.COLOR_BLUNDER
        if cls.contrast_ratio(ON_ACCENT, color) >= 4.5:
            return color
        return cls.readable_color(color, ON_ACCENT, 4.5)

    @property
    def COLOR_ON_DANGER(cls):
        """High-contrast ink for text/icons placed on ``COLOR_DANGER_FILL``."""
        return cls.on_accent_for(cls.COLOR_DANGER_FILL)

    @property
    def COLOR_ENGINE_READY(cls):
        return "#27ae60"

    @property
    def COLOR_ENGINE_BUSY(cls):
        return "#e67e22"

    # ═══════════════════════════════════════════════════════════════
    #  BOARD THEMES
    # ═══════════════════════════════════════════════════════════════
    @property
    def BOARD_THEMES(cls):
        return BOARD_THEMES

    # ═══════════════════════════════════════════════════════════════
    #  COMPONENT COLORS
    # ═══════════════════════════════════════════════════════════════
    @property
    def COLOR_EVAL_BAR_BG(cls):
        return ThemeManager.palette().eval_bar_background

    @property
    def COLOR_EVAL_BAR_FG(cls):
        return ThemeManager.palette().eval_bar_foreground

    @property
    def COLOR_GRAPH_GRID(cls):
        return ThemeManager.palette().graph_grid

    @property
    def COLOR_GRAPH_PIN(cls):
        return ThemeManager.palette().graph_pin

    @property
    def COLOR_STAR_ACTIVE(cls):
        return ThemeManager.palette().star_active

    @property
    def COLOR_STAR_INACTIVE(cls):
        return ThemeManager.palette().star_inactive

    @property
    def COLOR_STAR_ACTIVE_SUBTLE(cls):
        return ThemeManager.palette().star_active_subtle

    @property
    def COLOR_CROWN(cls):
        return ThemeManager.palette().crown

    @property
    def COLOR_BOARD_DIM(cls):
        return ThemeManager.palette().board_dim

    @property
    def COLOR_MOVE_DOT_ON_DARK(cls):
        return ThemeManager.palette().move_dot_on_dark

    @property
    def COLOR_MOVE_DOT_ON_LIGHT(cls):
        return ThemeManager.palette().move_dot_on_light

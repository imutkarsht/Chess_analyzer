# SPDX-License-Identifier: GPL-3.0-only
"""Toast, engine-line, and engine-score QSS."""

from __future__ import annotations

from src.gui.theme import ThemeManager


class _FeedbackMixin:
    @classmethod
    def get_toast_qss(
        cls,
        *,
        background: str | None = None,
        border: str | None = None,
        text_color: str | None = None,
        radius: int = 16,
    ) -> str:
        """Stylesheet for :class:`src.gui.components.feedback.toast.Toast`.

        The panel stays close to the neutral notification references: an
        elevated surface, one hairline border, and no saturated variant wash.
        Font sizes are set on the labels so width measurements stay accurate.
        """
        p = ThemeManager.palette()
        bg = background or p.surface
        bd = border or p.border
        fg = text_color or p.text_primary
        return f"""
            QFrame#ToastSurface {{
                background-color: {bg};
                border: 1px solid {bd};
                border-radius: {radius}px;
            }}
            QLabel#ToastIcon, QWidget#ToastText, QWidget#ToastProgressArea {{
                background: transparent;
            }}
            QLabel#ToastTitle, QLabel#ToastMessage {{
                color: {fg};
                background: transparent;
            }}
            QProgressBar#ToastProgress {{
                background-color: {bd};
                border: none;
                border-radius: 1px;
            }}
            QProgressBar#ToastProgress::chunk {{
                background-color: {p.accent};
                border-radius: 1px;
            }}
        """

    @classmethod
    def get_toast_icon_color(cls, variant: str, *, semantic: bool = False) -> str:
        """Glyph colour for a toast variant.

        The default follows the notification references: monochrome glyphs with
        red reserved for failures. ``semantic=True`` opts into the app's
        classification palette for call sites that need stronger signalling.
        """
        if variant == "error":
            return cls.COLOR_BLUNDER
        if not semantic:
            return cls.COLOR_TEXT_PRIMARY
        return {
            "success": cls.COLOR_ENGINE_READY,
            "warning": cls.COLOR_ENGINE_BUSY,
            "info": cls.COLOR_ACCENT,
            "loading": cls.COLOR_ACCENT,
        }.get(variant, cls.COLOR_TEXT_PRIMARY)

    @staticmethod
    def _blend_hex(color_a, color_b, ratio):
        """Linear blend between two ``#RRGGBB`` colours (ratio 0..1)."""
        ratio = max(0.0, min(1.0, ratio))
        a = color_a.lstrip("#")
        b = color_b.lstrip("#")
        if len(a) != 6 or len(b) != 6:
            return color_a
        channels = [
            round(int(a[index : index + 2], 16) * (1 - ratio) + int(b[index : index + 2], 16) * ratio)
            for index in (0, 2, 4)
        ]
        return "#" + "".join(f"{channel:02X}" for channel in channels)

    @classmethod
    def _contrast_text(cls, background):
        """Pick the palette's light or dark ink for a blended badge background."""
        p = ThemeManager.palette()
        value = background.lstrip("#")
        if len(value) != 6:
            return p.text_primary
        red, green, blue = (int(value[index : index + 2], 16) for index in (0, 2, 4))
        luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
        return p.piece_black if luminance > 140 else p.piece_white

    @classmethod
    def get_engine_score_badge_style(cls, line):
        """Score pill for a White-perspective ``EngineLine``."""
        p = ThemeManager.palette()
        if line.mate is not None:
            if line.mate > 0:
                return cls.get_eval_badge_style(p.piece_white, p.piece_black)
            return cls.get_eval_badge_style(p.piece_black, p.piece_white)
        if line.cp is None or line.cp == 0:
            return cls.get_eval_badge_style(p.surface_light, p.text_primary)

        intensity = min(1.0, abs(line.cp) / 300.0)
        if line.cp > 0:
            background = cls._blend_hex(p.surface_light, p.piece_white, 0.12 + 0.55 * intensity)
        else:
            background = cls._blend_hex(p.surface_light, p.piece_black, 0.12 + 0.60 * intensity)
        return cls.get_eval_badge_style(background, cls._contrast_text(background))

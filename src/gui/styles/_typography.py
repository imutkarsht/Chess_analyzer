# SPDX-License-Identifier: GPL-3.0-only
"""Tone mapping and generated typography QSS."""

from __future__ import annotations

from src.gui.theme import ThemeManager
from src.gui.theme.typography import (
    ALLOWED_SIZES,
    ALLOWED_WEIGHTS,
    MONO_FAMILIES,
    ROLE_SPECS,
    TextTone,
)

_TYPOGRAPHY_CACHE: tuple[int, str] | None = None


class _TypographyMixin:
    @classmethod
    def get_tone_color(cls, tone: TextTone | str) -> str:
        """Resolve a semantic text tone to its live palette colour."""
        tone = TextTone(tone)
        p = ThemeManager.palette()
        colors = {
            TextTone.PRIMARY: p.text_primary,
            TextTone.SECONDARY: p.text_secondary,
            TextTone.MUTED: p.text_muted,
            TextTone.ACCENT: p.accent,
            TextTone.BRILLIANT: cls.COLOR_BRILLIANT,
            TextTone.GREAT: cls.COLOR_GREAT,
            TextTone.BEST: cls.COLOR_BEST,
            TextTone.EXCELLENT: cls.COLOR_EXCELLENT,
            TextTone.GOOD: cls.COLOR_GOOD,
            TextTone.INACCURACY: cls.COLOR_INACCURACY,
            TextTone.MISTAKE: cls.COLOR_MISTAKE,
            TextTone.BLUNDER: cls.COLOR_BLUNDER,
            TextTone.MISS: cls.COLOR_MISS,
            TextTone.BOOK: cls.COLOR_BOOK,
            TextTone.RESULT_WIN: cls.COLOR_RESULT_WIN,
            TextTone.RESULT_DRAW: cls.COLOR_RESULT_DRAW,
            TextTone.RESULT_LOSS: cls.COLOR_BLUNDER,
            TextTone.ENGINE_READY: cls.COLOR_ENGINE_READY,
            TextTone.ENGINE_BUSY: cls.COLOR_ENGINE_BUSY,
        }
        return colors[tone]

    @classmethod
    def get_tone_surface(cls, tone: TextTone | str, alpha: float | None = None) -> str:
        """Return a subtle tinted surface for a semantic tone.

        Used by tonal status and classification chips. The value stays in the
        styles layer so widget files never hardcode ``rgba`` values.
        """
        if alpha is None:
            alpha = 0.16 if ThemeManager.mode() == "light" else 0.12
        color = cls.get_tone_color(tone).lstrip("#")
        if len(color) != 6:
            return cls.COLOR_SURFACE_LIGHT
        red, green, blue = (int(color[index : index + 2], 16) for index in (0, 2, 4))
        return f"rgba({red}, {green}, {blue}, {alpha:.2f})"

    @classmethod
    def get_tone_for_color(cls, color: str) -> TextTone:
        """Resolve a palette colour back to its semantic text tone."""
        for tone in TextTone:
            if cls.get_tone_color(tone) == color:
                return tone
        return TextTone.PRIMARY

    @classmethod
    def get_typography_qss(cls) -> str:
        """Generated rules for :class:`src.gui.components.display.label.Label`.

        Roles provide size/weight/case/family. Size and weight override blocks
        follow so a label can preserve a one-off value during migration. Tones
        come last and only set colour, keeping semantic colour independent from
        typography.
        """
        global _TYPOGRAPHY_CACHE
        revision = ThemeManager.style_revision()
        if _TYPOGRAPHY_CACHE is not None and _TYPOGRAPHY_CACHE[0] == revision:
            return _TYPOGRAPHY_CACHE[1]

        rules: list[str] = []

        for role, spec in ROLE_SPECS.items():
            declarations = [
                f"font-size: {spec.size}px;",
                f"font-weight: {spec.weight};",
            ]
            if spec.letter_spacing:
                declarations.append(f"letter-spacing: {spec.letter_spacing}px;")
            if spec.uppercase:
                declarations.append("text-transform: uppercase;")
            if spec.mono:
                declarations.append(f"font-family: {MONO_FAMILIES};")
            rules.append(
                f'QLabel[role="{role.value}"] {{ {" ".join(declarations)} }}'
            )

        for size in sorted(ALLOWED_SIZES):
            rules.append(f'QLabel[textSize="{size}"] {{ font-size: {size}px; }}')

        for weight in sorted(ALLOWED_WEIGHTS):
            rules.append(
                f'QLabel[textWeight="{weight}"] {{ font-weight: {weight}; }}'
            )

        for tone in TextTone:
            rules.append(
                f'QLabel[tone="{tone.value}"] {{ color: {cls.get_tone_color(tone)}; '
                "background: transparent; border: none; }"
            )

        qss = "\n".join(rules)
        _TYPOGRAPHY_CACHE = (revision, qss)
        return qss

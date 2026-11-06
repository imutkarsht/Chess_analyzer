# SPDX-License-Identifier: GPL-3.0-only
"""Semantic typography tokens for the shared ``Label`` component.

Typography is theme-independent, so roles describe size and weight only.
Colours belong to :class:`TextTone` and are resolved from the live palette by
``Styles.get_typography_qss``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TextRole(StrEnum):
    """Named typographic roles used across the application."""

    PAGE_TITLE = "page_title"
    DIALOG_TITLE = "dialog_title"
    SECTION_TITLE = "section_title"
    SUBHEADING = "subheading"
    CARD_TITLE = "card_title"
    BODY = "body"
    BODY_STRONG = "body_strong"
    BODY_LARGE = "body_large"
    CAPTION = "caption"
    CAPTION_STRONG = "caption_strong"
    MICRO = "micro"
    MICRO_STRONG = "micro_strong"
    MONO = "mono"
    STAT = "stat"
    STAT_LARGE = "stat_large"


class TextTone(StrEnum):
    """Semantic text colours resolved from the active palette."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    MUTED = "muted"
    ACCENT = "accent"

    BRILLIANT = "brilliant"
    GREAT = "great"
    BEST = "best"
    EXCELLENT = "excellent"
    GOOD = "good"
    INACCURACY = "inaccuracy"
    MISTAKE = "mistake"
    BLUNDER = "blunder"
    MISS = "miss"
    BOOK = "book"

    RESULT_WIN = "result_win"
    RESULT_DRAW = "result_draw"
    RESULT_LOSS = "result_loss"

    ENGINE_READY = "engine_ready"
    ENGINE_BUSY = "engine_busy"


@dataclass(frozen=True)
class RoleSpec:
    """Default typography for one semantic role."""

    size: int
    weight: int
    letter_spacing: float = 0.0
    uppercase: bool = False
    mono: bool = False


ROLE_SPECS: dict[TextRole, RoleSpec] = {
    TextRole.PAGE_TITLE: RoleSpec(24, 700),
    TextRole.DIALOG_TITLE: RoleSpec(20, 600),
    TextRole.SECTION_TITLE: RoleSpec(18, 700),
    TextRole.SUBHEADING: RoleSpec(16, 600),
    TextRole.CARD_TITLE: RoleSpec(12, 600, letter_spacing=0.5, uppercase=True),
    TextRole.BODY: RoleSpec(13, 400),
    TextRole.BODY_STRONG: RoleSpec(13, 600),
    TextRole.BODY_LARGE: RoleSpec(14, 400),
    TextRole.CAPTION: RoleSpec(12, 400),
    TextRole.CAPTION_STRONG: RoleSpec(12, 600),
    TextRole.MICRO: RoleSpec(11, 400),
    TextRole.MICRO_STRONG: RoleSpec(11, 600),
    TextRole.MONO: RoleSpec(12, 600, mono=True),
    TextRole.STAT: RoleSpec(28, 700),
    TextRole.STAT_LARGE: RoleSpec(40, 700),
}

# Overrides are migration aids for one-off sizes/weights. Prefer a role when one
# fits; keep these lists finite so typography cannot drift arbitrarily.
ALLOWED_SIZES: frozenset[int] = frozenset(
    {8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 22, 24, 28, 36, 40, 48, 64}
)
ALLOWED_WEIGHTS: frozenset[int] = frozenset({400, 500, 600, 700, 800})

MONO_FAMILIES = '"SFMono-Regular", "Menlo", "Consolas", "Liberation Mono", monospace'

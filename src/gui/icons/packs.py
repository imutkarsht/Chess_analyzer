# SPDX-License-Identifier: GPL-3.0-only
"""Built-in icon packs and the pack contract."""

from __future__ import annotations

from typing import Protocol

from src.gui.icons.spec import IconVariant

DEFAULT_ICON_PACK_ID = "fontawesome"


class IconPack(Protocol):
    """Maps semantic icon keys to a concrete icon font or source."""

    id: str
    display_name: str
    default_variant: IconVariant
    scale_factor: float

    def glyph(self, key: str, variant: IconVariant) -> str | None:
        """Return the concrete glyph for ``key``/``variant``, or ``None``."""


def _variant(variant: IconVariant | str | None) -> IconVariant:
    if variant is None:
        return IconVariant.SOLID
    try:
        return IconVariant(variant)
    except ValueError:
        return IconVariant.SOLID


class FontAwesomePack:
    """Solid Font Awesome Free glyphs via QtAwesome."""

    id = "fontawesome"
    display_name = "Font Awesome"
    default_variant = IconVariant.SOLID
    scale_factor = 1.0

    def glyph(self, key: str, variant: IconVariant) -> str | None:
        if not key or _variant(variant) is not IconVariant.SOLID:
            return None
        return f"fa5s.{key}"


class PhosphorPack:
    """Outline Phosphor glyphs via QtAwesome.

    Phosphor's free font is outline-based and ships with QtAwesome, so this
    pack adds no new assets or licence obligations beyond QtAwesome's existing
    notices.
    """

    id = "phosphor"
    display_name = "Phosphor"
    default_variant = IconVariant.OUTLINE
    scale_factor = 1.25

    # Font Awesome keys that need a different Phosphor name. Keys that already
    # match Phosphor resolve directly; unsupported keys fall back to the solid
    # pack (chess-piece glyphs are the intentional exception).
    _ALIASES = {
        "angle-double-left": "caret-double-left",
        "angle-double-right": "caret-double-right",
        "angle-left": "caret-left",
        "angle-right": "caret-right",
        "arrows-alt": "arrows-out",
        "arrows-alt-v": "arrows-down-up",
        "bold": "text-aa",
        "bolt": "lightning",
        "broom": "paint-brush",
        "bullseye": "target",
        "calendar-alt": "calendar",
        "chevron-down": "caret-down",
        "chevron-left": "caret-left",
        "chevron-right": "caret-right",
        "chevron-up": "caret-up",
        "cloud-download-alt": "cloud-arrow-down",
        "code-branch": "git-branch",
        "cog": "gear",
        "comment-dots": "chat-dots",
        "comment-slash": "chat-circle",
        "crosshairs": "crosshair",
        "door-open": "door",
        "exchange-alt": "arrows-left-right",
        "exclamation-circle": "warning-circle",
        "exclamation-triangle": "warning",
        "external-link-alt": "arrow-square-out",
        "file-alt": "file-text",
        "file-code": "file-text",
        "file-csv": "file-text",
        "file-export": "export",
        "file-import": "file-arrow-down",
        "file-upload": "upload-simple",
        "fill": "paint-bucket",
        "filter": "funnel",
        "flag-checkered": "flag",
        "font": "text-aa",
        "gem": "diamond",
        "grip-vertical": "dots-six-vertical",
        "history": "clock-counter-clockwise",
        "home": "house",
        "hourglass-half": "hourglass-medium",
        "images": "image-square",
        "info-circle": "info",
        "layer-group": "stack",
        "magic": "magic-wand",
        "paste": "clipboard",
        "plug": "power",
        "question-circle": "question",
        "random": "shuffle",
        "running": "person-simple-run",
        "save": "floppy-disk",
        "search": "magnifying-glass",
        "share-alt": "share-network",
        "shield-alt": "shield",
        "sign-out-alt": "sign-out",
        "star-half-alt": "star-half",
        "stopwatch": "timer",
        "sync-alt": "arrows-clockwise",
        "tachometer-alt": "gauge",
        "th-large": "squares-four",
        "thumbtack": "push-pin",
        "times": "x",
        "tools": "wrench",
        "trash-alt": "trash",
        "underline": "text-underline",
        "undo": "arrow-counter-clockwise",
        "user-slash": "user-minus",
        "weight": "barbell",
        "chess": "grid-four",
    }

    def glyph(self, key: str, variant: IconVariant) -> str | None:
        if not key or _variant(variant) is not IconVariant.OUTLINE:
            return None
        return f"ph.{self._ALIASES.get(key, key)}"

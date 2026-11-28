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

    def glyph(self, key: str, variant: IconVariant) -> str | None:
        """Return the concrete glyph for ``key``/``variant``, or ``None``."""


def _variant(variant: IconVariant | str | None) -> IconVariant:
    if variant is None:
        return IconVariant.DEFAULT
    try:
        return IconVariant(variant)
    except ValueError:
        return IconVariant.DEFAULT


class FontAwesomePack:
    """Default pack, backed by Font Awesome Free via QtAwesome."""

    id = "fontawesome"
    display_name = "Font Awesome"
    _PREFIXES = {
        IconVariant.DEFAULT: "fa5s",
        IconVariant.SOLID: "fa5s",
        # Font Awesome 5 uses ``fa5`` for regular and ``fa5s`` for solid.
        # Free regular only covers a subset of glyphs; the resolver falls back
        # to solid when a regular glyph is unavailable.
        IconVariant.REGULAR: "fa5",
        IconVariant.OUTLINE: "fa5",
    }

    def glyph(self, key: str, variant: IconVariant) -> str | None:
        if not key:
            return None
        prefix = self._PREFIXES.get(_variant(variant), "fa5s")
        return f"{prefix}.{key}"


class MaterialPack:
    """Material Design Icons via QtAwesome.

    Material has one weight for most free glyphs, so variants deliberately
    resolve to the same prefix. Missing glyphs fall back to Font Awesome.
    """

    id = "material"
    display_name = "Material"

    def glyph(self, key: str, variant: IconVariant) -> str | None:
        return f"mdi6.{key}" if key else None

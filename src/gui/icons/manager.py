# SPDX-License-Identifier: GPL-3.0-only
"""Active icon pack registry and variant-aware resolution."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from src.gui.icons.packs import (
    DEFAULT_ICON_PACK_ID,
    FontAwesomePack,
    IconPack,
    PhosphorPack,
)
from src.gui.icons.spec import IconVariant


def _variant(value: IconVariant | str | None) -> IconVariant | None:
    if value is None:
        return None
    try:
        return IconVariant(value)
    except ValueError:
        return None


class IconStyleManager(QObject):
    """Registry of icon packs plus the active pack.

    Emits ``style_changed`` when the pack changes. Consumers re-resolve their
    icons; call sites do not change.
    """

    style_changed = pyqtSignal(str)

    _instance: IconStyleManager | None = None
    _packs: dict[str, IconPack] = {}
    _active_pack_id: str = DEFAULT_ICON_PACK_ID

    def __init__(self, parent=None):
        super().__init__(parent)
        IconStyleManager._instance = self

    @classmethod
    def instance(cls) -> IconStyleManager:
        if cls._instance is None:
            cls._instance = IconStyleManager()
        return cls._instance

    @classmethod
    def register_pack(cls, pack: IconPack) -> None:
        cls._packs[pack.id] = pack

    @classmethod
    def registered_packs(cls) -> dict[str, IconPack]:
        return dict(cls._packs)

    @classmethod
    def active_pack_id(cls) -> str:
        return cls._active_pack_id

    @classmethod
    def active_pack(cls) -> IconPack:
        return cls._packs.get(
            cls._active_pack_id, cls._packs[DEFAULT_ICON_PACK_ID]
        )

    @classmethod
    def set_pack(cls, pack_id: str) -> bool:
        if pack_id not in cls._packs:
            return False
        if pack_id == cls._active_pack_id:
            return True
        cls._active_pack_id = pack_id
        cls._changed()
        return True

    @classmethod
    def _changed(cls) -> None:
        from src.gui.icons.resolver import clear_icon_cache

        clear_icon_cache()
        cls.instance().style_changed.emit(cls._active_pack_id)

    @classmethod
    def resolve_glyphs(
        cls,
        name: str,
        variant: IconVariant | str | None = None,
        pack_id: str | None = None,
    ) -> list[str]:
        """Return glyph candidates in fallback order."""
        from src.gui.icons.resolver import icon_key

        selected_id = pack_id or cls._active_pack_id
        requested_variant = _variant(variant)
        key = icon_key(name)
        candidates: list[str] = []

        def add(value: str | None) -> None:
            if value and value not in candidates:
                candidates.append(value)

        # Preserve explicit legacy font names in the default pack (fa6s.*).
        if selected_id == DEFAULT_ICON_PACK_ID and key != name:
            add(name)

        for current_id in (selected_id, DEFAULT_ICON_PACK_ID):
            pack = cls._packs.get(current_id)
            if pack is None:
                continue
            variants = (
                [requested_variant, pack.default_variant]
                if requested_variant is not None
                else [pack.default_variant]
            )
            for current_variant in variants:
                add(pack.glyph(key, current_variant))

        return candidates

    @classmethod
    def resolve_glyph(
        cls,
        name: str,
        variant: IconVariant | str | None = None,
        pack_id: str | None = None,
    ) -> str | None:
        candidates = cls.resolve_glyphs(name, variant, pack_id)
        return candidates[0] if candidates else None


IconStyleManager.register_pack(FontAwesomePack())
IconStyleManager.register_pack(PhosphorPack())

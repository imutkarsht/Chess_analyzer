# SPDX-License-Identifier: GPL-3.0-only
"""Shared icon resolution and icon-style providers.

UI code should request pack-independent icon keys (``play``, ``close``) or
asset paths. The active :class:`IconPack` maps those keys to a concrete glyph
for the selected icon style. Missing glyphs fall back to the default pack.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap

from src.gui.utils.assets import asset_path, resolve_asset

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:  # pragma: no cover - QtAwesome ships with the app
    qta = None
    HAS_QTAWESOME = False


@dataclass(frozen=True)
class IconSpec:
    """A pack-independent icon request.

    ``name`` is a semantic key (``play``), a legacy qtawesome name
    (``fa5s.play``), or an asset path. ``tone``/``color``/``size`` override the
    consuming widget's defaults when the widget supports them.
    """

    name: str
    fallback: str = ""
    size: int | None = None
    tone: str | None = None
    color: str | None = None


class IconPack(Protocol):
    """Maps semantic icon keys to a concrete icon font or source."""

    id: str
    display_name: str

    def glyph(self, key: str) -> str | None:
        """Return the concrete glyph for ``key``, or ``None`` if unsupported."""


class FontAwesomePack:
    """Default pack, backed by Font Awesome solid via QtAwesome."""

    id = "fontawesome"
    display_name = "Font Awesome"

    def glyph(self, key: str) -> str | None:
        return f"fa5s.{key}" if key else None


DEFAULT_ICON_PACK_ID = "fontawesome"


def _resolve_icon_path(name: str) -> Path | None:
    if "/" in name or "\\" in name:
        candidate = Path(asset_path(name))
        return candidate if candidate.exists() else None
    resolved = resolve_asset(name)
    return Path(resolved) if resolved else None


def icon_key(name: str) -> str:
    """Convert a legacy qtawesome name to its pack-independent key.

    ``fa5s.play`` and ``play`` both become ``play``. Asset paths and names
    without a known icon-font prefix are returned unchanged.
    """
    if not name or "/" in name or "\\" in name:
        return name
    prefix, separator, key = name.partition(".")
    if not separator or not key:
        return name
    if prefix.startswith(("fa", "mdi", "ph", "msc", "ri", "bi")):
        return key
    return name


class IconStyleManager(QObject):
    """Registry of icon packs and the active style.

    The future ``icon_style`` setting only needs to call :meth:`set_pack`;
    every consumer that listens to ``style_changed`` re-resolves its icons
    without changing call sites.
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
        clear_icon_cache()
        cls.instance().style_changed.emit(pack_id)
        return True

    @classmethod
    def resolve_glyph(cls, name: str, pack_id: str | None = None) -> str | None:
        selected_id = pack_id or cls._active_pack_id
        key = icon_key(name)
        # The default pack historically accepted explicit font flavours such
        # as fa6s.*; keep those intact while still exposing the semantic key
        # to future packs.
        if selected_id == DEFAULT_ICON_PACK_ID and key != name:
            return name
        active = cls._packs.get(selected_id)
        if active is not None:
            glyph = active.glyph(key)
            if glyph:
                return glyph
        fallback = cls._packs.get(DEFAULT_ICON_PACK_ID)
        return fallback.glyph(key) if fallback is not None else None


IconStyleManager.register_pack(FontAwesomePack())


@lru_cache(maxsize=512)
def _cached_icon_pixmap(
    name: str, color: str, size: int, pack_id: str
) -> QPixmap | None:
    if not name or size <= 0:
        return None

    path = _resolve_icon_path(name)
    if path is not None:
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            return pixmap.scaled(
                size,
                size,
                aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio,
                transformMode=Qt.TransformationMode.SmoothTransformation,
            )

    glyph = IconStyleManager.resolve_glyph(name, pack_id)
    if not glyph:
        return None

    glyph_path = _resolve_icon_path(glyph)
    if glyph_path is not None:
        pixmap = QPixmap(str(glyph_path))
        if not pixmap.isNull():
            return pixmap.scaled(
                size,
                size,
                aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio,
                transformMode=Qt.TransformationMode.SmoothTransformation,
            )

    if HAS_QTAWESOME and qta is not None:
        try:
            return qta.icon(glyph, color=color).pixmap(size, size)
        except Exception:
            return None
    return None


def icon_pixmap(name: str, color: str, size: int) -> QPixmap | None:
    """Resolve an icon key or asset path to a themed pixmap."""
    return _cached_icon_pixmap(
        name, color, size, IconStyleManager.active_pack_id()
    )


def icon_qicon(name: str, color: str, size: int = 16) -> QIcon:
    """Resolve an icon key or asset path to a ``QIcon`` for buttons/actions."""
    pixmap = icon_pixmap(name, color, size)
    return QIcon(pixmap) if pixmap is not None and not pixmap.isNull() else QIcon()


def clear_icon_cache() -> None:
    """Clear cached pixmaps when the active pack or palette changes."""
    _cached_icon_pixmap.cache_clear()

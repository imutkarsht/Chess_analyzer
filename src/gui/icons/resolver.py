# SPDX-License-Identifier: GPL-3.0-only
"""Icon resolution across packs, variants, and bundled assets."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap

from src.gui.icons.manager import IconStyleManager
from src.gui.icons.spec import IconVariant
from src.gui.utils.assets import asset_path, resolve_asset

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:  # pragma: no cover - QtAwesome ships with the app
    qta = None
    HAS_QTAWESOME = False


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


def _load_pixmap(path: Path, size: int) -> QPixmap | None:
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    return pixmap.scaled(
        size,
        size,
        aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio,
        transformMode=Qt.TransformationMode.SmoothTransformation,
    )


@lru_cache(maxsize=512)
def _cached_icon_pixmap(
    name: str,
    color: str,
    size: int,
    pack_id: str,
    variant: str,
    scale_factor: float,
) -> QPixmap | None:
    if not name or size <= 0:
        return None

    path = _resolve_icon_path(name)
    if path is not None:
        pixmap = _load_pixmap(path, size)
        if pixmap is not None:
            return pixmap

    for glyph in IconStyleManager.resolve_glyphs(name, variant, pack_id):
        glyph_path = _resolve_icon_path(glyph)
        if glyph_path is not None:
            pixmap = _load_pixmap(glyph_path, size)
            if pixmap is not None:
                return pixmap

        if HAS_QTAWESOME and qta is not None:
            try:
                pixmap = qta.icon(
                    glyph, color=color, scale_factor=scale_factor
                ).pixmap(size, size)
            except Exception:
                continue
            if pixmap is not None and not pixmap.isNull():
                return pixmap
    return None


def icon_pixmap(
    name: str,
    color: str,
    size: int,
    variant: IconVariant | str | None = None,
) -> QPixmap | None:
    """Resolve an icon key or asset path to a themed pixmap."""
    if isinstance(variant, IconVariant):
        variant_value = variant.value
    else:
        variant_value = str(variant or "")
    return _cached_icon_pixmap(
        name,
        color,
        size,
        IconStyleManager.active_pack_id(),
        variant_value,
        IconStyleManager.active_pack().scale_factor,
    )


def icon_qicon(
    name: str,
    color: str,
    size: int = 16,
    variant: IconVariant | str | None = None,
) -> QIcon:
    """Resolve an icon key or asset path to a vector ``QIcon``.

    QtAwesome and SVG assets keep their scalable icon engines so Qt can render
    them at the display's device pixel ratio instead of scaling a small bitmap.
    """
    if isinstance(variant, IconVariant):
        variant_value = variant.value
    else:
        variant_value = str(variant or "")

    path = _resolve_icon_path(name)
    if path is not None:
        return QIcon(str(path))

    scale_factor = IconStyleManager.active_pack().scale_factor
    for glyph in IconStyleManager.resolve_glyphs(name, variant_value):
        glyph_path = _resolve_icon_path(glyph)
        if glyph_path is not None:
            return QIcon(str(glyph_path))
        if HAS_QTAWESOME and qta is not None:
            try:
                icon = qta.icon(
                    glyph, color=color, scale_factor=scale_factor
                )
            except Exception:
                continue
            if not icon.isNull():
                return icon
    return QIcon()


def clear_icon_cache() -> None:
    """Clear cached pixmaps when the active pack, variant, or palette changes."""
    _cached_icon_pixmap.cache_clear()

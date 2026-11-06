# SPDX-License-Identifier: GPL-3.0-only
"""Shared icon resolution for labels and painted widgets."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap

from src.utils.path_utils import get_resource_path

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:  # pragma: no cover - QtAwesome ships with the app
    qta = None
    HAS_QTAWESOME = False

_ASSET_DIRS = ("assets/icons", "assets/images", "assets")


def _resolve_icon_path(name: str) -> Path | None:
    path = Path(name)
    if path.is_absolute() and path.exists():
        return path
    for directory in _ASSET_DIRS:
        candidate = Path(get_resource_path(str(Path(directory) / name)))
        if candidate.exists():
            return candidate
    return None


@lru_cache(maxsize=256)
def icon_pixmap(name: str, color: str, size: int) -> QPixmap | None:
    """Resolve a qtawesome name or asset file to a themed pixmap.

    The cache is keyed by name, colour, and size so repeated card renders do
    not re-read SVG assets or rebuild QtAwesome icons.
    """
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

    if HAS_QTAWESOME and qta is not None:
        try:
            return qta.icon(name, color=color).pixmap(size, size)
        except Exception:
            return None
    return None


def icon_qicon(name: str, color: str) -> QIcon:
    """Resolve a qtawesome name or asset file to a ``QIcon`` for buttons."""
    path = _resolve_icon_path(name)
    if path is not None:
        return QIcon(str(path))
    if HAS_QTAWESOME and qta is not None:
        try:
            return qta.icon(name, color=color)
        except Exception:
            pass
    return QIcon()


def clear_icon_cache() -> None:
    """Clear cached pixmaps when the active palette changes."""
    icon_pixmap.cache_clear()

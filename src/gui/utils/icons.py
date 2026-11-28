# SPDX-License-Identifier: GPL-3.0-only
"""Compatibility re-export for the central icon system.

New code should import from :mod:`src.gui.icons`.
"""

from src.gui.icons import (
    DEFAULT_ICON_PACK_ID,
    HAS_QTAWESOME,
    IconPack,
    IconSpec,
    IconStyleManager,
    IconVariant,
    clear_icon_cache,
    icon_key,
    icon_pixmap,
    icon_qicon,
)

__all__ = [
    "DEFAULT_ICON_PACK_ID",
    "HAS_QTAWESOME",
    "IconPack",
    "IconSpec",
    "IconStyleManager",
    "IconVariant",
    "clear_icon_cache",
    "icon_key",
    "icon_pixmap",
    "icon_qicon",
]

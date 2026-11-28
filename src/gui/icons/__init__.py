# SPDX-License-Identifier: GPL-3.0-only
"""Central icon system: specs, packs, variants, and resolution."""

from src.gui.icons.manager import IconStyleManager
from src.gui.icons.packs import (
    DEFAULT_ICON_PACK_ID,
    FontAwesomePack,
    IconPack,
    PhosphorPack,
)
from src.gui.icons.resolver import (
    HAS_QTAWESOME,
    clear_icon_cache,
    icon_key,
    icon_pixmap,
    icon_qicon,
)
from src.gui.icons.spec import IconSpec, IconVariant

__all__ = [
    "DEFAULT_ICON_PACK_ID",
    "FontAwesomePack",
    "HAS_QTAWESOME",
    "IconPack",
    "IconSpec",
    "IconStyleManager",
    "IconVariant",
    "PhosphorPack",
    "clear_icon_cache",
    "icon_key",
    "icon_pixmap",
    "icon_qicon",
]

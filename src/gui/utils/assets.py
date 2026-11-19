# SPDX-License-Identifier: GPL-3.0-only
"""Shared asset path resolution for GUI widgets and styles."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from src.constants import APP_LOGO_PATH
from src.utils.path_utils import get_resource_path

_ASSET_DIRS = ("assets/images", "assets/icons", "assets")


def asset_path(relative_path: str) -> str:
    """Resolve a bundled asset path with forward slashes for QSS/SVG."""
    return get_resource_path(relative_path).replace("\\", "/")


def icon_path(filename: str) -> str:
    """Resolve a file inside ``assets/icons``."""
    return asset_path(f"assets/icons/{filename}")


def tick_icon_path() -> str:
    """Path used by themed checkbox styles."""
    return asset_path("assets/images/tick.svg")


def app_logo_path() -> str:
    """Path to the bundled application logo."""
    return asset_path(APP_LOGO_PATH)


@lru_cache(maxsize=256)
def resolve_asset(name: str) -> str | None:
    """Find an asset by bare filename across images, icons, and assets roots."""
    if not name:
        return None

    path = Path(name)
    if path.is_absolute() and path.exists():
        return str(path)

    for directory in _ASSET_DIRS:
        candidate = Path(get_resource_path(str(Path(directory) / name)))
        if candidate.exists():
            return str(candidate)
    return None

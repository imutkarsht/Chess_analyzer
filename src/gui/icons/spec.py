# SPDX-License-Identifier: GPL-3.0-only
"""Icon specifications and variants."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class IconVariant(StrEnum):
    """Pack-defined icon weight or style."""

    DEFAULT = "default"
    SOLID = "solid"
    REGULAR = "regular"
    OUTLINE = "outline"


@dataclass(frozen=True)
class IconSpec:
    """A pack-independent icon request.

    ``name`` is a semantic key (``play``), a legacy qtawesome name
    (``fa5s.play``), or an asset path. ``variant`` selects a pack-defined
    weight/style; ``None`` follows the active icon variant.
    """

    name: str
    fallback: str = ""
    size: int | None = None
    tone: str | None = None
    color: str | None = None
    variant: IconVariant | str | None = None

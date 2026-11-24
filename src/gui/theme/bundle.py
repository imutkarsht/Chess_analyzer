# SPDX-License-Identifier: GPL-3.0-only
"""ThemeBundle: the complete definition of one installable theme.

Built-in bundles live in ``src/gui/theme/bundles/`` and are registered from
``src/gui/theme/__init__.py``. A plugin can ship its own bundle and call
``ThemeManager.register_bundle(bundle)`` at import time; it then appears in
the appearance picker and can be activated with ``set_bundle(id)``.

Import direction: ``palette`` -> ``bundle`` -> ``bundles/*`` -> ``__init__``.
``bundle.py`` must never import ``manager.py`` (circular import at startup).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.gui.theme.palette import (
    BOARD_THEMES,
    CLASSIFICATION_COLORS,
    TERMINATION_COLORS,
    TERMINATION_FALLBACK_COLOR,
    ThemePalette,
)


def _default_classification() -> dict[str, str]:
    return dict(CLASSIFICATION_COLORS)


def _default_termination() -> dict[str, str]:
    return dict(TERMINATION_COLORS)


def _default_boards() -> dict[str, dict]:
    return {name: dict(colors) for name, colors in BOARD_THEMES.items()}


@dataclass
class ThemeBundle:
    """Everything needed to describe one visual theme."""

    id: str
    display_name: str
    palette: ThemePalette
    # "dark" or "light"; selects the system rendering mode for native parts.
    mode: str = "dark"

    classification_colors: dict[str, str] = field(
        default_factory=_default_classification
    )
    termination_colors: dict[str, str] = field(default_factory=_default_termination)
    termination_fallback: str = TERMINATION_FALLBACK_COLOR
    board_themes: dict[str, dict] = field(default_factory=_default_boards)

    # Appended after the central template so a bundle can override or add
    # rules without editing theme_template.qss.
    extra_qss: str = ""


__all__ = ["ThemeBundle"]

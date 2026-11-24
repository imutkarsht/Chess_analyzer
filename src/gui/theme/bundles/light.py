# SPDX-License-Identifier: GPL-3.0-only
"""Built-in light theme bundle."""

from src.gui.theme.bundle import ThemeBundle
from src.gui.theme.palette import LIGHT

LIGHT_BUNDLE = ThemeBundle(
    id="light",
    display_name="Light",
    palette=LIGHT,
    mode="light",
)

__all__ = ["LIGHT_BUNDLE"]

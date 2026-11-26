# SPDX-License-Identifier: GPL-3.0-only
"""Built-in dark theme bundle."""

from src.gui.theme.bundle import ThemeBundle
from src.gui.theme.palette import DARK

DARK_BUNDLE = ThemeBundle(
    id="dark",
    display_name="Dark",
    palette=DARK,
    mode="dark",
    description="Dark interface that uses your selected accent colour.",
)

__all__ = ["DARK_BUNDLE"]

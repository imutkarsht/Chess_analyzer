"""Configuration for the shared engine-lines component."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EngineLinesConfig:
    """Per-page policy for :class:`EngineLinesWidget`.

    ``max_lines`` is the hard cap (MultiPV maxes out at 5).  The panel is
    sized to the number of lines it currently shows, up to ``visible_lines``;
    anything beyond that scrolls.
    """

    max_lines: int = 5
    visible_lines: int = 3
    row_height: int = 56
    row_spacing: int = 4
    show_eval: bool = True
    show_depth: bool = True
    clickable: bool = True
    compact: bool = False
    max_pv_plies: int = 12
    empty_text: str = "Waiting for engine…"

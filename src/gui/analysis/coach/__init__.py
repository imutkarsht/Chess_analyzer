# SPDX-License-Identifier: GPL-3.0-only
"""Coach tab building blocks: card, request lifecycle, and game summary."""

from src.gui.analysis.coach.card import CoachCardWidget, CoachState, is_llm_worthy
from src.gui.analysis.coach.panel import CoachPanel
from src.gui.analysis.coach.summary import SummaryPanel

__all__ = [
    "CoachCardWidget",
    "CoachPanel",
    "CoachState",
    "SummaryPanel",
    "is_llm_worthy",
]

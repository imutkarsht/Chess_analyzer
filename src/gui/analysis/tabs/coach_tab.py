# SPDX-License-Identifier: GPL-3.0-only
"""Coach tab: per-move explanation card plus the full-game AI summary."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QWidget

from src.backend.services.groq_service import GroqService
from src.gui.analysis.coach.panel import CoachPanel
from src.gui.analysis.coach.summary import SummaryPanel
from src.gui.styles import Styles


class CoachTab(QWidget):
    """Composes the two coach surfaces and relays their signals upward."""

    move_selected = pyqtSignal(int)
    # (FEN before the move, full UCI line) — replays an explanation line.
    line_requested = pyqtSignal(str, list)
    # (engine lines, FEN they belong to) — shown on the Evaluation tab.
    lines_requested = pyqtSignal(list, str)
    # (FEN the lines belong to, first move UCI) — opens variation mode.
    variation_requested = pyqtSignal(str, str)

    def __init__(self, groq_service: GroqService | None = None) -> None:
        super().__init__()
        Styles.apply_transparent(self, borderless=False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        self.coach_panel = CoachPanel(groq_service)
        self._relay(self.coach_panel)
        layout.addWidget(self.coach_panel)

        # Full-game report: the per-move card above answers "why this move?",
        # this answers "how did the whole game go?". It takes the rest of the
        # tab, so its action sits at the bottom.
        self.div_summary = QFrame()
        self.div_summary.setFrameShape(QFrame.Shape.HLine)
        self.div_summary.setStyleSheet(Styles.get_divider_style())
        layout.addWidget(self.div_summary)

        self.summary_panel = SummaryPanel(groq_service)
        layout.addWidget(self.summary_panel, stretch=1)

    def _relay(self, panel: CoachPanel) -> None:
        panel.move_selected.connect(self.move_selected.emit)
        panel.line_requested.connect(self.line_requested.emit)
        panel.lines_requested.connect(self.lines_requested.emit)
        panel.variation_requested.connect(self.variation_requested.emit)

    # ------------------------------------------------------------------
    # Delegation
    # ------------------------------------------------------------------

    def set_game(self, game, user_side: str | None) -> None:
        self.coach_panel.set_game(game)
        self.summary_panel.set_context(game, user_side)

    def render(self, game, user_side: str | None) -> None:
        """Refresh the stored report without clearing coach narratives."""
        self.summary_panel.set_context(game, user_side)

    def set_active(self, active: bool) -> None:
        self.coach_panel.set_active(active)

    @property
    def selected_index(self) -> int | None:
        return self.coach_panel.selected_index

    def set_selected_move(self, index: int) -> None:
        self.coach_panel.set_selected_move(index)

    def set_llm_service(self, service: GroqService) -> None:
        self.coach_panel.set_llm_service(service)
        self.summary_panel.set_llm_service(service)

    def refresh_styles(self) -> None:
        self.coach_panel.refresh_styles()
        self.div_summary.setStyleSheet(Styles.get_divider_style())
        self.summary_panel.refresh_styles()

    def shutdown(self) -> None:
        self.coach_panel.shutdown()
        self.summary_panel.shutdown()


__all__ = ["CoachTab"]

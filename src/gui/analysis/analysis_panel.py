"""
Analysis Panel - Tab container for evaluation, report, coach, and tactics.

Each tab owns its own widgets and state; the panel only gates tabs, routes
signals, and builds the per-game tactical reports (which need both sides).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from src.backend.analysis.metrics.filters import resolve_user_side
from src.backend.analysis.tactics import TACTICS_VERSION, analyze_game_tactics
from src.backend.analysis.tactics.report import (
    GameTacticsReport,
    build_game_tactics_report,
)
from src.backend.services.groq_service import GroqService
from src.gui.analysis.tabs import CoachTab, EvaluationTab, ReportTab, TacticsTab
from src.gui.components import Tabs, TabVariant
from src.gui.styles import Styles
from src.utils.config import ConfigManager
from src.utils.logger import logger

# Tabs that only make sense once the game has analysis results.
_TABS_REQUIRING_ANALYSIS = (1, 2, 3)
_TAB_LOCK_HINT = "Analyze this game to unlock this tab."


class AnalysisPanel(QWidget):
    cache_toggled = pyqtSignal(bool)
    # (FEN the lines belong to, first move UCI) — opens the board in variation mode.
    variation_requested = pyqtSignal(str, str)
    # (FEN before the move, full UCI line) — replays a coach explanation line.
    line_requested = pyqtSignal(str, list)
    # Board move index selected from the per-game Tactics tab.
    move_requested = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)
        self.layout.setContentsMargins(5, 5, 5, 5)

        self.config_manager = ConfigManager()
        self.current_game = None
        self._analysis_running = False

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Tabs: the shared segmented control. Expanding keeps the four
        # sections split evenly across the narrow analysis panel.
        self.tabs = Tabs(TabVariant.SEGMENTED, font_size=12, padding=(8, 10, 8, 10))
        self.layout.addWidget(self.tabs)

        # --- Tab 1: Evaluation ---
        self.evaluation_tab = EvaluationTab()
        self.evaluation_tab.cache_toggled.connect(self.cache_toggled.emit)
        self.evaluation_tab.variation_requested.connect(self.variation_requested.emit)
        self.tabs.add_tab("Evaluation", self.evaluation_tab)
        self._apply_tabs_style()

        # --- Tab 2: Report ---
        self.report_tab = ReportTab()
        self.tabs.add_tab("Report", self.report_tab)

        # --- Tab 3: Coach ---
        self.coach_tab = CoachTab(GroqService())
        self.coach_tab.move_selected.connect(self._on_coach_move_selected)
        self.coach_tab.line_requested.connect(self.line_requested.emit)
        self.coach_tab.lines_requested.connect(self._on_coach_lines_requested)
        self.coach_tab.variation_requested.connect(self.variation_requested.emit)
        self._coach_tab_index = self.tabs.add_tab("Coach", self.coach_tab)

        # --- Tab 4: Tactics ---
        self.tactics_tab = TacticsTab()
        self.tactics_tab.move_requested.connect(self.move_requested.emit)
        self._tactics_tab_index = self.tabs.add_tab("Tactics", self.tactics_tab)
        self._tactics_cache: dict[tuple[str, str], GameTacticsReport] = {}

        # Connect only once every tab exists: add_tab() selects the first tab.
        self.tabs.current_changed.connect(self._on_tab_changed)

    # ------------------------------------------------------------------
    # MainWindow-facing surface (delegates to the owning tabs)
    # ------------------------------------------------------------------

    @property
    def graph_widget(self):
        return self.evaluation_tab.graph_widget

    @property
    def toggle_checkbox(self):
        return self.evaluation_tab.toggle_checkbox

    @property
    def cache_checkbox(self):
        return self.evaluation_tab.cache_checkbox

    def update_lines(self, lines, fen: str | None = None) -> None:
        """Render White-perspective engine lines for the board position."""
        self.evaluation_tab.update_lines(lines, fen)

    def set_selected_move(self, index: int) -> None:
        self.coach_tab.set_selected_move(index)

    def set_llm_service(self, service: GroqService) -> None:
        self.coach_tab.set_llm_service(service)

    def set_analysis_running(self, running: bool):
        self._analysis_running = running
        self._tactics_cache.clear()
        self._update_tab_availability()
        if running:
            self.tactics_tab.show_empty("Analysis in progress…")
        elif (
            self._tactics_tab_index is not None
            and self.tabs.current_index() == self._tactics_tab_index
        ):
            self._ensure_tactics_reports()

    # ------------------------------------------------------------------
    # Game lifecycle
    # ------------------------------------------------------------------

    def set_game(self, game_analysis):
        self.current_game = game_analysis
        self.evaluation_tab.clear()
        self._tactics_cache.clear()
        self.tactics_tab.show_empty("Analyze this game to reveal its tactics.")
        self.coach_tab.set_game(game_analysis, self._user_side())
        self.refresh()

    def refresh(self):
        self._update_tab_availability()
        self._tactics_cache.clear()
        user_side = self._user_side()

        try:
            if not self.current_game:
                self.evaluation_tab.clear()
                self.report_tab.render(None, user_side)
                return

            self.evaluation_tab.clear()
            self.evaluation_tab.render(self.current_game)
            self.report_tab.render(self.current_game, user_side)
            self.coach_tab.render(self.current_game, user_side)
        except Exception as e:
            logger.error("Error refreshing AnalysisPanel: %s", e, exc_info=True)

        if (
            not self._analysis_running
            and self._tactics_tab_index is not None
            and self.tabs.current_index() == self._tactics_tab_index
        ):
            self._ensure_tactics_reports()

    # ------------------------------------------------------------------
    # Tab gating / routing
    # ------------------------------------------------------------------

    def _analysis_tabs_unlocked(self) -> bool:
        """True when the current game has analysis results and is not running."""
        if self._analysis_running or self.current_game is None:
            return False
        return getattr(self.current_game, "analyzed_moves_count", 0) > 0

    def _update_tab_availability(self) -> None:
        """Disable Report/Coach/Tactics until the current game has analysis."""
        unlocked = self._analysis_tabs_unlocked()
        for index in _TABS_REQUIRING_ANALYSIS:
            self.tabs.set_tab_enabled(index, unlocked)
            self.tabs.set_tab_tooltip(index, "" if unlocked else _TAB_LOCK_HINT)
        if not unlocked and self.tabs.current_index() in _TABS_REQUIRING_ANALYSIS:
            self.tabs.set_current_index(0)

    def _on_tab_changed(self, index):
        if index in _TABS_REQUIRING_ANALYSIS and not self._analysis_tabs_unlocked():
            self.tabs.set_current_index(0)
            return
        self.coach_tab.set_active(
            self._coach_tab_index is not None and index == self._coach_tab_index
        )
        if self._tactics_tab_index is not None and index == self._tactics_tab_index:
            self._ensure_tactics_reports()

    def _on_coach_move_selected(self, index: int) -> None:
        self.tactics_tab.set_selected_move(index)

    def _on_coach_lines_requested(self, lines, fen: str) -> None:
        """The coach's replay lines live on the Evaluation tab."""
        self.update_lines(lines, fen)
        self.tabs.set_current_index(0)

    # ------------------------------------------------------------------
    # Tactics tab
    # ------------------------------------------------------------------

    def _ensure_tactics_reports(self) -> None:
        """Build and render both side reports, reusing cached results."""
        if not self.current_game:
            self.tactics_tab.show_empty("Load a game to see its tactical insights.")
            return

        moves = getattr(self.current_game, "moves", None) or []
        if not moves:
            self.tactics_tab.show_empty("Analyze this game to reveal its tactics.")
            return
        if self._analysis_running:
            self.tactics_tab.show_empty("Analysis in progress…")
            return
        if not any(getattr(move, "classification", "") for move in moves):
            self.tactics_tab.show_empty("Analyze this game to reveal its tactics.")
            return

        meta = self.current_game.metadata
        result = getattr(meta, "result", "*") or "*"
        speed = getattr(meta, "speed_category", "Blitz") or "Blitz"
        game_id = str(getattr(self.current_game, "game_id", "") or "")
        moves_data = [move.to_dict() for move in moves]

        reports: dict[str, GameTacticsReport] = {}
        for side in ("white", "black"):
            key = (game_id, side)
            report = self._tactics_cache.get(key)
            if report is None:
                tactics = self._stored_or_compute_tactics(
                    side, moves_data, result, speed
                )
                report = build_game_tactics_report(tactics, moves, side)
                self._tactics_cache[key] = report
            reports[side] = report

        self.tactics_tab.set_reports(
            reports,
            self._user_side() or "white",
            {"white": meta.white or "", "black": meta.black or ""},
            result,
        )
        selected = self.coach_tab.selected_index
        if selected is not None:
            self.tactics_tab.set_selected_move(selected)

    def _stored_or_compute_tactics(
        self,
        side: str,
        moves_data: list[dict],
        result: str,
        speed: str,
    ) -> dict:
        summary = getattr(self.current_game, "summary", None) or {}
        stored = (summary.get(side) or {}).get("tactics")
        if isinstance(stored, dict) and stored.get("tactics_version") == TACTICS_VERSION:
            return stored
        return analyze_game_tactics(moves_data, side, result, speed)

    def _user_side(self) -> str | None:
        """Which colour the configured Chess.com/Lichess username played."""
        if not self.current_game:
            return None
        meta = self.current_game.metadata
        return resolve_user_side(
            meta.white, meta.black, self.config_manager.player_usernames
        )

    # ------------------------------------------------------------------
    # Theme / lifecycle
    # ------------------------------------------------------------------

    def refresh_styles(self):
        """Re-applies styles to every tab from the live palette."""
        Styles.apply_background(self)
        self.evaluation_tab.refresh_styles()
        self.report_tab.refresh_styles()
        self.coach_tab.refresh_styles()
        self.tactics_tab.refresh_styles()
        self.tabs.refresh_styles()

    def _apply_tabs_style(self):
        """Regenerates the tab stylesheet from the active theme."""
        self.tabs.refresh_styles()

    def shutdown(self) -> None:
        """Stop the summary/coach workers owned by the tab children."""
        self.coach_tab.shutdown()

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)

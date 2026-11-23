# SPDX-License-Identifier: GPL-3.0-only
"""Per-move coach card: deterministic insight plus on-demand LLM explanation."""

from __future__ import annotations

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from src.backend.analysis.tactics.insight import MoveInsight, build_move_insight
from src.backend.services.groq_service import GroqService
from src.backend.storage.cache import AnalysisCache
from src.constants import (
    EXPLANATION_DEBOUNCE_MS,
    EXPLANATION_PROMPT_VERSION,
    normalize_coach_persona,
)
from src.gui.analysis.coach_card_widget import CoachCardWidget
from src.gui.analysis.line_utils import lines_for_move
from src.gui.components import ToastManager, open_llm_settings
from src.gui.utils.worker_registry import register_worker, remove_worker
from src.utils.config import ConfigManager
from src.utils.logger import logger
from src.workers.analysis import ExplainMoveWorker, RequestLimiter


class CoachPanel(QWidget):
    """Owns the coach request lifecycle and the card that renders it."""

    move_selected = pyqtSignal(int)
    # (FEN before the move, full UCI line) — replays an explanation line.
    line_requested = pyqtSignal(str, list)
    # (FEN the lines belong to, first move UCI) — opens variation mode.
    lines_requested = pyqtSignal(list, str)
    variation_requested = pyqtSignal(str, str)

    def __init__(self, groq_service: GroqService | None = None) -> None:
        super().__init__()
        self.config_manager = ConfigManager()
        self.groq_service = groq_service or GroqService()
        self.current_game = None
        self._active = False
        self._selected_index: int | None = None
        self._coach_seq = 0
        self._coach_insight: MoveInsight | None = None
        self._coach_worker: ExplainMoveWorker | None = None
        # Rendered explanations are retained per (game, ply) so returning to a
        # move does not need a SQLite read on the GUI thread.
        self._coach_narratives: dict[
            tuple[str, int], tuple[tuple[str, str, str, int], str]
        ] = {}
        self._coach_limiter = RequestLimiter()
        self._coach_debounce = QTimer(self)
        self._coach_debounce.setSingleShot(True)
        self._coach_debounce.timeout.connect(self._dispatch_explanation)
        self._explanation_cache: AnalysisCache | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.coach_card = CoachCardWidget()
        self.coach_card.ask_requested.connect(self._on_coach_ask_requested)
        self.coach_card.best_move_requested.connect(self.replay_best)
        self.coach_card.line_requested.connect(self.line_requested.emit)
        layout.addWidget(self.coach_card)

    # ------------------------------------------------------------------
    # Game / selection lifecycle
    # ------------------------------------------------------------------

    def set_game(self, game) -> None:
        previous_id = getattr(self.current_game, "game_id", None)
        if previous_id != getattr(game, "game_id", None):
            self._coach_narratives.clear()
        self.current_game = game
        self.set_selected_move(-1)

    def set_active(self, active: bool) -> None:
        """Build the pending insight only once the Coach tab is visible."""
        self._active = active
        if active:
            self._ensure_coach_insight()

    @property
    def selected_index(self) -> int | None:
        return self._selected_index

    def set_selected_move(self, index: int) -> None:
        """
        Track the selected move and rebuild Coach facts only when visible.

        Building the deterministic insight costs a few milliseconds per move;
        the hidden Coach tab does not need it, so it is deferred until the tab
        is opened or an explanation is requested. Any in-flight explanation
        belongs to the previous move and is cancelled without waiting (D6).
        """
        self._coach_debounce.stop()
        self._cancel_explanation_worker()

        moves = getattr(self.current_game, "moves", None) if self.current_game else None
        valid = bool(moves and 0 <= index < len(moves))
        self._selected_index = index if valid else None
        self._coach_insight = None
        self.move_selected.emit(index if valid else -1)

        if valid and self._active:
            self._ensure_coach_insight()
        else:
            self.coach_card.set_insight(
                None, allow_trivial=self._allow_trivial_explanations()
            )

    def _ensure_coach_insight(self) -> None:
        """Build the selected move's insight lazily, once, when the tab needs it."""
        if self._coach_insight is not None or self._selected_index is None:
            return
        moves = getattr(self.current_game, "moves", None) if self.current_game else None
        if not moves or not 0 <= self._selected_index < len(moves):
            return
        meta = self.current_game.metadata
        try:
            insight = build_move_insight(
                moves,
                self._selected_index,
                metadata=meta,
                chess960=bool(getattr(meta, "chess960", False)),
            )
        except Exception as e:
            logger.error(
                "Failed to build move insight for index %s: %s",
                self._selected_index,
                e,
                exc_info=True,
            )
            return
        self._coach_insight = insight
        self.coach_card.set_insight(
            insight, allow_trivial=self._allow_trivial_explanations()
        )
        if insight is not None:
            self._restore_memorized_explanation(insight)

    # ------------------------------------------------------------------
    # Explanation request lifecycle
    # ------------------------------------------------------------------

    def _coach_identity(self) -> tuple[str, str, str, int]:
        """The axes that make a retained explanation valid for the current settings."""
        return (
            normalize_coach_persona(self.config_manager.coach_persona),
            self.groq_service.model_name,
            self.groq_service._lang_code(),
            EXPLANATION_PROMPT_VERSION,
        )

    def _restore_memorized_explanation(self, insight: MoveInsight) -> None:
        """Show a rendered explanation when returning to the same move."""
        game_id = getattr(self.current_game, "game_id", "")
        stored = self._coach_narratives.get((game_id, insight.ply))
        if stored is not None and stored[0] == self._coach_identity():
            self.coach_card.show_cached(stored[1])

    def _allow_trivial_explanations(self) -> bool:
        return self.config_manager.explain_llm_for_trivial_moves

    def _on_coach_ask_requested(self) -> None:
        self._ensure_coach_insight()
        if self._coach_insight is None:
            return
        if not self.groq_service.client:
            open_llm_settings(self)
            return
        # Debounce so rapid clicking or move-hopping fires a single request.
        self._coach_debounce.start(EXPLANATION_DEBOUNCE_MS)

    def _dispatch_explanation(self) -> None:
        self._ensure_coach_insight()
        insight = self._coach_insight
        if insight is None:
            return
        if not self._coach_limiter.allow():
            logger.info("Coach request rate-limited")
            self._toast("Slow down a moment — coach is cooling off.")
            return

        self._cancel_explanation_worker()
        self._coach_seq += 1
        self.coach_card.begin_loading(self._coach_seq, insight.ply)

        worker = ExplainMoveWorker(
            self.groq_service,
            insight,
            seq=self._coach_seq,
            cache=self._get_explanation_cache(),
            lang_code=self.groq_service._lang_code(),
            model_name=self.groq_service.model_name,
            persona=normalize_coach_persona(self.config_manager.coach_persona),
        )
        worker.finished.connect(self._on_coach_finished)
        worker.error.connect(self._on_coach_error)
        self._coach_worker = worker
        worker.start()

    def _on_coach_finished(self, seq: int, ply: int, text: str) -> None:
        if self.coach_card.show_narrative(seq, ply, text):
            game_id = getattr(self.current_game, "game_id", "")
            self._coach_narratives[(game_id, ply)] = (self._coach_identity(), text)
            logger.info("Coach explanation rendered (ply=%d)", ply)

    def _on_coach_error(self, seq: int, ply: int, reason: str) -> None:
        logger.warning("Coach explanation unavailable (ply=%d): %s", ply, reason)
        self.coach_card.show_fallback(seq, ply, reason)

    def _cancel_explanation_worker(self) -> None:
        """Disconnect + interrupt + join the worker; never terminate a thread."""
        worker, self._coach_worker = self._coach_worker, None
        if worker is None:
            return
        for signal in (worker.finished, worker.error):
            try:
                signal.disconnect()
            except TypeError:
                pass  # nothing connected
        done = getattr(worker, "done", None)
        if done is not None:
            register_worker(worker)
            done.connect(lambda w=worker: remove_worker(w))
        worker.cancel()
        if done is not None and worker.isFinished():
            remove_worker(worker)

    def _get_explanation_cache(self) -> AnalysisCache | None:
        if self._explanation_cache is None:
            try:
                self._explanation_cache = AnalysisCache()
            except Exception as e:
                logger.error("Failed to open the explanation cache: %s", e)
                return None
        return self._explanation_cache

    def replay_best(self) -> None:
        """Show the engine's top choice from the played move's position."""
        self._ensure_coach_insight()
        insight = self._coach_insight
        moves = getattr(self.current_game, "moves", None) if self.current_game else None
        if insight is None or not moves:
            return
        played_index = insight.ply  # ply is 0-based and indexes ``moves`` directly
        if not 0 <= played_index < len(moves):
            return
        played = moves[played_index]
        if not played.multi_pvs:
            return

        lines, _lines_fen = lines_for_move(played, chess960=self._is_chess960())
        self.lines_requested.emit(lines, played.fen_before)

        best_uci = insight.best_move_uci
        if not best_uci:
            pv = played.multi_pvs[0].get("pv_uci") or played.multi_pvs[0].get("pv") or []
            best_uci = pv[0] if pv else None
            if best_uci is not None and not isinstance(best_uci, str):
                best_uci = best_uci.uci()
        if best_uci:
            self.variation_requested.emit(played.fen_before, best_uci)

    def _is_chess960(self) -> bool:
        meta = getattr(self.current_game, "metadata", None)
        return bool(getattr(meta, "chess960", False))

    def _toast(self, message: str) -> None:
        ToastManager.info(self, message)

    # ------------------------------------------------------------------
    # Lifecycle / theme
    # ------------------------------------------------------------------

    def set_llm_service(self, service: GroqService) -> None:
        self.groq_service = service

    def refresh_styles(self) -> None:
        self.coach_card.refresh_styles()

    def shutdown(self) -> None:
        self._coach_debounce.stop()
        self._cancel_explanation_worker()
        if self._explanation_cache is not None:
            self._explanation_cache.close()
            self._explanation_cache = None

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)

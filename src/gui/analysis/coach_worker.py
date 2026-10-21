"""
Off-UI-thread worker for the Coach move-explanation feature.

All network work (cache lookup, LLM request, reply validation, cache write)
happens inside :class:`ExplainMoveWorker.run`, which is executed by Qt on a
worker thread. The worker only ever communicates back through ``pyqtSignal``.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

from PyQt6.QtCore import QThread, pyqtSignal

from src.backend.analysis.tactics.insight import (
    MoveInsight,
    format_move_insight_for_llm,
    insight_allowed_tokens,
)
from src.backend.services.groq_service import validate_explanation
from src.backend.storage.cache import AnalysisCache
from src.constants import (
    EXPLANATION_CACHE_TTL_DAYS,
    EXPLANATION_MAX_PER_MINUTE,
    EXPLANATION_MIN_INTERVAL_S,
    EXPLANATION_PROMPT_VERSION,
)
from src.utils.config import ConfigManager
from src.utils.logger import logger


class RequestLimiter:
    """
    Sliding-window guard against runaway LLM spend.

    Enforces both a minimum gap between requests and a per-minute cap. The
    clock is injectable so the behaviour is testable without sleeping.
    """

    def __init__(
        self,
        min_interval_s: float = EXPLANATION_MIN_INTERVAL_S,
        max_per_minute: int = EXPLANATION_MAX_PER_MINUTE,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._min_interval_s = min_interval_s
        self._max_per_minute = max_per_minute
        self._clock = clock
        self._recent: deque[float] = deque()

    def _prune(self, now: float) -> None:
        cutoff = now - 60.0
        while self._recent and self._recent[0] < cutoff:
            self._recent.popleft()

    def allow(self) -> bool:
        """Return True and consume a slot if a request may start right now."""
        now = self._clock()
        self._prune(now)
        if self._recent and now - self._recent[-1] < self._min_interval_s:
            return False
        if len(self._recent) >= self._max_per_minute:
            return False
        self._recent.append(now)
        return True


class ExplainMoveWorker(QThread):
    """
    Fetch one move explanation.

    Flow: cache hit -> emit immediately with no network; otherwise ask the
    service, validate the reply against the insight's allowed tokens, cache it,
    and emit. A missing/invalid/erroring reply reports through ``error`` and the
    card keeps showing the deterministic offline text.
    """

    finished = pyqtSignal(int, int, str)  # seq, ply, validated narrative
    error = pyqtSignal(int, int, str)  # seq, ply, human-readable reason

    def __init__(
        self,
        service,
        insight: MoveInsight,
        *,
        seq: int,
        cache: AnalysisCache | None = None,
        lang_code: str = "en",
        model_name: str = "",
        force: bool = False,
    ) -> None:
        super().__init__()
        self._service = service
        self._insight = insight
        self._seq = seq
        self._cache = cache
        self._lang_code = lang_code
        self._model = model_name or getattr(service, "model_name", "") or "unknown"
        self._force = force
        self._ttl_days = ConfigManager().get("explain_cache_ttl_days", EXPLANATION_CACHE_TTL_DAYS)
        self._cancelled = False

    def cancel(self) -> None:
        """
        Ask the thread to abandon its result (never terminates it).

        ``requestInterruption()`` is a no-op while the thread has not started
        yet, so an explicit flag covers the cancel-before-start race.
        """
        self._cancelled = True
        self.requestInterruption()

    def _is_cancelled(self) -> bool:
        return self._cancelled or self.isInterruptionRequested()

    def run(self) -> None:  # noqa: D102 - Qt entry point
        insight = self._insight
        try:
            cached = None if self._force else self._read_cache()
            if self._is_cancelled():
                return
            if cached is not None:
                logger.info("Coach explanation served from cache (ply=%d)", insight.ply)
                self.finished.emit(self._seq, insight.ply, cached)
                return

            reply = self._service.explain_move(
                format_move_insight_for_llm(insight), insight.classification
            )
            if self._is_cancelled():
                return
            if not reply or reply.lstrip().startswith("Error"):
                logger.warning("Coach explanation unavailable: %s", reply)
                self.error.emit(self._seq, insight.ply, reply or "No response generated.")
                return

            allowed_san, allowed_squares = insight_allowed_tokens(insight)
            is_valid, offending = validate_explanation(reply, allowed_san, allowed_squares)
            if not is_valid:
                self.error.emit(
                    self._seq,
                    insight.ply,
                    f"Coach mentioned unknown moves or squares: {', '.join(offending)}",
                )
                return

            self._write_cache(reply)
            self.finished.emit(self._seq, insight.ply, reply)
        except Exception as exc:  # noqa: BLE001 - a failed explanation must never crash the app
            logger.error("Coach explanation worker failed: %s", exc, exc_info=True)
            self.error.emit(self._seq, insight.ply, str(exc))

    # ------------------------------------------------------------------
    # Cache helpers (both are no-ops when no cache was supplied)
    # ------------------------------------------------------------------

    def _read_cache(self) -> str | None:
        if self._cache is None:
            return None
        return self._cache.get_explanation(
            self._insight.fen_before,
            self._insight.uci,
            self._model,
            self._lang_code,
            EXPLANATION_PROMPT_VERSION,
            max_age_days=self._ttl_days,
        )

    def _write_cache(self, reply: str) -> None:
        if self._cache is None:
            return
        self._cache.set_explanation(
            self._insight.fen_before,
            self._insight.uci,
            self._model,
            self._lang_code,
            EXPLANATION_PROMPT_VERSION,
            reply,
            max_age_days=self._ttl_days,
        )

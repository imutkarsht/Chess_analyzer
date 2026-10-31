"""Online Lichess explorer orchestration and offline/cache fallbacks."""

import json
import time

from PyQt6.QtCore import QTimer

from src.backend.analysis.opening_db import _normalize_fen
from src.backend.api.import_limits import current_token
from src.backend.storage.game_history import GameHistoryManager
from src.gui.views.explorer.lichess_worker import LichessExplorerWorker
from src.utils.logger import logger


class ExplorerOnlineMixin:
    """Owns the token gate, cache, debounce and Lichess worker lifecycle."""

    def _init_online_explorer(self) -> None:
        # Lichess requires a token for explorer requests. Debounce move
        # stepping, coalesce to the latest FEN, rate-limit to the account's
        # 20 req/min budget, and stop retrying for a while after failures.
        self._history_manager = None
        self._explorer_workers: set[LichessExplorerWorker] = set()
        self._explorer_worker: LichessExplorerWorker | None = None
        self._explorer_pending_fen: str | None = None
        self._explorer_failures = 0
        self._explorer_offline_until = 0.0
        # 20 requests/minute = one every 3s. Cached positions render before
        # this gate, so only real network requests consume the budget.
        self._explorer_min_interval = 3.0
        self._explorer_last_request = 0.0
        self._explorer_debounce = QTimer(self)
        self._explorer_debounce.setSingleShot(True)
        self._explorer_debounce.setInterval(180)
        self._explorer_debounce.timeout.connect(self._start_lichess_explorer)

    # ------------------------------------------------------------------
    # Gate + cache
    # ------------------------------------------------------------------

    def _history(self) -> GameHistoryManager:
        """Lazily share one history/cache manager across workers."""
        manager = getattr(self, "_history_manager", None)
        if manager is None:
            manager = GameHistoryManager()
            self._history_manager = manager
        return manager

    def _explorer_enabled(self) -> bool:
        try:
            return bool(self.config_manager.get("lichess_explorer_enabled", True))
        except Exception:
            return True

    def _online_explorer_allowed(self) -> bool:
        """Whether the online explorer is enabled, authorised, and not cooling down."""
        return (
            bool(current_token(self.config_manager))
            and self._explorer_enabled()
            and time.time() >= self._explorer_offline_until
        )

    def _explorer_disabled_reason(self) -> str:
        """Human-readable reason the online explorer is not being used."""
        if not current_token(self.config_manager):
            return "Add a Lichess token in Settings → Integrations to load online explorer data."
        if not self._explorer_enabled():
            return "Online explorer is disabled in Settings → Integrations."
        return ""

    def _render_cached_explorer(self, fen: str) -> bool:
        """Render a cached explorer response so offline use needs no token."""
        if not self.chk_cache.isChecked():
            return False
        try:
            raw = self._history().get_explorer_cache(_normalize_fen(fen))
            data = json.loads(raw) if raw else None
        except Exception:
            return False
        if not isinstance(data, dict) or not data.get("moves"):
            return False
        self.on_lichess_explorer_finished(data)
        return True

    def _update_explorer_hint(self, message: str | None = None) -> None:
        """Show the token/settings hint when online data is unavailable."""
        text = message if message is not None else self._explorer_disabled_reason()
        if text:
            self.explorer_hint.setText(text)
            self.explorer_hint.show()
        else:
            self.explorer_hint.clear()
            self.explorer_hint.hide()

    # ------------------------------------------------------------------
    # Position update
    # ------------------------------------------------------------------

    def update_opening_db(self, fen):
        norm_fen = _normalize_fen(fen)
        node_id = self.opening_db.get_node_by_fen(norm_fen)

        if not self.board_widget.board.move_stack:
            self.opening_badge.setText("Opening: -")

        if node_id is not None:
            openings = self.opening_db.get_openings_at_node(node_id)
            if openings:
                best = max(openings, key=lambda x: len(x[1]))
                self.opening_badge.setText(f"Opening: {best[0]} - {best[1]}")

        if not self._online_explorer_allowed():
            self._explorer_pending_fen = None
            self._explorer_debounce.stop()
            hint = ""
            cached_shown = self._explorer_enabled() and self._render_cached_explorer(
                self.board_widget.board.fen()
            )
            if cached_shown:
                if not current_token(self.config_manager):
                    hint = (
                        "Showing cached explorer data. Add a Lichess token in "
                        "Settings → Integrations for live updates."
                    )
            else:
                self._draw_local_book(node_id)
                if self._current_book_count:
                    self._update_book_toggle("  · local book")
                self.lichess_attribution.setVisible(False)
            self._update_explorer_hint(hint or None)
            self.board_widget.draw_interactive_overlays()
            return

        self._update_explorer_hint("")

        # Cached responses render instantly and the worker would only return
        # the same cache, so skip both the skeleton and the rate-limited fetch.
        if self._render_cached_explorer(self.board_widget.board.fen()):
            self._explorer_pending_fen = None
            self._explorer_debounce.stop()
            self.board_widget.draw_interactive_overlays()
            return

        # Never paint the local book while a live lookup is in flight: the
        # skeleton makes it clear the panel is still loading.
        self._show_book_skeleton()
        self._explorer_pending_fen = self.board_widget.board.fen()
        self._explorer_debounce.start()
        self.board_widget.draw_interactive_overlays()

    # ------------------------------------------------------------------
    # Worker lifecycle
    # ------------------------------------------------------------------

    def _start_lichess_explorer(self) -> None:
        fen = self._explorer_pending_fen
        if not fen or not self._online_explorer_allowed():
            return
        if self._explorer_worker is not None and self._explorer_worker.isRunning():
            # The pending FEN is picked up when the active request retires.
            return

        # Stay inside the 20 requests/minute account budget. If we are early,
        # keep only the latest FEN and retry once the interval has elapsed.
        elapsed = time.time() - self._explorer_last_request
        remaining = self._explorer_min_interval - elapsed
        if remaining > 0:
            self._explorer_debounce.start(int(remaining * 1000) + 1)
            return

        self._explorer_pending_fen = None
        self._explorer_last_request = time.time()
        worker = LichessExplorerWorker(
            fen,
            self.chk_cache.isChecked(),
            self._history(),
            current_token(self.config_manager),
        )
        self._explorer_workers.add(worker)
        self._explorer_worker = worker
        worker.loaded.connect(
            lambda data, w=worker: self._on_explorer_data(w, data)
        )
        worker.error.connect(
            lambda message, w=worker: self._on_explorer_error(w, message)
        )
        worker.finished.connect(
            lambda w=worker: self._retire_explorer_worker(w)
        )
        worker.start()

    def _retire_explorer_worker(self, worker: LichessExplorerWorker) -> None:
        self._explorer_workers.discard(worker)
        worker.deleteLater()
        if worker is self._explorer_worker:
            self._explorer_worker = None
        if self._explorer_pending_fen and self._online_explorer_allowed():
            QTimer.singleShot(0, self._start_lichess_explorer)

    def _is_worker_current(self, worker: LichessExplorerWorker) -> bool:
        """Ignore a result that belongs to a position the user already left."""
        if worker is not self._explorer_worker:
            return False
        try:
            current_fen = self.board_widget.board.fen()
        except Exception:
            return False
        return _normalize_fen(worker.fen) == _normalize_fen(current_fen)

    def _on_explorer_data(self, worker: LichessExplorerWorker, data) -> None:
        if not self._is_worker_current(worker):
            return
        self._explorer_failures = 0
        if not isinstance(data, dict):
            self._on_explorer_error(worker, "invalid_response")
            return
        if not data.get("moves"):
            # A valid but empty response should still show the local book.
            self._draw_local_book_fallback()
            return
        self._update_explorer_hint("")
        self.on_lichess_explorer_finished(data)

    def _on_explorer_error(
        self, worker: LichessExplorerWorker, message: str
    ) -> None:
        if not self._is_worker_current(worker):
            return
        logger.warning(f"Lichess explorer fetch failed: {message}")
        self._explorer_failures += 1
        if message == "unauthorized":
            self._update_explorer_hint(
                "Lichess rejected the explorer token. Update it in "
                "Settings → Integrations."
            )
        elif message in {"offline", "rate_limited"} or self._explorer_failures >= 3:
            cooldown = 300 if message == "offline" else 120
            self._explorer_offline_until = time.time() + cooldown
            logger.info(
                "Lichess explorer paused for %ss after: %s", cooldown, message
            )
        self._draw_local_book_fallback()

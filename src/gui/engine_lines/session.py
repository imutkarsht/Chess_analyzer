"""Shared live-engine session.

Both the Analysis page and the Explorer used to duplicate the same fragile
plumbing (sequence counter, ``live_data`` dict, thinking signals, engine
restarts).  This QObject owns that state once:

* every request carries a monotonic sequence number, so late results for a
  position the UI already left are discarded;
* :meth:`clear` bumps the sequence, which is what makes a cleared panel stay
  cleared even if a result was already queued;
* updates are coalesced (~8 Hz) so the engine cannot repaint the panel on
  every depth iteration;
* ``pause``/``resume`` stop the engine during a full analysis without losing
  the displayed lines;
* the engine process is started lazily on the first request.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from src.backend.analysis.engine_line import EngineLine
from src.constants import DEFAULT_MULTI_PV
from src.gui.analysis.live_analysis import LiveAnalysisWorker
from src.utils.logger import logger


class LiveEngineSession(QObject):
    """Owns one :class:`LiveAnalysisWorker` and its request lifecycle."""

    lines_changed = pyqtSignal(list)  # list[EngineLine], White perspective
    eval_changed = pyqtSignal(object, object)  # white cp, white mate
    state_changed = pyqtSignal(str)  # idle | thinking | ready | error
    error = pyqtSignal(str)

    def __init__(
        self,
        engine_path: str,
        config_manager=None,
        parent: QObject | None = None,
        *,
        debounce_ms: int = 0,
        throttle_ms: int = 120,
    ):
        super().__init__(parent)
        self._engine_path = engine_path
        self._config = config_manager
        self._worker: LiveAnalysisWorker | None = None

        self._seq = 0
        self._lines: dict[int, EngineLine] = {}
        self._pending: tuple[str, bool] | None = None
        self._fen: str | None = None
        self._enabled = True
        self._paused = False
        self._state = "idle"
        self._last_key: tuple = ()

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(max(0, debounce_ms))
        self._debounce.timeout.connect(self._dispatch)

        self._throttle = QTimer(self)
        self._throttle.setSingleShot(True)
        self._throttle.setInterval(max(0, throttle_ms))
        self._throttle.timeout.connect(self._flush)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def state(self) -> str:
        return self._state

    @property
    def current_fen(self) -> str | None:
        return self._fen

    def request(
        self,
        fen: str | None,
        *,
        chess960: bool = False,
        force: bool = False,
        emit_empty: bool = False,
    ) -> None:
        """Analyse ``fen`` (debounced), discarding any older in-flight result.

        ``emit_empty`` clears the widget immediately; leave it off when the
        caller is showing cached lines until the first live result arrives.
        """
        if not fen:
            self.clear()
            return

        self._pending = (fen, bool(chess960))
        if not self._enabled or self._paused:
            return
        if (
            not force
            and fen == self._fen
            and self._lines
            and self._worker is not None
            and self._worker.isRunning()
        ):
            return

        self._seq += 1
        self._fen = fen
        self._lines.clear()
        self._last_key = ()
        self._throttle.stop()
        if emit_empty:
            self.lines_changed.emit([])

        if self._debounce.interval() > 0:
            self._debounce.start()
        else:
            self._dispatch()

    def clear(self, *, emit: bool = True) -> None:
        """Cancel analysis and forget the current position and lines."""
        self._seq += 1
        self._pending = None
        self._fen = None
        self._lines.clear()
        self._last_key = ()
        self._debounce.stop()
        self._throttle.stop()
        if self._worker is not None:
            self._worker.set_position(None, self._seq)
        if emit:
            self.lines_changed.emit([])
        self._set_state("idle")

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if not enabled:
            self._paused = True
            self.clear()
            return
        # Enabling engine lines must also undo a pause left over from the page
        # being hidden; the caller then requests the position it is showing.
        self._paused = False

    def pause(self) -> None:
        """Stop the engine (e.g. a full analysis needs the CPU) keeping lines."""
        self._paused = True
        self._debounce.stop()
        self._throttle.stop()
        self._seq += 1
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
        self._set_state("idle")

    def resume(self) -> None:
        """Re-enable analysis after :meth:`pause` without needless re-search."""
        self._paused = False
        if not self._enabled or self._pending is None:
            return
        fen, _chess960 = self._pending
        if self._lines and fen == self._fen:
            # Same position, results still valid: just bring the engine back.
            self._ensure_worker()
            return
        self._seq += 1
        self._lines.clear()
        self._last_key = ()
        self._dispatch()

    def set_engine_path(self, path: str) -> None:
        if path == self._engine_path and self._worker is not None:
            return
        self._engine_path = path
        self._dispose_worker()
        if self._enabled and not self._paused and self._pending is not None:
            self._seq += 1
            self._lines.clear()
            self._last_key = ()
            self._dispatch()

    def reconfigure(self) -> None:
        """Apply new Threads/Hash/MultiPV settings to the running engine."""
        if self._worker is not None:
            self._worker.configure_engine()
        if self._enabled and not self._paused and self._pending is not None:
            self.request(*self._pending, force=True)

    def shutdown(self) -> None:
        self._debounce.stop()
        self._throttle.stop()
        self._dispose_worker()

    # ------------------------------------------------------------------
    # Worker plumbing
    # ------------------------------------------------------------------
    def _ensure_worker(self) -> None:
        if self._worker is None:
            worker = LiveAnalysisWorker(
                self._engine_path, config_manager=self._config
            )
            worker.info_ready.connect(self._on_info)
            worker.thinking_started.connect(self._on_thinking_started)
            worker.thinking_stopped.connect(self._on_thinking_stopped)
            worker.error.connect(self._on_error)
            self._worker = worker
        if not self._worker.isRunning():
            self._worker.start()

    def _dispose_worker(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.stop()
            worker.deleteLater()

    def _dispatch(self) -> None:
        if self._paused or not self._enabled or self._pending is None:
            return
        fen, chess960 = self._pending
        self._ensure_worker()
        self._worker.set_chess960(chess960)
        self._worker.set_position(fen, self._seq)
        self._set_state("thinking")

    # ------------------------------------------------------------------
    # Worker signals
    # ------------------------------------------------------------------
    def _on_info(self, info: dict) -> None:
        if info.get("seq") != self._seq:
            return
        line = info.get("line")
        if not isinstance(line, EngineLine):
            return

        previous = self._lines.get(line.rank)
        if previous is not None:
            line = line.with_longer_pv(previous)
        self._lines[line.rank] = line
        limit = self._multi_pv()
        for rank in [rank for rank in self._lines if rank > limit]:
            del self._lines[rank]
        self._schedule_flush()

    def _on_thinking_started(self) -> None:
        self._set_state("thinking")

    def _on_thinking_stopped(self) -> None:
        self._flush()
        self._set_state("ready" if self._pending is not None else "idle")

    def _on_error(self, message: str) -> None:
        logger.warning("Live engine error: %s", message)
        self.error.emit(message)
        self._set_state("error")

    # ------------------------------------------------------------------
    # Coalesced rendering
    # ------------------------------------------------------------------
    def _schedule_flush(self) -> None:
        if self._throttle.interval() <= 0:
            self._flush()
        elif not self._throttle.isActive():
            self._throttle.start()

    def _flush(self) -> None:
        lines = [self._lines[rank] for rank in sorted(self._lines)]
        key = tuple(
            (line.rank, line.depth, line.cp, line.mate, line.pv_uci) for line in lines
        )
        if key == self._last_key:
            return
        self._last_key = key
        self.lines_changed.emit(lines)
        if lines:
            best = lines[0]
            self.eval_changed.emit(best.cp, best.mate)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _multi_pv(self) -> int:
        if self._config is not None:
            try:
                value = int(self._config.get("multi_pv", DEFAULT_MULTI_PV))
                if value >= 1:
                    return value
            except (TypeError, ValueError):
                pass
        return DEFAULT_MULTI_PV

    def _set_state(self, state: str) -> None:
        if state == self._state:
            return
        self._state = state
        self.state_changed.emit(state)

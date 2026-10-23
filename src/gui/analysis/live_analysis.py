"""Background Stockfish worker for live position analysis.

The worker owns the engine process and a single "analyse this FEN" loop.  It
emits White-perspective :class:`EngineLine` objects tagged with the sequence
number of the request they belong to, so consumers can discard results for a
position they have already left.
"""

import time

import chess
import chess.engine
from PyQt6.QtCore import QMutex, QThread, QWaitCondition, pyqtSignal

from src.backend.analysis.engine_line import line_from_engine_info
from src.constants import (
    DEFAULT_ANALYSIS_DEPTH,
    DEFAULT_ENGINE_HASH_MB,
    DEFAULT_ENGINE_THREADS,
    DEFAULT_LIVE_ANALYSIS_TIME,
    DEFAULT_MULTI_PV,
)
from src.utils.logger import logger


class LiveAnalysisWorker(QThread):
    # info: {"seq": int, "line": EngineLine}
    info_ready = pyqtSignal(dict)
    # Emitted when the engine starts / stops calculating a position
    thinking_started = pyqtSignal()
    thinking_stopped = pyqtSignal()
    # Emitted when the engine binary cannot be started or dies mid-analysis
    error = pyqtSignal(str)

    def __init__(self, engine_path, config_manager=None):
        super().__init__()
        self.engine_path = engine_path
        # Optional dependency.  When wired in (the normal path) the
        # worker respects the user's `live_analysis_time` and
        # `live_multi_pv` settings; when not provided we fall back
        # to the conservative hard-coded defaults below.  See
        # https://github.com/imutkarsht/Chess_analyzer/issues/5
        self.config_manager = config_manager
        self.engine = None
        self.board = chess.Board()
        self.running = True
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self.new_position = False
        self.current_fen = None
        self.current_seq = 0
        self.is_chess960 = False
        # UCI options that arrived while a search was running.  They are
        # applied between searches so `setoption` never interrupts a search.
        self._pending_options: dict = {}
        self._searching = False

    # ------------------------------------------------------------------
    # Config accessors with safe fallbacks.  We isolate the fallback
    # logic so the run() loop stays readable and so the defaults
    # match the new conservative settings (see issue #5).
    # ------------------------------------------------------------------
    def _live_time(self) -> float:
        if self.config_manager is not None:
            try:
                return float(self.config_manager.get("live_analysis_time", DEFAULT_LIVE_ANALYSIS_TIME))
            except (TypeError, ValueError):
                pass
        return DEFAULT_LIVE_ANALYSIS_TIME

    def _live_multi_pv(self) -> int:
        if self.config_manager is not None:
            try:
                value = int(self.config_manager.get("multi_pv", DEFAULT_MULTI_PV))
                if value >= 1:
                    return value
            except (TypeError, ValueError):
                pass
        return DEFAULT_MULTI_PV

    def _live_depth(self) -> int:
        if self.config_manager is not None:
            try:
                return int(self.config_manager.get("analysis_depth", DEFAULT_ANALYSIS_DEPTH))
            except (TypeError, ValueError):
                pass
        return DEFAULT_ANALYSIS_DEPTH

    def _threads(self) -> int:
        if self.config_manager is not None:
            try:
                return int(self.config_manager.get("engine_threads", DEFAULT_ENGINE_THREADS))
            except (TypeError, ValueError):
                pass
        return 1

    def _hash(self) -> int:
        if self.config_manager is not None:
            try:
                return int(self.config_manager.get("engine_hash", DEFAULT_ENGINE_HASH_MB))
            except (TypeError, ValueError):
                pass
        return DEFAULT_ENGINE_HASH_MB

    def _live_limit(self) -> chess.engine.Limit:
        """Search limit for one live position.

        ``live_analysis_time`` is the per-position CPU budget (issue #5);
        the depth ceiling only keeps the search bounded if the user raises
        that budget. Without the time limit the engine searched to
        ``analysis_depth + 6`` (e.g. depth 26) and saturated the CPU for
        tens of seconds after every move.
        """
        return chess.engine.Limit(
            time=self._live_time(),
            depth=self._live_depth() + 6,
        )

    # ------------------------------------------------------------------
    # Engine configuration (safe to call from the GUI thread)
    # ------------------------------------------------------------------
    def configure_engine(self):
        """Queue Threads/Hash for the next search, or apply them while idle."""
        self._queue_or_apply(
            {"Threads": self._threads(), "Hash": self._hash()}
        )
        logger.info(
            "Live engine reconfigured: Threads=%s, Hash=%s",
            self._threads(),
            self._hash(),
        )

    def set_chess960(self, enabled: bool):
        """Set Chess960 mode for the boards this worker creates.

        python-chess manages the ``UCI_Chess960`` option itself and raises
        ``ValueError: cannot set UCI_Chess960 which is automatically managed``
        if we try to configure it, so only the flag is stored here.
        """
        self.mutex.lock()
        self.is_chess960 = bool(enabled)
        self.mutex.unlock()

    def _queue_or_apply(self, options: dict) -> None:
        self.mutex.lock()
        self._pending_options.update(options)
        engine = self.engine
        searching = self._searching
        self.mutex.unlock()
        if engine is None or searching:
            return
        self._apply_pending_options(engine)

    def _apply_pending_options(self, engine) -> None:
        self.mutex.lock()
        options = self._pending_options
        self._pending_options = {}
        self.mutex.unlock()
        if not options:
            return
        try:
            engine.configure(options)
        except Exception as e:
            logger.error(f"Failed to configure live engine: {e}")

    # ------------------------------------------------------------------
    # Position requests
    # ------------------------------------------------------------------
    def set_position(self, fen, seq=0):
        """Updates the position to analyze. `seq` is a caller-supplied
        monotonic counter; when set, the worker includes it in every
        info_ready signal so the receiver can discard stale results."""
        self.mutex.lock()
        if fen != self.current_fen or seq != self.current_seq:
            self.current_fen = fen
            self.current_seq = seq
            self.new_position = True
            self.condition.wakeAll()
        self.mutex.unlock()

    def start(self, priority=QThread.Priority.InheritPriority):
        self.running = True
        super().start(priority)

    def stop(self):
        """Stops the worker thread, bounded so app shutdown cannot hang."""
        self.running = False
        self.mutex.lock()
        self.condition.wakeAll()
        self.mutex.unlock()
        if self.isRunning() and not self.wait(3000):
            logger.warning("Live analysis worker did not stop in time; terminating it.")
            self.terminate()
            self.wait(1000)

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------
    def run(self):
        self.running = True
        self.engine = None
        logger.info(f"LiveAnalysisWorker starting with engine: {self.engine_path}")
        try:
            import subprocess
            import sys

            popen_args = {}
            if sys.platform == "win32":
                popen_args["creationflags"] = subprocess.CREATE_NO_WINDOW
            self.engine = chess.engine.SimpleEngine.popen_uci(
                self.engine_path, **popen_args
            )
            self.engine.configure({"Threads": self._threads(), "Hash": self._hash()})

            while self.running:
                self.mutex.lock()
                # Wait until there is a new position to analyze
                while self.running and not self.new_position:
                    self.condition.wait(self.mutex)

                if not self.running:
                    self.mutex.unlock()
                    break

                # Read the FEN and its sequence atomically: a batch must never
                # be stamped with the sequence of a *newer* position.
                fen = self.current_fen
                batch_seq = self.current_seq
                chess960 = self.is_chess960
                self.new_position = False
                self.mutex.unlock()

                self._apply_pending_options(self.engine)

                if not fen:
                    continue

                try:
                    board = chess.Board(fen, chess960=chess960)
                    self.thinking_started.emit()
                    self.mutex.lock()
                    self._searching = True
                    self.mutex.unlock()
                    with self.engine.analysis(
                        board,
                        self._live_limit(),
                        multipv=self._live_multi_pv(),
                    ) as analysis:
                        for info in analysis:
                            self.mutex.lock()
                            should_break = self.new_position or not self.running
                            self.mutex.unlock()
                            if should_break:
                                break
                            line = line_from_engine_info(info, board)
                            self.info_ready.emit({"seq": batch_seq, "line": line})
                except Exception as e:
                    logger.error(f"Live analysis error: {e}")
                    self.error.emit(str(e))
                    time.sleep(0.5)  # Wait before retrying
                finally:
                    self.mutex.lock()
                    self._searching = False
                    self.mutex.unlock()
                    self.thinking_stopped.emit()

        except Exception as e:
            logger.error(f"Failed to start live analysis engine: {e}")
            self.error.emit(str(e))
        finally:
            engine = self.engine
            self.engine = None
            if engine:
                try:
                    engine.quit()
                except Exception:
                    pass
            logger.info("LiveAnalysisWorker stopped")

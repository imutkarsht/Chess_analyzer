import chess
import chess.engine
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition
from src.utils.logger import logger
import time


class LiveAnalysisWorker(QThread):
    # Signals
    # info: dict with analysis info (depth, score, pv, etc.)
    info_ready = pyqtSignal(dict)
    # Emitted when the engine starts / stops calculating a position
    thinking_started = pyqtSignal()
    thinking_stopped = pyqtSignal()

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
        self.is_chess960 = False

    # ------------------------------------------------------------------
    # Config accessors with safe fallbacks.  We isolate the fallback
    # logic so the run() loop stays readable and so the defaults
    # match the new conservative settings (see issue #5).
    # ------------------------------------------------------------------
    def _live_time(self) -> float:
        if self.config_manager is not None:
            try:
                return float(self.config_manager.get("live_analysis_time", 2.0))
            except (TypeError, ValueError):
                pass
        return 2.0

    def _live_multi_pv(self) -> int:
        if self.config_manager is not None:
            try:
                value = int(self.config_manager.get("multi_pv", 1))
                if value >= 1:
                    return value
            except (TypeError, ValueError):
                pass
        return 1
        
    def _live_depth(self) -> int:
        if self.config_manager is not None:
            try:
                return int(self.config_manager.get("analysis_depth", 18))
            except (TypeError, ValueError):
                pass
        return 18

    def _threads(self) -> int:
        if self.config_manager is not None:
            try:
                return int(self.config_manager.get("engine_threads", 1))
            except (TypeError, ValueError):
                pass
        return 1

    def _hash(self) -> int:
        if self.config_manager is not None:
            try:
                return int(self.config_manager.get("engine_hash", 32))
            except (TypeError, ValueError):
                pass
        return 32

    def configure_engine(self):
        """Reconfigures engine Thread and Hash options dynamically."""
        self.mutex.lock()
        engine = self.engine
        self.mutex.unlock()
        if engine:
            try:
                engine.configure({"Threads": self._threads(), "Hash": self._hash()})
                logger.info(f"Live engine reconfigured dynamically: Threads={self._threads()}, Hash={self._hash()}")
            except Exception as e:
                logger.error(f"Failed to reconfigure live engine: {e}")
        
    def set_chess960(self, enabled: bool):
        """Set Chess960 mode. Reconfigures the engine if running."""
        self.is_chess960 = enabled
        if self.engine:
            try:
                self.engine.configure({"UCI_Chess960": "true" if enabled else "false"})
            except Exception as e:
                pass

    def set_position(self, fen):
        """Updates the position to analyze."""
        self.mutex.lock()
        if fen != self.current_fen:
            self.current_fen = fen
            self.new_position = True
            self.condition.wakeAll()
        self.mutex.unlock()
        
    def start(self, priority=QThread.Priority.InheritPriority):
        self.running = True
        super().start(priority)

    def stop(self):
        """Stops the worker thread."""
        self.running = False
        self.mutex.lock()
        self.condition.wakeAll()
        self.mutex.unlock()
        self.wait()
        
    def run(self):
        self.running = True
        logger.info(f"LiveAnalysisWorker starting with engine: {self.engine_path}")
        try:
            # Start engine
            import sys, subprocess
            popen_args = {}
            if sys.platform == "win32":
                popen_args["creationflags"] = subprocess.CREATE_NO_WINDOW
            self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path, **popen_args)
            self.engine.configure({"Threads": self._threads(), "Hash": self._hash()})
            
            while self.running:
                self.mutex.lock()
                # Wait until there is a new position to analyze
                while self.running and not self.new_position:
                    self.condition.wait(self.mutex)
                
                if not self.running:
                    self.mutex.unlock()
                    break
                    
                fen = self.current_fen
                self.new_position = False
                self.mutex.unlock()
                
                # Start analysis
                if fen:
                    try:
                        board = chess.Board(fen, chess960=self.is_chess960)
                        self.thinking_started.emit()
                        # Finite analysis: calculate incrementally up to selected depth + 10 max
                        with self.engine.analysis(
                            board,
                            chess.engine.Limit(depth=self._live_depth() + 6),
                            multipv=self._live_multi_pv(),
                        ) as analysis:
                            for info in analysis:
                                self.mutex.lock()
                                should_break = self.new_position or not self.running
                                self.mutex.unlock()
                                if should_break:
                                    break
                                
                                # Process info
                                processed_info = self._process_info(info, board)
                                self.info_ready.emit(processed_info)
                        self.thinking_stopped.emit()
                    except Exception as e:
                        self.thinking_stopped.emit()
                        logger.error(f"Live analysis error: {e}")
                        time.sleep(0.5) # Wait before retrying
                
        except Exception as e:
            logger.error(f"Failed to start live analysis engine: {e}")
        finally:
            if self.engine:
                self.engine.quit()
            logger.info("LiveAnalysisWorker stopped")

    def _process_info(self, info, board):
        """Converts engine info to friendly format."""
        result = {}
        
        # Depth
        result["depth"] = info.get("depth", 0)
        result["nodes"] = info.get("nodes", 0)
        result["nps"] = info.get("nps", 0)
        
        # Score
        result["score_value"] = None
        score = info.get("score")
        if score:
            if score.is_mate():
                mate = score.relative.mate()
                if mate is not None:
                    result["mate"] = mate
                    result["score_value"] = f"M{mate}"
            else:
                cp = score.relative.score(mate_score=10000)
                if cp is not None:
                    result["cp"] = cp
                    result["score_value"] = f"{cp/100:.2f}"
        
        # PV
        pv_moves = info.get("pv", [])
        result["pv_uci"] = [m.uci() for m in pv_moves]
        
        # SAN
        try:
            result["pv_san"] = board.variation_san(pv_moves)
        except:
            result["pv_san"] = " ".join([m.uci() for m in pv_moves])
            
        # MultiPV ID
        result["multipv"] = info.get("multipv", 1)
        
        return result

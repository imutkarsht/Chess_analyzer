import chess
import chess.engine
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition
from ..utils.logger import logger
import time


class LiveAnalysisWorker(QThread):
    # Signals
    # info: dict with analysis info (depth, score, pv, etc.)
    info_ready = pyqtSignal(dict)

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
        
    def set_position(self, fen):
        """Updates the position to analyze."""
        self.mutex.lock()
        self.current_fen = fen
        self.new_position = True
        self.condition.wakeAll()
        self.mutex.unlock()
        
    def stop(self):
        """Stops the worker thread."""
        self.running = False
        self.mutex.lock()
        self.condition.wakeAll()
        self.mutex.unlock()
        self.wait()
        
    def run(self):
        logger.info(f"LiveAnalysisWorker starting with engine: {self.engine_path}")
        try:
            # Start engine
            self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            self.engine.configure({"Threads": 1, "Hash": 32}) # Lightweight config
            
            while self.running:
                self.mutex.lock()
                if not self.current_fen:
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
                        board = chess.Board(fen)
                        # Finite analysis: bound the search by wall-clock
                        # time so the worker releases the CPU after the
                        # configured budget even if the user goes idle.
                        # The previous `Limit(depth=None)` ran forever,
                        # pinning every core and frying fanless laptops.
                        # See https://github.com/imutkarsht/Chess_analyzer/issues/5
                        with self.engine.analysis(
                            board,
                            chess.engine.Limit(time=self._live_time()),
                            multipv=self._live_multi_pv(),
                        ) as analysis:
                            for info in analysis:
                                if self.new_position or not self.running:
                                    break
                                
                                # Process info
                                processed_info = self._process_info(info, board)
                                self.info_ready.emit(processed_info)
                                
                                # Small sleep to avoid flooding GUI? Not needed for analysis iterator usually
                                # But let's be safe
                                # time.sleep(0.01) 
                                
                    except Exception as e:
                        logger.error(f"Live analysis error: {e}")
                        time.sleep(1) # Wait before retrying
                
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
        score = info.get("score")
        if score:
            if score.is_mate():
                result["mate"] = score.relative.mate()
                result["score_value"] = f"M{result['mate']}"
            else:
                cp = score.relative.score(mate_score=10000)
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

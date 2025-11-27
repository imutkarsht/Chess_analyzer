import chess.engine
import chess
from typing import Optional, Dict, Any, Tuple
import logging

class EngineManager:
    def __init__(self, engine_path: str):
        self.engine_path = engine_path
        self.engine: Optional[chess.engine.SimpleEngine] = None
        self.options: Dict[str, Any] = {
            "Threads": 1,
            "Hash": 16
        }

    def start_engine(self):
        if not self.engine:
            try:
                # Assuming UCI engine
                self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
                self.configure_engine(self.options)
            except Exception as e:
                logging.error(f"Failed to start engine at {self.engine_path}: {e}")
                raise

    def stop_engine(self):
        if self.engine:
            self.engine.quit()
            self.engine = None

    def configure_engine(self, options: Dict[str, Any]):
        self.options.update(options)
        if self.engine:
            for name, value in options.items():
                try:
                    self.engine.configure({name: value})
                except Exception as e:
                    logging.warning(f"Could not configure {name}: {e}")

    def analyze_position(self, board: chess.Board, time_limit: float = 0.1, depth: Optional[int] = None, multi_pv: int = 1) -> chess.engine.InfoDict:
        if not self.engine:
            raise RuntimeError("Engine not started")
        
        limit = chess.engine.Limit(time=time_limit, depth=depth)
        info = self.engine.analyse(board, limit, multipv=multi_pv)
        return info

    def get_best_move(self, board: chess.Board, time_limit: float = 0.1) -> Optional[chess.Move]:
        if not self.engine:
            raise RuntimeError("Engine not started")
        
        limit = chess.engine.Limit(time=time_limit)
        result = self.engine.play(board, limit)
        return result.move

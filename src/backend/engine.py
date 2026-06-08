import chess.engine
import chess
import os
from typing import Optional, Dict, Any, Tuple
from ..utils.logger import logger

# Sensible defaults; overridden from the ConfigManager at runtime.
_DEFAULT_THREADS = min(os.cpu_count() or 1, 8)
_DEFAULT_HASH_MB = 256


def _options_from_config(config_manager=None) -> Dict[str, Any]:
    """Build the Stockfish UCI options dict from the user config.

    Falls back to conservative defaults if the ConfigManager is missing
    the keys (e.g. on a fresh install) or if it is not provided.
    """
    if config_manager is None:
        return {"Threads": _DEFAULT_THREADS, "Hash": _DEFAULT_HASH_MB}
    threads = config_manager.get("engine_threads", _DEFAULT_THREADS)
    hash_mb = config_manager.get("engine_hash", _DEFAULT_HASH_MB)
    return {"Threads": int(threads), "Hash": int(hash_mb)}


class EngineManager:
    def __init__(self, engine_path: str, config_manager=None):
        self.engine_path = engine_path
        self.config_manager = config_manager
        self.engine: Optional[chess.engine.SimpleEngine] = None
        self.options: Dict[str, Any] = _options_from_config(config_manager)

    def start_engine(self):
        if not self.engine:
            try:
                # Assuming UCI engine
                self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
                self.configure_engine(self.options)
            except Exception as e:
                logger.error(f"Failed to start engine at {self.engine_path}: {e}")
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
                    logger.warning(f"Could not configure {name}: {e}")

    def apply_settings_from_config(self):
        """Reload Threads/Hash from the ConfigManager and apply them to
        the running engine, if any. Safe to call when no engine is
        started — the next start_engine() will pick up the new values."""
        new_opts = _options_from_config(self.config_manager)
        self.configure_engine(new_opts)

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

import chess.engine
import chess
import os
from typing import Optional, Dict, Any, Tuple
from ..utils.logger import logger

# Conservative defaults aimed at laptops (incl. fanless MacBook Air).
# Power users can raise these in Settings; the values here are deliberately
# small so that a stock install does not pin every core at 100% forever.
# See https://github.com/imutkarsht/Chess_analyzer/issues/5
DEFAULT_THREADS = min(os.cpu_count() or 1, 4)
DEFAULT_HASH_MB = 64


def engine_options(threads: int, hash_mb: int) -> Dict[str, Any]:
    """Build a Stockfish UCI options dict from raw values.

    Centralised so callers can construct one without having to know
    Stockfish's option spelling.
    """
    return {"Threads": int(threads), "Hash": int(hash_mb)}


def options_from_config(config_manager=None) -> Dict[str, Any]:
    """Build the Stockfish UCI options dict from the user config.

    Falls back to conservative defaults if the ConfigManager is missing
    the keys (e.g. on a fresh install) or if it is not provided.
    """
    if config_manager is None:
        return engine_options(DEFAULT_THREADS, DEFAULT_HASH_MB)
    threads = config_manager.get("engine_threads", DEFAULT_THREADS)
    hash_mb = config_manager.get("engine_hash", DEFAULT_HASH_MB)
    return engine_options(threads, hash_mb)


class EngineManager:
    def __init__(self, engine_path: str, config_manager=None):
        self.engine_path = engine_path
        # config_manager is kept purely as a convenience for the
        # apply_settings_from_config() bridge. EngineManager itself does
        # NOT read from it — pass values explicitly via apply_settings()
        # so the manager stays trivially testable and CLI-friendly.
        self.config_manager = config_manager
        self.engine: Optional[chess.engine.SimpleEngine] = None
        self.options: Dict[str, Any] = options_from_config(config_manager)

    def start_engine(self):
        if not self.engine:
            try:
                # Assuming UCI engine
                import sys, subprocess
                popen_args = {}
                if sys.platform == "win32":
                    popen_args["creationflags"] = subprocess.CREATE_NO_WINDOW
                self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path, **popen_args)
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
        logger.info(f"EngineManager: Configuring engine with options: {options}")
        if self.engine:
            for name, value in options.items():
                try:
                    self.engine.configure({name: value})
                    logger.debug(f"EngineManager: Successfully set {name} to {value}")
                except Exception as e:
                    logger.warning(f"Could not configure {name}: {e}")

    def apply_settings(self, threads: int, hash_mb: int) -> None:
        """Apply the given Threads/Hash to the running engine (if any).

        Safe to call when no engine is started — the next start_engine()
        will pick up the new values from self.options.
        """
        self.configure_engine(engine_options(threads, hash_mb))

    def apply_settings_from_config(self) -> None:
        """Reload Threads/Hash from the ConfigManager and apply them to
        the running engine, if any. Convenience wrapper for callers that
        still want the ConfigManager-driven path."""
        if self.config_manager is None:
            return
        self.apply_settings(
            threads=self.config_manager.get("engine_threads", DEFAULT_THREADS),
            hash_mb=self.config_manager.get("engine_hash", DEFAULT_HASH_MB),
        )

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

import chess.engine
import chess
import os
import sys
import shutil
from typing import Optional, Dict, Any, Tuple, List
from src.utils.logger import logger
from src.utils.path_utils import get_stockfish_common_paths, get_engine_data_dir
from src.constants import DEFAULT_ENGINE_THREADS, DEFAULT_ENGINE_HASH_MB


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
        return engine_options(DEFAULT_ENGINE_THREADS, DEFAULT_ENGINE_HASH_MB)
    threads = config_manager.get("engine_threads", DEFAULT_ENGINE_THREADS)
    hash_mb = config_manager.get("engine_hash", DEFAULT_ENGINE_HASH_MB)
    return engine_options(threads, hash_mb)


def _validate_engine_path(path: str) -> bool:
    if not path or not os.path.isfile(path):
        return False
    if sys.platform != "win32" and not os.access(path, os.X_OK):
        return False
    return True


_resolve_cache = None


def invalidate_engine_cache() -> None:
    """Reset the cached engine path so the next resolve_engine_path() call re-probes."""
    global _resolve_cache
    _resolve_cache = None


def _save_fallback_to_config(config_manager, resolved_path: str) -> None:
    """If the config still holds a stale path, overwrite it with the
    working fallback so the Settings UI stays in sync."""
    if config_manager is None:
        return
    current = config_manager.get("engine_path", "")
    if current and current != resolved_path:
        logger.info(
            "resolve_engine_path: updating config from '%s' to fallback '%s'",
            current, resolved_path,
        )
        config_manager.config["engine_path"] = resolved_path
        config_manager.save_config()


def resolve_engine_path(config_manager=None) -> Optional[str]:
    """Auto-detect a Stockfish binary using the priority table.
    Result is cached for the lifetime of the process (call
    invalidate_engine_cache() if the config changes).

    | Priority | Check |
    |----------|-------|
    | 1        | ``config["engine_path"]`` – explicit user setting |
    | 2        | ``shutil.which("stockfish")`` – ``$PATH`` (Homebrew, system) |
    | 3        | Platform-specific common paths |
    | 4        | Already-downloaded in engine data dir |
    | 5        | ``None`` – caller should fall back to download |

    When a fallback path is used (priorities 2-4), the config is updated
    so the Settings UI reflects the working path on next load.
    Returns the path string or ``None`` if nothing was found.
    """
    global _resolve_cache
    if _resolve_cache is not None:
        return _resolve_cache

    # Priority 1 – explicit user setting
    if config_manager is not None:
        cfg_path = config_manager.get("engine_path", "")
        if cfg_path:
            resolved = shutil.which(cfg_path) or cfg_path
            if _validate_engine_path(resolved):
                logger.info("resolve_engine_path: using config path %s", resolved)
                _resolve_cache = resolved
                return resolved

    # Priority 2 – PATH lookup
    which_path = shutil.which("stockfish")
    if which_path and _validate_engine_path(which_path):
        logger.info("resolve_engine_path: found via PATH at %s", which_path)
        _save_fallback_to_config(config_manager, which_path)
        _resolve_cache = which_path
        return which_path

    # Priority 3 – platform-specific common paths
    for candidate in get_stockfish_common_paths():
        if _validate_engine_path(candidate):
            logger.info("resolve_engine_path: found at common path %s", candidate)
            _save_fallback_to_config(config_manager, candidate)
            _resolve_cache = candidate
            return candidate

    # Priority 4 – previously downloaded
    downloaded = os.path.join(get_engine_data_dir(), "stockfish")
    if _validate_engine_path(downloaded):
        logger.info("resolve_engine_path: found previously downloaded at %s", downloaded)
        _save_fallback_to_config(config_manager, downloaded)
        _resolve_cache = downloaded
        return downloaded

    logger.info("resolve_engine_path: no Stockfish found, returning None")
    _resolve_cache = None
    return None


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

    def set_chess960_mode(self, enabled: bool) -> None:
        """Enable or disable Chess960 mode on the running engine (UCI_Chess960).

        When enabled, Stockfish expects Chess960-format castling UCI moves
        (king moves to rook square) instead of standard O-O/O-O-O notation.
        This only configures the running engine and does NOT persist to
        self.options, so the next start_engine() will not carry this setting.
        """
        if self.engine:
            try:
                self.engine.configure({"UCI_Chess960": "true" if enabled else "false"})
                logger.debug(f"EngineManager: Successfully set UCI_Chess960 to {enabled}")
            except Exception as e:
                # Stockfish 16+ manages UCI_Chess960 automatically.
                # Throwing here is harmless — the engine auto-detects Chess960
                # from the UCI position command.
                logger.debug(f"EngineManager: Cannot set UCI_Chess960 (auto-managed): {e}")

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
            threads=self.config_manager.get("engine_threads", DEFAULT_ENGINE_THREADS),
            hash_mb=self.config_manager.get("engine_hash", DEFAULT_ENGINE_HASH_MB),
        )

    def recheck_engine_path(self, config_manager=None) -> bool:
        """Re-run auto-detection and restart the engine if the path changed.

        This is useful after the user downloads Stockfish through the setup
        wizard or changes settings – call it to pick up the new binary
        without requiring an app restart.

        Returns ``True`` if the engine is running (or was successfully
        restarted) after the check.
        """
        invalidate_engine_cache()
        new_path = resolve_engine_path(config_manager)
        if new_path is None:
            return False
        if new_path != self.engine_path:
            self.stop_engine()
            self.engine_path = new_path
        if self.engine is None:
            try:
                self.start_engine()
            except Exception:
                logger.exception("recheck_engine_path: failed to start engine at %s", new_path)
                return False
        return self.engine is not None

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

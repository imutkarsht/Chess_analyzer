"""
Regression tests for issue #5 — engine overheating on fanless laptops.

The previous defaults were:
- engine.py:    DEFAULT_THREADS = min(cpu_count, 8), DEFAULT_HASH_MB = 256
- analyzer.py:  "multi_pv": 3  (hard-coded)
- live_analysis.py: chess.engine.Limit(depth=None), multipv=3 (infinite, 3 PVs)

That combination pinned every CPU core at 100% forever and was reported
as a real-world problem on a MacBook Air M4.  These tests pin the new
conservative behaviour so a future refactor cannot silently regress to
the old, fan-melting values.
"""
import os
import sys
import pytest


# =====================================================================
# Module-level defaults (src/constants.py)
# =====================================================================
def test_default_threads_capped_for_laptops():
    """Engine must default to 1 thread."""
    from src.constants import DEFAULT_ENGINE_THREADS
    assert isinstance(DEFAULT_ENGINE_THREADS, int)
    assert DEFAULT_ENGINE_THREADS >= 1
    assert DEFAULT_ENGINE_THREADS == 1, (
        f"DEFAULT_ENGINE_THREADS={DEFAULT_ENGINE_THREADS}; expected 1."
    )


def test_default_hash_is_conservative():
    """Engine must default to 128 MB hash."""
    from src.constants import DEFAULT_ENGINE_HASH_MB
    assert isinstance(DEFAULT_ENGINE_HASH_MB, int)
    assert DEFAULT_ENGINE_HASH_MB == 128, (
        f"DEFAULT_ENGINE_HASH_MB={DEFAULT_ENGINE_HASH_MB}; expected 128."
    )


def test_engine_options_passthrough():
    """engine_options() simply forwards the int values."""
    from src.backend.analysis.engine import engine_options
    assert engine_options(2, 128) == {"Threads": 2, "Hash": 128}


# =====================================================================
# Multi-PV defaults flow through ConfigManager
# =====================================================================
def test_config_defaults_include_multi_pv_and_live_time(tmp_path, monkeypatch):
    """A fresh install must seed multi_pv=2 and live_analysis_time=0.5.

    These are the user-facing toggles that fix the overheating bug;
    they must be present in DEFAULT_CONFIG so a brand-new config.json
    is created with safe values.
    """
    monkeypatch.setattr(
        "src.utils.path_utils.get_user_data_dir", lambda: str(tmp_path)
    )
    monkeypatch.setattr(
        "src.utils.config.get_user_data_dir", lambda: str(tmp_path)
    )
    from src.utils.config import ConfigManager
    ConfigManager._shared_config = None
    ConfigManager._shared_config_path = None
    cm = ConfigManager()
    assert cm.get("multi_pv", None) == 2
    assert cm.get("live_analysis_time", None) == 0.5


def test_config_loaded_multi_pv_is_consumed_by_analyzer(monkeypatch, tmp_path):
    """Analyzer's effective multi_pv must follow the config, not a hard 3."""
    monkeypatch.setattr(
        "src.utils.path_utils.get_user_data_dir", lambda: str(tmp_path)
    )
    monkeypatch.setattr(
        "src.utils.config.get_user_data_dir", lambda: str(tmp_path)
    )
    class FakeCM:
        def get(self, key, default=None):
            data = {"analysis_depth": 18, "multi_pv": 2, "live_analysis_time": 1.5}
            return data.get(key, default)
    from src.utils import config as cfg_mod
    from src.backend.analysis import analyzer as analyzer_mod
    monkeypatch.setattr(cfg_mod, "ConfigManager", FakeCM)
    monkeypatch.setattr(analyzer_mod, "ConfigManager", FakeCM)
    analyzer = analyzer_mod.Analyzer(engine_manager=None)
    try:
        assert analyzer.config["multi_pv"] == 2
    finally:
        cache = getattr(analyzer, "cache", None)
        if cache is not None and hasattr(cache, "close"):
            try:
                cache.close()
            except Exception:
                pass


# =====================================================================
# LiveAnalysisWorker — finite CPU budget per position
# =====================================================================
def test_live_worker_defaults_when_no_config(mocker):
    """Without a config_manager the worker must use 0.5s / 2 PV."""
    mocker.patch("chess.engine.SimpleEngine.popen_uci")
    from src.gui.analysis.live_analysis import LiveAnalysisWorker
    worker = LiveAnalysisWorker("/fake/stockfish")
    assert worker._live_time() == 0.5
    assert worker._live_multi_pv() == 2
    assert worker._live_depth() == 18
    assert worker._threads() == 1
    assert worker._hash() == 128
    assert worker.config_manager is None


def test_live_worker_reads_config(mocker):
    """When a config_manager is provided, the worker honours it."""
    mocker.patch("chess.engine.SimpleEngine.popen_uci")
    from src.gui.analysis.live_analysis import LiveAnalysisWorker
    cm = mocker.Mock()
    cm.get.side_effect = lambda key, default=None: {
        "live_analysis_time": 5.0,
        "multi_pv": 3,
    }.get(key, default)
    worker = LiveAnalysisWorker("/fake/stockfish", config_manager=cm)
    assert worker._live_time() == 5.0
    assert worker._live_multi_pv() == 3


def test_live_worker_falls_back_safely_on_garbage_config(mocker):
    """Bad config values (wrong type, non-positive) must not crash."""
    mocker.patch("chess.engine.SimpleEngine.popen_uci")
    from src.gui.analysis.live_analysis import LiveAnalysisWorker
    cm = mocker.Mock()
    cm.get.side_effect = lambda key, default=None: {
        "live_analysis_time": "not-a-number",
        "multi_pv": 0,  # invalid (< 1) — should be rejected
    }.get(key, default)
    worker = LiveAnalysisWorker("/fake/stockfish", config_manager=cm)
    assert worker._live_time() == 0.5
    assert worker._live_multi_pv() == 2

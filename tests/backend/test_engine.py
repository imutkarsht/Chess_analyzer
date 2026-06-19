import pytest
from src.backend.analysis.engine import (
    EngineManager,
    DEFAULT_THREADS,
    DEFAULT_HASH_MB,
    engine_options,
    options_from_config,
)
import chess.engine


def test_engine_init():
    """Test EngineManager initialization."""
    manager = EngineManager("dummy_path")
    assert manager.engine_path == "dummy_path"
    assert manager.engine is None


def test_configure_engine(mocker):
    """Test configuring engine options."""
    manager = EngineManager("dummy_path")
    manager.engine = mocker.Mock()

    manager.configure_engine({"Threads": 2})
    manager.engine.configure.assert_called_with({"Threads": 2})


def test_engine_options_builds_uci_dict():
    """engine_options() returns Stockfish's expected option spelling."""
    assert engine_options(4, 128) == {"Threads": 4, "Hash": 128}


def test_options_from_config_without_manager_uses_defaults():
    """Without a ConfigManager we get the module-level defaults."""
    opts = options_from_config(None)
    assert opts["Threads"] == DEFAULT_THREADS
    assert opts["Hash"] == DEFAULT_HASH_MB


def test_apply_settings_runs_on_running_engine(mocker):
    """apply_settings() configures the running engine with the new values."""
    manager = EngineManager("dummy_path")
    manager.engine = mocker.Mock()

    manager.apply_settings(threads=4, hash_mb=512)

    # configure_engine() sends one UCI call per option, so we expect two.
    manager.engine.configure.assert_has_calls(
        [mocker.call({"Threads": 4}), mocker.call({"Hash": 512})],
        any_order=True,
    )


def test_apply_settings_is_safe_when_engine_not_started():
    """No engine running -> no exception, next start picks up the new values."""
    manager = EngineManager("dummy_path")
    manager.apply_settings(threads=2, hash_mb=64)
    assert manager.options["Threads"] == 2
    assert manager.options["Hash"] == 64


def test_apply_settings_from_config_without_manager_is_noop():
    """apply_settings_from_config() without a manager must not raise."""
    manager = EngineManager("dummy_path")
    # No exception means the noop worked.
    manager.apply_settings_from_config()

import os
import sys

import pytest

from src.backend.analysis.engine import (
    EngineManager,
    _validate_engine_path,
    engine_options,
    options_from_config,
    resolve_engine_path,
)
from src.constants import DEFAULT_ENGINE_HASH_MB, DEFAULT_ENGINE_THREADS


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
    """Without a ConfigManager we get the conservative laptop-safe defaults."""
    opts = options_from_config(None)
    assert opts["Threads"] == DEFAULT_ENGINE_THREADS == 1
    assert opts["Hash"] == DEFAULT_ENGINE_HASH_MB == 128


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


# ── resolve_engine_path ─────────────────────────────────────────────────

class TestValidateEnginePath:
    def test_none_or_empty_returns_false(self):
        assert _validate_engine_path("") is False

    def test_nonexistent_file_returns_false(self):
        assert _validate_engine_path("/nonexistent/stockfish") is False

    def test_valid_file_returns_true(self, tmp_path):
        p = tmp_path / "stockfish"
        p.write_text("fake binary")
        p.chmod(0o755)
        assert _validate_engine_path(str(p)) is True

    @pytest.mark.skipif(sys.platform == "win32", reason="chmod exec bits have no effect on Windows")
    def test_non_executable_on_unix_returns_false(self, mocker, tmp_path):
        mocker.patch.object(sys, "platform", "linux")
        p = tmp_path / "stockfish"
        p.write_text("fake binary")
        p.chmod(0o644)
        assert _validate_engine_path(str(p)) is False

    def test_windows_skips_exec_check(self, mocker, tmp_path):
        mocker.patch.object(sys, "platform", "win32")
        p = tmp_path / "stockfish.exe"
        p.write_text("fake binary")
        # Not setting executable bits — Windows doesn't care
        assert _validate_engine_path(str(p)) is True


class TestResolveEnginePath:
    """Tests the priority-based resolution (no real filesystem access)."""

    def test_priority1_config_path(self, mocker):
        """Config path that exists is returned first."""
        mock_cfg = mocker.Mock()
        mock_cfg.get.return_value = "/usr/local/bin/stockfish"

        mocker.patch("shutil.which", return_value=None)
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("os.access", return_value=True)

        result = resolve_engine_path(mock_cfg)
        assert result == "/usr/local/bin/stockfish"
        mock_cfg.get.assert_called_with("engine_path", "")

    def test_priority1_config_path_which_resolves(self, mocker):
        """If config path is a bare name, shutil.which resolves it."""
        mock_cfg = mocker.Mock()
        mock_cfg.get.return_value = "stockfish"

        mocker.patch("shutil.which", return_value="/opt/homebrew/bin/stockfish")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("os.access", return_value=True)

        result = resolve_engine_path(mock_cfg)
        assert result == "/opt/homebrew/bin/stockfish"

    def test_priority1_skips_when_config_empty(self, mocker):
        """Empty config path falls through to PATH lookup."""
        mock_cfg = mocker.Mock()
        mock_cfg.get.return_value = ""

        mocker.patch("shutil.which", return_value=None)
        mocker.patch("os.path.isfile", return_value=False)
        mocker.patch("src.backend.analysis.engine.get_stockfish_common_paths",
                     return_value=[])
        mocker.patch("src.backend.analysis.engine.get_engine_data_dir",
                     return_value="/tmp/engine_data")

        result = resolve_engine_path(mock_cfg)
        # Falls all the way through to None since nothing is found
        assert result is None

    def test_priority1_skips_when_config_path_invalid(self, mocker):
        """Config path that doesn't exist falls through."""
        mock_cfg = mocker.Mock()
        mock_cfg.get.return_value = "/usr/local/bin/stockfish"

        mocker.patch("shutil.which", return_value=None)
        mocker.patch("os.path.isfile", return_value=False)

        result = resolve_engine_path(mock_cfg)
        assert result is None

    def test_priority2_path_lookup(self, mocker):
        """shutil.which result is returned before common paths."""
        mock_cfg = mocker.Mock()
        mock_cfg.get.return_value = ""

        mocker.patch("shutil.which", return_value="/usr/bin/stockfish")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("os.access", return_value=True)

        result = resolve_engine_path(mock_cfg)
        assert result == "/usr/bin/stockfish"

    def test_priority2_path_lookup_second_place(self, mocker):
        """shutil.which returning None -> skip to common paths."""
        mock_cfg = mocker.Mock()
        mock_cfg.get.return_value = ""

        mocker.patch("shutil.which", return_value=None)
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("os.access", return_value=True)
        mocker.patch("src.backend.analysis.engine.get_stockfish_common_paths",
                     return_value=["/opt/homebrew/bin/stockfish"])
        mocker.patch("src.backend.analysis.engine.get_engine_data_dir",
                     return_value="/tmp/data/engine")

        result = resolve_engine_path(mock_cfg)
        assert result == "/opt/homebrew/bin/stockfish"

    def test_priority3_common_paths_checked(self, mocker):
        """Common paths are checked after PATH."""
        mock_cfg = mocker.Mock()
        mock_cfg.get.return_value = ""

        def which_side_effect(cmd, **kw):
            return None

        mocker.patch("shutil.which", side_effect=which_side_effect)

        # Make first common path valid
        mocker.patch("src.backend.analysis.engine.get_stockfish_common_paths",
                     return_value=["/opt/homebrew/bin/stockfish",
                                   "/usr/local/bin/stockfish"])

        def isfile_side_effect(p):
            return p == "/opt/homebrew/bin/stockfish"

        mocker.patch("os.path.isfile", side_effect=isfile_side_effect)
        mocker.patch("os.access", return_value=True)

        result = resolve_engine_path(mock_cfg)
        assert result == "/opt/homebrew/bin/stockfish"

    def test_priority4_downloaded_dir(self, mocker):
        """Previously-downloaded binary in engine data dir is found."""
        mock_cfg = mocker.Mock()
        mock_cfg.get.return_value = ""

        engine_data_dir = "/tmp/engine_data"
        mocker.patch("shutil.which", return_value=None)
        mocker.patch("src.backend.analysis.engine.get_stockfish_common_paths",
                     return_value=[])
        mocker.patch("src.backend.analysis.engine.get_engine_data_dir",
                     return_value=engine_data_dir)
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("os.access", return_value=True)

        result = resolve_engine_path(mock_cfg)
        # engine.py always joins "stockfish" (no .exe) for the downloaded path
        assert result == os.path.join(engine_data_dir, "stockfish")

    def test_all_priorities_fail_returns_none(self, mocker):
        """When nothing is found, returns None."""
        mock_cfg = mocker.Mock()
        mock_cfg.get.return_value = ""

        mocker.patch("shutil.which", return_value=None)
        mocker.patch("src.backend.analysis.engine.get_stockfish_common_paths",
                     return_value=[])
        mocker.patch("src.backend.analysis.engine.get_engine_data_dir",
                     return_value="/tmp/engine_data")
        mocker.patch("os.path.isfile", return_value=False)

        result = resolve_engine_path(mock_cfg)
        assert result is None

    def test_no_config_manager_uses_fallback(self, mocker):
        """When config_manager is None, skips priority 1 and goes to PATH."""
        mocker.patch("shutil.which", return_value="/usr/bin/stockfish")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("os.access", return_value=True)

        result = resolve_engine_path(None)
        assert result == "/usr/bin/stockfish"

    def test_no_config_manager_falls_through(self, mocker):
        """When config_manager is None and no PATH match, goes to common paths."""
        mocker.patch("shutil.which", return_value=None)
        mocker.patch("src.backend.analysis.engine.get_stockfish_common_paths",
                     return_value=["/usr/local/bin/stockfish"])
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("os.access", return_value=True)

        result = resolve_engine_path(None)
        assert result == "/usr/local/bin/stockfish"


# ── recheck_engine_path ─────────────────────────────────────────────────

class TestRecheckEnginePath:
    def test_finds_engine_and_starts_it(self, mocker):
        """If resolve finds a path, engine is started."""
        mocker.patch("src.backend.analysis.engine.resolve_engine_path",
                     return_value="/usr/bin/stockfish")
        manager = EngineManager("old/path")
        mocker.patch.object(manager, "start_engine",
                            side_effect=lambda: setattr(manager, "engine", mocker.Mock()))

        result = manager.recheck_engine_path()
        assert result is True
        assert manager.engine_path == "/usr/bin/stockfish"

    def test_path_unchanged_and_engine_running(self, mocker):
        """Same path and engine already running -> returns True, no restart."""
        mocker.patch("src.backend.analysis.engine.resolve_engine_path",
                     return_value="/same/path")
        manager = EngineManager("/same/path")
        manager.engine = mocker.Mock()

        start_mock = mocker.patch.object(manager, "start_engine")
        stop_mock = mocker.patch.object(manager, "stop_engine")

        result = manager.recheck_engine_path()
        assert result is True
        stop_mock.assert_not_called()
        start_mock.assert_not_called()

    def test_path_changed_restarts_engine(self, mocker):
        """Different path -> stops old, starts new."""
        mocker.patch("src.backend.analysis.engine.resolve_engine_path",
                     return_value="/new/path")
        manager = EngineManager("/old/path")
        manager.engine = mocker.Mock()
        mocker.patch.object(manager, "start_engine",
                            side_effect=lambda: setattr(manager, "engine", mocker.Mock()))

        result = manager.recheck_engine_path()
        assert result is True
        assert manager.engine_path == "/new/path"

    def test_returns_false_when_not_found(self, mocker):
        """resolve returns None -> returns False."""
        mocker.patch("src.backend.analysis.engine.resolve_engine_path",
                     return_value=None)
        manager = EngineManager("/old/path")

        result = manager.recheck_engine_path()
        assert result is False

    def test_returns_false_when_start_fails(self, mocker):
        """start_engine raises -> returns False."""
        mocker.patch("src.backend.analysis.engine.resolve_engine_path",
                     return_value="/new/path")
        manager = EngineManager("/old/path")
        mocker.patch.object(manager, "start_engine",
                            side_effect=Exception("engine crash"))

        result = manager.recheck_engine_path()
        assert result is False


# ── engine lifecycle ────────────────────────────────────────────────────

class TestEngineLifecycle:
    def test_start_engine_launches_and_applies_options(self, mocker):
        fake_engine = mocker.Mock()
        popen = mocker.patch(
            "src.backend.analysis.engine.chess.engine.SimpleEngine.popen_uci",
            return_value=fake_engine,
        )
        manager = EngineManager("/fake/stockfish")
        manager.options = {"Threads": 1, "Hash": 128}

        manager.start_engine()

        popen.assert_called_once_with("/fake/stockfish")
        fake_engine.configure.assert_has_calls(
            [mocker.call({"Threads": 1}), mocker.call({"Hash": 128})],
            any_order=True,
        )
        assert manager.engine is fake_engine

    def test_start_engine_is_idempotent(self, mocker):
        popen = mocker.patch(
            "src.backend.analysis.engine.chess.engine.SimpleEngine.popen_uci"
        )
        manager = EngineManager("/fake/stockfish")
        manager.engine = mocker.Mock()

        manager.start_engine()

        popen.assert_not_called()

    def test_start_engine_propagates_failure(self, mocker):
        mocker.patch(
            "src.backend.analysis.engine.chess.engine.SimpleEngine.popen_uci",
            side_effect=OSError("missing binary"),
        )
        manager = EngineManager("/missing/stockfish")

        with pytest.raises(OSError, match="missing binary"):
            manager.start_engine()

        assert manager.engine is None

    def test_stop_engine_quits_and_clears_analysis(self, mocker):
        manager = EngineManager("/fake/stockfish")
        fake_engine = mocker.Mock()
        manager.engine = fake_engine
        analysis = mocker.Mock()
        manager._current_analysis = analysis

        manager.stop_engine()

        analysis.stop.assert_called_once()
        fake_engine.quit.assert_called_once()
        assert manager.engine is None
        assert manager._current_analysis is None

    def test_stop_engine_swallows_quit_failure(self, mocker):
        manager = EngineManager("/fake/stockfish")
        manager.engine = mocker.Mock()
        manager.engine.quit.side_effect = RuntimeError("already dead")

        manager.stop_engine()

        assert manager.engine is None

    def test_cancel_analysis_clears_even_if_stop_fails(self, mocker):
        manager = EngineManager("/fake/stockfish")
        manager._current_analysis = mocker.Mock()
        manager._current_analysis.stop.side_effect = RuntimeError("gone")

        manager.cancel_current_analysis()

        assert manager._current_analysis is None

    def test_configure_failure_does_not_block_other_options(self, mocker):
        manager = EngineManager("/fake/stockfish")
        manager.engine = mocker.Mock()
        manager.engine.configure.side_effect = [RuntimeError("bad"), None]

        manager.configure_engine({"Threads": 4, "Hash": 256})

        assert manager.engine.configure.call_count == 2
        assert manager.options["Threads"] == 4
        assert manager.options["Hash"] == 256

    def test_chess960_mode_toggles_uci_option(self, mocker):
        manager = EngineManager("/fake/stockfish")
        manager.engine = mocker.Mock()

        manager.set_chess960_mode(True)
        manager.set_chess960_mode(False)

        manager.engine.configure.assert_has_calls(
            [mocker.call({"UCI_Chess960": "true"}), mocker.call({"UCI_Chess960": "false"})]
        )

    def test_chess960_mode_is_noop_without_engine(self):
        manager = EngineManager("/fake/stockfish")

        manager.set_chess960_mode(True)

        assert manager.engine is None

    def test_chess960_failure_is_non_fatal(self, mocker):
        manager = EngineManager("/fake/stockfish")
        manager.engine = mocker.Mock()
        manager.engine.configure.side_effect = RuntimeError("auto-managed")

        manager.set_chess960_mode(True)

        assert manager.engine is not None

    def test_apply_settings_from_config_reloads_values(self, mocker):
        config = mocker.Mock()
        config.get.side_effect = [3, 256]
        manager = EngineManager("/fake/stockfish")
        manager.config_manager = config
        manager.engine = mocker.Mock()

        manager.apply_settings_from_config()

        assert manager.options["Threads"] == 3
        assert manager.options["Hash"] == 256

    def test_options_from_config_uses_configured_values(self, mocker):
        config = mocker.Mock()
        config.get.side_effect = [4, 512]

        assert options_from_config(config) == {"Threads": 4, "Hash": 512}


class TestAnalyzePosition:
    def _manager_with_stream(self, mocker, stream):
        manager = EngineManager("/fake/stockfish")
        manager.engine = mocker.Mock()
        context = mocker.MagicMock()
        context.__enter__.return_value = stream
        manager.engine.analysis.return_value = context
        return manager

    def test_requires_started_engine(self, mocker):
        manager = EngineManager("/fake/stockfish")

        with pytest.raises(RuntimeError, match="Engine not started"):
            manager.analyze_position(mocker.Mock())

    def test_returns_single_pv_info(self, mocker):
        stream = mocker.Mock()
        stream.info = {"depth": 20, "pv": []}
        stream.multipv = [{"depth": 20}]
        manager = self._manager_with_stream(mocker, stream)
        board = mocker.Mock()

        result = manager.analyze_position(board, time_limit=0.5, depth=18)

        assert result == {"depth": 20, "pv": []}
        stream.wait.assert_called_once()
        manager.engine.analysis.assert_called_once()

    def test_returns_multipv_list(self, mocker):
        stream = mocker.Mock()
        stream.multipv = [{"depth": 20}, {"depth": 19}]
        manager = self._manager_with_stream(mocker, stream)

        result = manager.analyze_position(mocker.Mock(), multi_pv=2)

        assert result == [{"depth": 20}, {"depth": 19}]

    def test_clears_active_analysis_when_wait_fails(self, mocker):
        stream = mocker.Mock()
        stream.wait.side_effect = RuntimeError("cancelled")
        manager = self._manager_with_stream(mocker, stream)

        with pytest.raises(RuntimeError, match="cancelled"):
            manager.analyze_position(mocker.Mock())

        assert manager._current_analysis is None


class TestGetBestMove:
    def test_requires_started_engine(self, mocker):
        manager = EngineManager("/fake/stockfish")

        with pytest.raises(RuntimeError, match="Engine not started"):
            manager.get_best_move(mocker.Mock())

    def test_returns_engine_move(self, mocker):
        import chess

        manager = EngineManager("/fake/stockfish")
        manager.engine = mocker.Mock()
        best = chess.Move.from_uci("e2e4")
        manager.engine.play.return_value = mocker.Mock(move=best)

        assert manager.get_best_move(chess.Board()) == best


class TestResolveFallbackConfig:
    def test_stale_config_is_updated_to_working_path(self, mocker):
        config = mocker.Mock()
        config.get.side_effect = ["", "/stale/stockfish"]
        config.config = {"engine_path": "/stale/stockfish"}
        mocker.patch("shutil.which", return_value="/usr/bin/stockfish")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("os.access", return_value=True)

        assert resolve_engine_path(config) == "/usr/bin/stockfish"

        config.save_config.assert_called_once()
        assert config.config["engine_path"] == "/usr/bin/stockfish"

    def test_resolution_is_cached_between_calls(self, mocker):
        which = mocker.patch("shutil.which", return_value="/usr/bin/stockfish")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("os.access", return_value=True)

        assert resolve_engine_path(None) == "/usr/bin/stockfish"
        assert resolve_engine_path(None) == "/usr/bin/stockfish"

        which.assert_called_once()

    def test_deep_probe_rejects_binary_that_fails_handshake(self, mocker):
        config = mocker.Mock()
        config.get.return_value = "/broken/stockfish"
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("os.access", return_value=True)
        mocker.patch("shutil.which", return_value=None)
        mocker.patch(
            "src.backend.analysis.engine.get_stockfish_common_paths", return_value=[]
        )
        mocker.patch(
            "src.backend.analysis.engine.get_engine_data_dir", return_value="/tmp/engine"
        )
        probe = mocker.patch(
            "src.backend.analysis.engine.probe_engine_binary", return_value=False
        )

        assert resolve_engine_path(config, deep_probe=True) is None
        assert probe.call_count >= 2

    def test_deep_probe_accepts_working_binary(self, mocker):
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("os.access", return_value=True)
        mocker.patch("shutil.which", return_value="/usr/bin/stockfish")
        mocker.patch(
            "src.backend.analysis.engine.probe_engine_binary", return_value=True
        )

        assert resolve_engine_path(None, deep_probe=True) == "/usr/bin/stockfish"

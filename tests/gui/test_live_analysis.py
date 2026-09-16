"""Tests for the LiveAnalysisWorker thread control loop and configuration handling."""
from unittest.mock import MagicMock, patch
from src.gui.analysis.live_analysis import LiveAnalysisWorker


@patch("chess.engine.SimpleEngine.popen_uci")
def test_live_worker_running_flag(mock_popen, mocker):
    """Verify that starting, stopping, and restarting resets the running flag properly."""
    mock_engine = MagicMock()
    mock_popen.return_value = mock_engine

    worker = LiveAnalysisWorker("dummy_path")
    assert worker.running is True

    # Mock run method so it doesn't execute popen loop
    mocker.patch.object(worker, 'run', return_value=None)

    # Start worker
    worker.start()
    assert worker.running is True

    # Stop worker
    worker.stop()
    assert worker.running is False

    # Start worker again (restart)
    worker.start()
    assert worker.running is True

    # Stop clean up
    worker.stop()


def test_live_worker_defaults_when_no_config(mocker):
    """Without a config_manager the worker must use safe defaults (0.5s / 2 PV)."""
    mocker.patch("chess.engine.SimpleEngine.popen_uci")
    worker = LiveAnalysisWorker("/fake/stockfish")
    assert worker._live_time() == 0.5
    assert worker._live_multi_pv() == 2
    assert worker._live_depth() == 18
    assert worker._threads() == 1
    assert worker._hash() == 128
    assert worker.config_manager is None


def test_live_worker_reads_config(mocker):
    """When a config_manager is provided, the worker honours its values."""
    mocker.patch("chess.engine.SimpleEngine.popen_uci")
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
    cm = mocker.Mock()
    cm.get.side_effect = lambda key, default=None: {
        "live_analysis_time": "not-a-number",
        "multi_pv": 0,  # invalid (< 1) — should be rejected
    }.get(key, default)
    worker = LiveAnalysisWorker("/fake/stockfish", config_manager=cm)
    assert worker._live_time() == 0.5
    assert worker._live_multi_pv() == 2

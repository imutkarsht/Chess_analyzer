"""Tests for the LiveAnalysisWorker thread control loop."""
import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import QThread
from src.gui.analysis.live_analysis import LiveAnalysisWorker


@patch("chess.engine.SimpleEngine.popen_uci")
def test_live_worker_running_flag(mock_popen, mocker):
    """Verify that starting, stopping, and restarting resets the running flag properly."""
    mock_engine = MagicMock()
    mock_popen.return_value = mock_engine

    worker = LiveAnalysisWorker("dummy_path")
    assert worker.running is True  # initially True
    
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

import pytest
from src.backend.engine import EngineManager
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

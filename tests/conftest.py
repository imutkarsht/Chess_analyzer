import pytest
import sys
import os
from PyQt6.QtWidgets import QApplication

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app

@pytest.fixture
def mock_engine(mocker):
    """Mocks the chess engine."""
    mock = mocker.Mock()
    mock.analyse.return_value = {"score": mocker.Mock(white=lambda: mocker.Mock(score=lambda: 100))}
    return mock

@pytest.fixture
def mock_requests(mocker):
    """Mocks requests library."""
    return mocker.patch("requests.get")

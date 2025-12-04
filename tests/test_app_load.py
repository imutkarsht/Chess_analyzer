import pytest
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow
import sys

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app

def test_mainwindow_init(qapp):
    """Test that MainWindow can be initialized."""
    window = MainWindow()
    assert window is not None
    assert window.windowTitle() == "Chess Analyzer Pro"
    window.close()

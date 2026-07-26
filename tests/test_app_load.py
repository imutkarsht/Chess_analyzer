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

def test_mainwindow_switch_page(qapp, qtbot):
    """Test that page switching via switch_page is deferred and runs correctly."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    assert window.stack.currentIndex() == 0

    # Trigger switch to page 1
    window.switch_page(1)

    # Should still be 0 before processing events due to singleShot deferral
    assert window.stack.currentIndex() == 0

    # Wait for singleShot + fade transition to complete
    qtbot.waitUntil(lambda: window.stack.currentIndex() == 1, timeout=1000)

    assert window.stack.currentIndex() == 1
    window.close()

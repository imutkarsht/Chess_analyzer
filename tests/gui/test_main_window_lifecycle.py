"""Tests for MainWindow lifecycle and page switching."""
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def test_mainwindow_init(qapp):
    """Test that MainWindow initializes with proper defaults."""
    window = MainWindow()
    assert window is not None
    assert window.windowTitle() == "Chess Analyzer Pro"
    window.close()


def test_mainwindow_switch_page(qapp, qtbot):
    """Test that page switching via switch_page transitions correctly."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    assert window.stack.currentIndex() == 0

    # Trigger switch to page 1
    window.switch_page(1)

    # Deferral: wait for singleShot + transition to complete
    qtbot.waitUntil(lambda: window.stack.currentIndex() == 1, timeout=1000)
    assert window.stack.currentIndex() == 1
    window.close()


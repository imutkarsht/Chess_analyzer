"""Tests for MainWindow lifecycle and page switching."""

from src.gui.main_window import MainWindow


def test_mainwindow_lifecycle_and_page_switch(qapp, qtbot):
    """Test that MainWindow initializes with proper defaults and switches pages correctly."""
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.windowTitle() == "Chess Analyzer Pro"
    window.show()
    assert window.stack.currentIndex() == 0

    # Trigger switch to page 1
    window.switch_page(1)

    # Deferral: wait for singleShot + transition to complete
    qtbot.waitUntil(lambda: window.stack.currentIndex() == 1, timeout=1000)
    assert window.stack.currentIndex() == 1
    window.close()

"""Tests for TourManager and TourOverlay components."""
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtCore import QRect
from src.gui.components.tour_manager import TourManager, TourStep
from src.gui.components.tour_overlay import TourOverlay


def test_tour_manager_step_lifecycle():
    """TourManager properly tracks step progression and bounds."""
    w1 = QWidget()
    w2 = QWidget()
    w3 = QWidget()

    steps = [
        TourStep(target=w1, text="Step 1", position="below", page_index=0),
        TourStep(target=w2, text="Step 2", position="above", page_index=0),
        TourStep(target=w3, text="Step 3", position="right", page_index=0),
    ]

    mgr = TourManager()
    assert mgr.active is False
    assert mgr.total_steps == 0

    mgr.start(steps)
    assert mgr.active is True
    assert mgr.total_steps == 3
    assert mgr.current_step == 0
    assert mgr.current.text == "Step 1"

    # Step next
    assert mgr.next() is True
    assert mgr.current_step == 1
    assert mgr.current.text == "Step 2"

    assert mgr.next() is True
    assert mgr.current_step == 2
    assert mgr.current.text == "Step 3"

    # Beyond last step ends tour
    assert mgr.next() is False
    assert mgr.active is False

    # Previous step
    mgr.start(steps)
    mgr.next()
    assert mgr.prev() is True
    assert mgr.current_step == 0
    assert mgr.prev() is False  # Cannot go below 0

    # Stop resets
    mgr.stop()
    assert mgr.active is False


def test_tour_manager_seen_state():
    """TourManager marks and checks seen pages via ConfigManager."""
    mock_config = MagicMock()
    mock_store = {}
    mock_config.get.side_effect = lambda key, default=None: mock_store.get(key, default or {})
    mock_config.set.side_effect = lambda key, val: mock_store.update({key: val})

    mgr = TourManager(config_manager=mock_config)
    assert mgr.has_seen_tour(0) is False

    mgr.mark_seen(0)
    assert mgr.has_seen_tour(0) is True
    assert mgr.has_seen_tour(1) is False


def test_tour_overlay_positioning(qapp, qtbot):
    """TourOverlay positions bubble correctly and clamps within viewport."""
    parent = QWidget()
    parent.resize(1000, 800)
    qtbot.addWidget(parent)
    parent.show()

    target = QLabel("Target Widget", parent)
    target.setGeometry(400, 300, 200, 50)
    target.show()

    mgr = TourManager()
    step = TourStep(target=target, text="Tour bubble test", position="below", page_index=0)
    mgr.start([step])

    overlay = TourOverlay(parent, mgr)
    qtbot.addWidget(overlay)
    overlay.show_tour()

    # Verify bubble is placed near target
    assert overlay.bubble.isVisible()
    assert overlay.bubble.y() >= target.y() + target.height()

    # Smart boundary flip test: place target at bottom edge
    target.setGeometry(400, 750, 200, 40)
    overlay._highlight_rect = overlay._widget_rect_in_parent(target)
    overlay._position_bubble("below")
    # Because 'below' overflows 800px viewport, it should flip to 'above'
    assert overlay.bubble.y() < target.y()

    overlay.close_silently()


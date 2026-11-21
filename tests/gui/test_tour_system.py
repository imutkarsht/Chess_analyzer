"""TourManager state and persistence.

The overlay's pixel positioning is cosmetic; the state machine and the
seen-page migration are what suppress a broken or repeated onboarding tour.
"""
from PyQt6.QtWidgets import QWidget

from src.gui.components.layout.tour_manager import TourManager, TourStep


def test_tour_manager_step_lifecycle():
    """TourManager properly tracks step progression and bounds."""
    steps = [
        TourStep(target=QWidget(), text=f"Step {i}", position="below", page_index=0)
        for i in range(1, 4)
    ]

    mgr = TourManager()
    assert (mgr.active, mgr.total_steps) == (False, 0)

    mgr.start(steps)
    assert (mgr.active, mgr.total_steps, mgr.current_step) == (True, 3, 0)
    assert mgr.current.text == "Step 1"

    assert mgr.next() is True
    assert mgr.next() is True
    assert mgr.current.text == "Step 3"
    assert mgr.next() is False
    assert mgr.active is False

    mgr.start(steps)
    mgr.next()
    assert mgr.prev() is True and mgr.current_step == 0
    assert mgr.prev() is False

    mgr.stop()
    assert mgr.active is False


class _Store:
    def __init__(self):
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    @property
    def tour_seen_pages(self):
        return self.data.get("tour_seen_pages", {})


def test_tour_manager_seen_state():
    """TourManager marks and checks seen pages via ConfigManager."""
    store = _Store()

    mgr = TourManager(config_manager=store)
    assert mgr.has_seen_tour("landing") is False

    mgr.mark_seen("landing")
    assert mgr.has_seen_tour("landing") is True
    assert mgr.has_seen_tour("analysis") is False

    # Check semantic drill-down key
    assert mgr.has_seen_tour("metrics_drill_down") is False
    mgr.mark_seen("metrics_drill_down")
    assert mgr.has_seen_tour("metrics_drill_down") is True

    # Legacy numeric migration: legacy "1" maps to "explorer"
    store.data["tour_seen_pages"] = {"1": True}
    assert mgr.has_seen_tour("explorer") is True
    assert mgr.has_seen_tour(1) is True

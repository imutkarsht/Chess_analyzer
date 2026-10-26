"""Dashboard card ordering in Appearance."""

from src.gui.views.metrics.card_registry import DEFAULT_CARD_ORDER
from src.gui.views.settings.dashboard_layout_settings import DashboardLayoutSettings


class _FakeConfig:
    def __init__(self, order=None):
        self.config = {"metrics_card_order": order or []}

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value


def test_default_order_and_unknown_keys(qapp):
    widget = DashboardLayoutSettings(
        _FakeConfig(["ai_coach", "removed_card", "ai_coach"])
    )

    expected = ["ai_coach"] + [
        key for key in DEFAULT_CARD_ORDER if key != "ai_coach"
    ]
    assert widget.current_order() == expected
    assert widget.sortable_list.count() == len(DEFAULT_CARD_ORDER)
    widget.deleteLater()


def test_reorder_persists_and_reset_restores_default(qapp):
    config = _FakeConfig()
    widget = DashboardLayoutSettings(config)
    changes = []
    widget.order_changed.connect(lambda: changes.append(True))

    custom = ["ai_coach"] + [
        key for key in DEFAULT_CARD_ORDER if key != "ai_coach"
    ]
    widget.apply_order(custom)

    assert config.config["metrics_card_order"] == custom
    assert widget.current_order() == custom
    assert changes == [True]

    widget.reset_order()

    assert config.config["metrics_card_order"] == list(DEFAULT_CARD_ORDER)
    assert widget.current_order() == list(DEFAULT_CARD_ORDER)
    assert changes == [True, True]
    widget.deleteLater()

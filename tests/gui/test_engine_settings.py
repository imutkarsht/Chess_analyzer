"""Engine card uses binder-driven defaults and typed persistence."""

from src.gui.views.settings.engine_settings import EngineSettings


class _FakeConfig:
    """Minimal ConfigManager stand-in; the engine card only reads and assigns keys."""

    def __init__(self, overrides=None):
        self.config = {}
        self.config.update(overrides or {})

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value


def test_engine_defaults_fall_back_to_thermal_safe_values(qapp):
    """Threads/hash are not persisted by default, so the UI must show fallbacks."""
    widget = EngineSettings(_FakeConfig())

    assert widget.threads_input.text() == "1"
    assert widget.hash_input.text() == "128"
    assert widget.depth_combo.currentData() == 18
    assert widget.multi_pv_input.text() == "2"
    assert widget.live_time_input.text() == "0.5"
    widget.deleteLater()


def test_engine_commits_typed_values_on_change(qapp):
    config = _FakeConfig()
    widget = EngineSettings(config)

    widget.depth_combo.setCurrentIndex(widget.depth_combo.findData(22))
    widget.hash_input.setCurrentText("256")
    widget.multi_pv_input.setValue(3)
    widget.multi_pv_input.editingFinished.emit()

    assert config.config["analysis_depth"] == 22
    assert config.config["engine_hash"] == 256
    assert config.config["multi_pv"] == 3
    widget.deleteLater()


def test_engine_advanced_rows_hide_by_tier(qapp):
    widget = EngineSettings(_FakeConfig())

    widget.set_advanced_visible(False)

    assert widget.threads_input.parentWidget().isHidden() is True
    assert widget.hash_input.parentWidget().isHidden() is True
    assert widget.depth_combo.parentWidget().isHidden() is False

    widget.set_advanced_visible(True)
    assert widget.threads_input.parentWidget().isHidden() is False
    widget.deleteLater()

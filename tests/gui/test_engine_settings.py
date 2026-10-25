"""Analysis cards use binder-driven defaults and typed persistence."""

from src.gui.views.settings.engine_settings import EngineSettings
from src.gui.views.settings.full_analysis_settings import FullAnalysisSettings
from src.gui.views.settings.live_analysis_settings import LiveAnalysisSettings


class _FakeConfig:
    """Minimal ConfigManager stand-in; the cards only read and assign keys."""

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
    widget.deleteLater()


def test_full_analysis_defaults_match_schema(qapp):
    widget = FullAnalysisSettings(_FakeConfig())

    assert widget.depth_combo.currentData() == 18
    assert widget.time_cap_combo.currentData() == 1.0
    assert widget.multi_pv_input.text() == "2"
    assert widget.cache_checkbox.isChecked() is True
    widget.deleteLater()


def test_full_analysis_commits_typed_values_and_null_time_cap(qapp):
    config = _FakeConfig()
    widget = FullAnalysisSettings(config)

    widget.depth_combo.setCurrentIndex(widget.depth_combo.findData(22))
    widget.multi_pv_input.setValue(3)
    widget.multi_pv_input.editingFinished.emit()
    widget.cache_checkbox.setChecked(False)
    widget.time_cap_combo.setCurrentIndex(widget.time_cap_combo.findText("No cap"))

    assert config.config["analysis_depth"] == 22
    assert config.config["multi_pv"] == 3
    assert config.config["use_cache"] is False
    assert config.config["time_per_move"] is None
    widget.deleteLater()


def test_engine_and_analysis_rows_hide_by_tier(qapp):
    engine = EngineSettings(_FakeConfig())
    full = FullAnalysisSettings(_FakeConfig())
    live = LiveAnalysisSettings(_FakeConfig())

    engine.set_advanced_visible(False)
    full.set_advanced_visible(False)
    live.set_advanced_visible(False)

    assert engine.threads_input.parentWidget().isHidden() is True
    assert engine.hash_input.parentWidget().isHidden() is True
    assert full.multi_pv_input.parentWidget().isHidden() is True
    assert full.time_cap_combo.parentWidget().isHidden() is False
    assert live.live_time_input.parentWidget().isHidden() is True
    assert live.live_multi_pv_input.parentWidget().isHidden() is True
    assert live.engine_lines_checkbox.parentWidget().isHidden() is False

    engine.deleteLater()
    full.deleteLater()
    live.deleteLater()


def test_live_analysis_defaults_and_commit(qapp):
    config = _FakeConfig()
    widget = LiveAnalysisSettings(config)

    assert widget.live_time_input.text() == "0.5"
    assert widget.live_multi_pv_input.text() == "2"
    assert widget.engine_lines_checkbox.isChecked() is False

    widget.live_multi_pv_input.setValue(4)
    widget.live_multi_pv_input.editingFinished.emit()
    widget.engine_lines_checkbox.setChecked(True)

    assert config.config["live_multi_pv"] == 4
    assert config.config["engine_lines_enabled"] is True
    widget.deleteLater()

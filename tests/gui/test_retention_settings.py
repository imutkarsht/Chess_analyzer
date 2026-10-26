"""Data & Storage retention card: cache TTLs and evaluation capacity."""

from src.gui.views.settings.retention_settings import RetentionSettings


class _FakeConfig:
    """Minimal ConfigManager stand-in; the retention card only reads and assigns keys."""

    def __init__(self, overrides=None):
        self.config = {
            "explorer_cache_ttl_hours": 48,
            "analysis_cache_max_entries": 250_000,
            "explain_cache_ttl_days": 30,
        }
        self.config.update(overrides or {})

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value


def _select(combo, label: str) -> None:
    combo.setCurrentIndex(combo.findText(label))


def test_retention_rows_reflect_saved_config(qapp):
    config = _FakeConfig(
        {"explorer_cache_ttl_hours": 168, "explain_cache_ttl_days": 90}
    )
    widget = RetentionSettings(config)

    assert widget.explorer_ttl_combo.currentText() == "7 days"
    assert widget.explain_ttl_combo.currentText() == "90 days"
    assert widget.analysis_cap_input.value() == 250_000
    assert widget.analysis_cap_input.value_label.text() == "250,000"
    widget.deleteLater()


def test_never_expire_persists_null_ttl(qapp):
    """``None`` survives the combo round-trip; ``currentData()`` would lose it."""
    config = _FakeConfig()
    widget = RetentionSettings(config)

    _select(widget.explorer_ttl_combo, "Never expire")
    assert config.config["explorer_cache_ttl_hours"] is None

    _select(widget.explain_ttl_combo, "Never expire")
    assert config.config["explain_cache_ttl_days"] is None
    widget.deleteLater()

"""Coach explanation card is binder-driven."""

from src.gui.views.settings.coach_settings import CoachSettings


class _FakeConfig:
    """Minimal ConfigManager stand-in; the Coach card only reads and assigns keys."""

    def __init__(self, overrides=None):
        self.config = {
            "explain_llm_for_trivial_moves": False,
            "explain_cache_ttl_days": 30,
        }
        self.config.update(overrides or {})

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value


def _select_ttl(widget: CoachSettings, label: str) -> None:
    combo = widget.explain_ttl_combo
    combo.setCurrentIndex(combo.findText(label))


def test_coach_rows_reflect_saved_config(qapp):
    config = _FakeConfig({"explain_llm_for_trivial_moves": True})
    widget = CoachSettings(config)

    assert widget.explain_trivial_checkbox.isChecked() is True
    assert widget.explain_ttl_combo.currentText() == "30 days"
    widget.deleteLater()


def test_never_expire_persists_null_ttl(qapp):
    """``None`` survives the combo round-trip; ``currentData()`` would lose it."""
    config = _FakeConfig()
    widget = CoachSettings(config)

    _select_ttl(widget, "Never expire")

    assert config.config["explain_cache_ttl_days"] is None
    widget.deleteLater()


def test_explanation_sync_restores_null_and_numeric_ttl(qapp):
    config = _FakeConfig({"explain_cache_ttl_days": None})
    widget = CoachSettings(config)
    assert widget.explain_ttl_combo.currentText() == "Never expire"

    config.config["explain_cache_ttl_days"] = 90
    widget.sync_explanation_settings()

    assert widget.explain_ttl_combo.currentText() == "90 days"
    widget.deleteLater()


def test_trivial_move_toggle_writes_config(qapp):
    config = _FakeConfig()
    widget = CoachSettings(config)

    widget.explain_trivial_checkbox.setChecked(True)

    assert config.config["explain_llm_for_trivial_moves"] is True
    widget.deleteLater()


def test_coach_card_hides_as_a_whole_in_basic_mode(qapp):
    """Every Coach row is Advanced, so an empty card must not be left behind."""
    widget = CoachSettings(_FakeConfig())

    widget.set_advanced_visible(False)
    assert widget.isHidden() is True

    widget.set_advanced_visible(True)
    assert widget.isHidden() is False
    widget.deleteLater()

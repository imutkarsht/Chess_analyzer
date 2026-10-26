"""Coach explanation settings are binder-driven."""

from src.gui.views.settings.coach_settings import CoachSettings


class _FakeConfig:
    """Minimal ConfigManager stand-in; the Coach card only reads and assigns keys."""

    def __init__(self, overrides=None):
        self.config = {
            "explain_llm_for_trivial_moves": False,
            "explain_temperature": 0.3,
            "explain_max_tokens": 1024,
            "explain_reasoning_effort": "",
        }
        self.config.update(overrides or {})

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value


def test_coach_rows_reflect_saved_config(qapp):
    config = _FakeConfig({
        "explain_llm_for_trivial_moves": True,
        "explain_temperature": 1.1,
        "explain_max_tokens": 2048,
        "explain_reasoning_effort": "medium",
    })
    widget = CoachSettings(config)

    assert widget.explain_trivial_checkbox.isChecked() is True
    assert widget.temperature_input.value() == 1.1
    assert widget.max_tokens_input.value() == 2048
    assert widget.reasoning_effort_combo.currentData() == "medium"
    widget.deleteLater()


def test_coach_edits_write_config(qapp):
    config = _FakeConfig()
    widget = CoachSettings(config)

    widget.explain_trivial_checkbox.setChecked(True)
    widget.temperature_input.setValue(0.7)
    widget.max_tokens_input.setValue(512)
    widget.reasoning_effort_combo.setCurrentIndex(
        widget.reasoning_effort_combo.findData("high")
    )

    assert config.config["explain_llm_for_trivial_moves"] is True
    assert config.config["explain_temperature"] == 0.7
    assert config.config["explain_max_tokens"] == 512
    assert config.config["explain_reasoning_effort"] == "high"
    widget.deleteLater()


def test_basic_mode_keeps_the_card_and_hides_only_tuning(qapp):
    """The toggle is Basic, so the card must survive Basic mode."""
    widget = CoachSettings(_FakeConfig())

    widget.set_advanced_visible(False)

    assert widget.isHidden() is False
    assert widget.explain_trivial_checkbox.parentWidget().isHidden() is False
    assert widget.temperature_input.parentWidget().isHidden() is True
    assert widget.max_tokens_input.parentWidget().isHidden() is True
    assert widget.reasoning_effort_combo.parentWidget().isHidden() is True

    widget.set_advanced_visible(True)
    assert widget.temperature_input.parentWidget().isHidden() is False
    widget.deleteLater()

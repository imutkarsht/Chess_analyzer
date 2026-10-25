"""Coach explanation card is binder-driven."""

from src.gui.views.settings.coach_settings import CoachSettings


class _FakeConfig:
    """Minimal ConfigManager stand-in; the Coach card only reads and assigns keys."""

    def __init__(self, overrides=None):
        self.config = {
            "explain_llm_for_trivial_moves": False,
        }
        self.config.update(overrides or {})

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value


def test_coach_rows_reflect_saved_config(qapp):
    config = _FakeConfig({"explain_llm_for_trivial_moves": True})
    widget = CoachSettings(config)

    assert widget.explain_trivial_checkbox.isChecked() is True
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

"""Profile management and provider behaviour in the AI Coach settings card."""

from copy import deepcopy
from types import SimpleNamespace

from src.gui.views.settings.api_settings import ApiSettings
from src.gui.views.settings.api_settings import test_llm_sync as run_llm_test


class _FakeConfig:
    """Minimal ConfigManager surface used by ApiSettings."""

    def __init__(self, profiles, active="Groq"):
        self.profiles = deepcopy(profiles)
        self.values = {"llm_active_profile": active}

    def get_profiles(self):
        return deepcopy(self.profiles)

    def set_profiles(self, profiles, active_name=""):
        self.profiles = deepcopy(profiles)
        if active_name:
            self.values["llm_active_profile"] = active_name

    def get(self, key, default=None):
        return self.values.get(key, default)


def _profiles():
    return [
        {
            "name": "Groq",
            "provider": "groq",
            "api_key": "gsk_test",
            "model": "llama-3.3-70b-versatile",
            "base_url": "https://api.groq.com/openai/v1",
        },
        {
            "name": "OpenAI",
            "provider": "openai",
            "api_key": "sk-test",
            "model": "gpt-4o-mini",
            "base_url": "https://api.openai.com/v1",
        },
    ]


def test_provider_change_resets_model_and_url(qapp):
    config = _FakeConfig([_profiles()[0]])
    widget = ApiSettings(config)

    widget.llm_provider_combo.setCurrentIndex(
        widget.llm_provider_combo.findData("openai")
    )

    assert widget.llm_model_input.text() == "gpt-4o-mini"
    assert widget.llm_url_input.text() == "https://api.openai.com/v1"
    assert config.profiles[0]["model"] == "gpt-4o-mini"
    widget.deleteLater()


def test_keyless_provider_disables_the_key_field(qapp):
    config = _FakeConfig([_profiles()[0]])
    widget = ApiSettings(config)

    widget.llm_provider_combo.setCurrentIndex(
        widget.llm_provider_combo.findData("lmstudio")
    )
    assert widget.llm_key_input.line_edit.isEnabled() is False

    widget.llm_provider_combo.setCurrentIndex(
        widget.llm_provider_combo.findData("custom")
    )
    assert widget.llm_key_input.line_edit.isEnabled() is True
    widget.deleteLater()


def test_custom_base_url_stays_visible_in_basic_mode(qapp):
    config = _FakeConfig([_profiles()[0]])
    widget = ApiSettings(config)
    widget.set_advanced_visible(False)

    assert widget._base_url_wrapper.isHidden() is True

    widget.llm_provider_combo.setCurrentIndex(
        widget.llm_provider_combo.findData("custom")
    )
    assert widget._base_url_wrapper.isHidden() is False

    widget.set_advanced_visible(True)
    assert widget._base_url_wrapper.isHidden() is False
    widget.deleteLater()


def test_selection_does_not_activate_but_set_active_does(qapp):
    config = _FakeConfig(_profiles(), active="Groq")
    widget = ApiSettings(config)

    widget.llm_profile_combo.setCurrentIndex(1)
    assert config.get("llm_active_profile") == "Groq"

    widget._on_set_active()
    assert config.get("llm_active_profile") == "OpenAI"
    assert widget.llm_set_active_btn.isEnabled() is False
    widget.deleteLater()


def test_renaming_the_active_profile_keeps_it_active(qapp):
    config = _FakeConfig(_profiles(), active="Groq")
    widget = ApiSettings(config)

    widget.llm_profile_name.setText("Groq Work")
    assert widget._persist_current_profile() is True

    assert config.get("llm_active_profile") == "Groq Work"
    assert config.profiles[0]["name"] == "Groq Work"
    assert widget.llm_profile_combo.currentText() == "Groq Work"
    widget.deleteLater()


def test_duplicate_profile_name_is_rejected(qapp, mocker):
    config = _FakeConfig(_profiles(), active="Groq")
    widget = ApiSettings(config)
    warn = mocker.patch.object(widget, "_warn")

    widget.llm_profile_combo.setCurrentIndex(1)
    widget.llm_profile_name.setText("Groq")
    assert widget._persist_current_profile() is False

    assert config.profiles[1]["name"] == "OpenAI"
    warn.assert_called_once()
    widget.deleteLater()


def test_profile_edits_persist_on_field_commit(qapp):
    config = _FakeConfig([_profiles()[0]])
    widget = ApiSettings(config)

    widget.llm_model_input.setText("llama-3.1-8b-instant")
    widget.llm_model_input.editingFinished.emit()

    assert config.profiles[0]["model"] == "llama-3.1-8b-instant"
    widget.deleteLater()


def test_delete_is_disabled_with_one_profile(qapp):
    config = _FakeConfig([_profiles()[0]])
    widget = ApiSettings(config)

    assert widget.llm_del_btn.isEnabled() is False
    widget.deleteLater()


def test_provider_help_link_only_for_presets_with_a_url(qapp):
    config = _FakeConfig([_profiles()[0]])
    widget = ApiSettings(config)
    assert widget.llm_help_btn.isHidden() is False

    widget.llm_provider_combo.setCurrentIndex(
        widget.llm_provider_combo.findData("custom")
    )
    assert widget.llm_help_btn.isHidden() is True
    widget.deleteLater()


class _FakeCompletions:
    def __init__(self, error=None):
        self.error = error
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise RuntimeError(self.error)
        return SimpleNamespace()


def _fake_openai(mocker, error=None):
    completions = _FakeCompletions(error=error)

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=completions)

    mocker.patch("openai.OpenAI", FakeOpenAI)
    return completions


def test_connection_test_sends_explanation_tuning(mocker):
    completions = _fake_openai(mocker)

    ok, short, _details = run_llm_test(_profiles()[0], (0.7, 512, "medium"))

    assert ok is True
    assert short == "✓ Connected"
    assert completions.kwargs["temperature"] == 0.7
    assert completions.kwargs["max_tokens"] == 512
    assert completions.kwargs["reasoning_effort"] == "medium"


def test_connection_test_omits_tuning_when_not_provided(mocker):
    completions = _fake_openai(mocker)

    ok, _short, _details = run_llm_test(_profiles()[0])

    assert ok is True
    assert completions.kwargs["max_tokens"] == 10
    assert "temperature" not in completions.kwargs
    assert "reasoning_effort" not in completions.kwargs


def test_connection_test_surfaces_unsupported_tuning(mocker):
    _fake_openai(mocker, error="Unsupported parameter: reasoning_effort")

    ok, short, details = run_llm_test(_profiles()[0], (0.3, 1024, "low"))

    assert ok is False
    assert "reasoning_effort" in details
    assert short.startswith("✗")

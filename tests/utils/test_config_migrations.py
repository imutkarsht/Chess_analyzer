"""Tests for upgrade-safe config migration and typed accessors."""

import json

import pytest

from src.config.settings_schema import SECRET_PROFILE_PREFIX
from src.utils.config import ConfigManager
from src.utils.secrets import SecretStore


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """Isolate config and secrets files, and reset the shared config cache."""
    monkeypatch.setattr("src.utils.config.get_user_data_dir", lambda: str(tmp_path))
    ConfigManager._shared_config = None
    ConfigManager._shared_config_path = None
    yield tmp_path
    ConfigManager._shared_config = None
    ConfigManager._shared_config_path = None


def _write_config(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def _saved_config(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_legacy_flat_llm_config_becomes_a_profile(config_dir):
    config_file = config_dir / "config.json"
    _write_config(
        config_file,
        {"groq_api_key": "gsk_legacy", "groq_model": "llama-3.3-70b-versatile"},
    )

    manager = ConfigManager()

    profile = manager.get_active_profile()
    assert profile["name"] == "Groq"
    assert profile["provider"] == "groq"
    assert profile["api_key"] == "gsk_legacy"
    assert profile["model"] == "llama-3.3-70b-versatile"
    assert manager.get("groq_api_key") is None

    saved = _saved_config(config_file)
    assert saved["llm_active_profile"] == "Groq"
    assert "api_key" not in saved["llm_profiles"][0]
    assert "groq_api_key" not in saved


def test_profile_list_is_not_migrated_twice(config_dir):
    config_file = config_dir / "config.json"
    _write_config(
        config_file,
        {
            "llm_profiles": [
                {"name": "Work", "provider": "openai", "model": "gpt-4o", "api_key": ""}
            ],
            "llm_active_profile": "Work",
        },
    )

    manager = ConfigManager()

    assert manager.get_active_profile()["name"] == "Work"
    assert manager.get_active_profile()["provider"] == "openai"


def test_inline_lichess_token_moves_to_the_secret_store(config_dir):
    config_file = config_dir / "config.json"
    _write_config(config_file, {"lichess_token": "lip_inline"})

    manager = ConfigManager()

    assert manager.get("lichess_token") == "lip_inline"
    assert _saved_config(config_file)["lichess_token"] == ""

    manager.set("lichess_token", "lip_new")

    assert manager.get("lichess_token") == "lip_new"
    assert _saved_config(config_file)["lichess_token"] == ""


def test_set_profiles_keeps_keys_out_of_config_file(config_dir):
    manager = ConfigManager()

    manager.set_profiles(
        [
            {"name": "Work", "provider": "openai", "api_key": "sk-work", "model": "gpt-4o"},
            {"name": "Home", "provider": "groq", "api_key": "gsk-home", "model": "llama"},
        ],
        active_name="Home",
    )

    saved = _saved_config(config_dir / "config.json")
    assert [profile["name"] for profile in saved["llm_profiles"]] == ["Work", "Home"]
    assert all("api_key" not in profile for profile in saved["llm_profiles"])
    assert manager.get_active_profile()["name"] == "Home"
    assert manager.get("llm_profiles")[0]["api_key"] == "sk-work"

    store = SecretStore(str(config_dir / SecretStore.FILE))
    assert store.get(f"{SECRET_PROFILE_PREFIX}Work") == "sk-work"


def test_missing_active_profile_falls_back_to_first(config_dir):
    manager = ConfigManager()

    manager.set_profiles(
        [{"name": "Only", "provider": "groq", "api_key": "", "model": "llama"}],
        active_name="Deleted",
    )

    assert manager.get_active_profile()["name"] == "Only"


def test_save_failure_is_logged_not_raised(config_dir, mocker):
    manager = ConfigManager()
    error_log = mocker.patch("src.utils.config.logger.error")
    mocker.patch("builtins.open", side_effect=OSError("read-only filesystem"))

    manager.set("theme", "dark")

    assert error_log.called


@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, True), (0, False), (1, True), (" YES ", True), ("off", False), (None, True)],
)
def test_get_bool_coerces_stored_values(config_dir, value, expected):
    manager = ConfigManager()
    manager.config["custom_flag"] = value

    assert manager.get_bool("custom_flag", default=True) is expected


@pytest.mark.parametrize(
    ("value", "default", "expected"), [("12", 0, 12), (3.9, 0, 3), (None, 7, 7), ("x", 7, 7)]
)
def test_get_int_falls_back_for_invalid_values(config_dir, value, default, expected):
    manager = ConfigManager()
    manager.config["custom_int"] = value

    assert manager.get_int("custom_int", default) == expected


@pytest.mark.parametrize(
    ("value", "default", "expected"), [("2.5", 0.0, 2.5), (None, 1.5, 1.5), ("x", 1.5, 1.5)]
)
def test_get_float_falls_back_for_invalid_values(config_dir, value, default, expected):
    manager = ConfigManager()
    manager.config["custom_float"] = value

    assert manager.get_float("custom_float", default) == expected


def test_get_choice_rejects_values_outside_the_schema(config_dir):
    manager = ConfigManager()
    manager.config["theme_mode"] = "dark"
    assert manager.get_choice("theme_mode", "system") == "dark"

    manager.config["theme_mode"] = "neon"
    assert manager.get_choice("theme_mode", "system") == "system"

    assert manager.get_choice("unknown_setting", "fallback") == "fallback"


@pytest.mark.parametrize(("value", "expected"), [(0, 1), (3, 3), (99, 5)])
def test_set_clamps_bounded_int_settings(config_dir, value, expected):
    manager = ConfigManager()

    manager.set("live_multi_pv", value)

    assert manager.get("live_multi_pv") == expected


def test_invalid_bool_setting_keeps_the_previous_value(config_dir):
    manager = ConfigManager()
    assert manager.get("use_cache") is True

    manager.set("use_cache", "not-a-bool")

    assert manager.get("use_cache") is True

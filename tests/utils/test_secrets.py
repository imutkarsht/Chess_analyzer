"""Tests for keychain-backed secret storage and its plaintext fallback."""

import json
import stat

import pytest

from src.utils import secrets
from src.utils.secrets import SecretStore


@pytest.fixture
def legacy_path(tmp_path):
    return tmp_path / "secrets.json"


@pytest.fixture
def keychain(mocker):
    """Pretend a working OS keychain exists and capture its calls."""
    mocker.patch.object(secrets, "KEYRING_AVAILABLE", True)
    fake = mocker.patch.object(secrets, "keyring")
    fake.get_password.return_value = None
    return fake


def _write_legacy(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_set_and_get_delegate_to_keychain(keychain, legacy_path):
    store = SecretStore(str(legacy_path))

    store.set("groq_api_key", "  gsk_secret  ")

    keychain.set_password.assert_called_once_with(
        secrets.SERVICE_NAME, "groq_api_key", "gsk_secret"
    )
    keychain.get_password.return_value = "gsk_secret"
    assert store.get("groq_api_key") == "gsk_secret"
    assert not legacy_path.exists()


def test_keychain_read_failure_falls_back_to_legacy_data(keychain, legacy_path):
    _write_legacy(legacy_path, {"lichess_token": "lip_from_file"})
    # Simulate the migration failing so the plaintext data survives in memory.
    keychain.set_password.side_effect = secrets.KeyringError("locked")
    store = SecretStore(str(legacy_path))
    keychain.get_password.side_effect = secrets.KeyringError("locked")

    assert store.get("lichess_token") == "lip_from_file"
    assert store.get("missing", "fallback") == "fallback"


def test_set_failure_writes_private_fallback_file(keychain, legacy_path, mocker):
    keychain.set_password.side_effect = secrets.KeyringError("locked")
    mocker.patch.object(secrets, "KEYRING_AVAILABLE", False)
    store = SecretStore(str(legacy_path))

    store.set("openai_api_key", "sk-test-value")

    assert json.loads(legacy_path.read_text(encoding="utf-8")) == {
        "openai_api_key": "sk-test-value"
    }
    assert stat.S_IMODE(legacy_path.stat().st_mode) == 0o600
    assert SecretStore(str(legacy_path)).get("openai_api_key") == "sk-test-value"


def test_set_blank_value_deletes_secret(legacy_path):
    store = SecretStore(str(legacy_path))
    store.set("token", "keep-me")

    store.set("token", "   ")

    assert store.get("token") == ""
    assert json.loads(legacy_path.read_text(encoding="utf-8")) == {}


def test_delete_removes_fallback_entry(legacy_path):
    store = SecretStore(str(legacy_path))
    store.set("a", "1")
    store.set("b", "2")

    store.delete("a")

    assert store.get("a") == ""
    assert json.loads(legacy_path.read_text(encoding="utf-8")) == {"b": "2"}


def test_legacy_secrets_are_migrated_and_file_removed(keychain, legacy_path):
    _write_legacy(legacy_path, {"lichess_token": "lip_old"})

    store = SecretStore(str(legacy_path))

    keychain.set_password.assert_called_once_with(
        secrets.SERVICE_NAME, "lichess_token", "lip_old"
    )
    assert not legacy_path.exists()
    assert store._data == {}


def test_migration_failure_preserves_file_for_retry(keychain, legacy_path):
    _write_legacy(legacy_path, {"token": "value"})
    keychain.set_password.side_effect = secrets.KeyringError("no backend")

    store = SecretStore(str(legacy_path))

    assert legacy_path.exists()
    assert store.get("token") == "value"


@pytest.mark.parametrize("payload", ["{not json", "[1, 2]"])
def test_malformed_legacy_file_is_ignored(legacy_path, payload):
    legacy_path.write_text(payload, encoding="utf-8")

    store = SecretStore(str(legacy_path))

    assert store.get("anything", "default") == "default"


def test_reload_picks_up_external_changes(legacy_path):
    store = SecretStore(str(legacy_path))
    assert store.get("token") == ""

    _write_legacy(legacy_path, {"token": "new-value"})
    store.reload()

    assert store.get("token") == "new-value"


def test_fallback_write_failure_is_logged_not_raised(legacy_path, mocker):
    error_log = mocker.patch.object(secrets.logger, "error")
    mocker.patch("src.utils.secrets.os.replace", side_effect=OSError("disk full"))
    store = SecretStore(str(legacy_path))

    store.set("token", "value")

    assert error_log.called

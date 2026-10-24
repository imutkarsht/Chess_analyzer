"""Secret storage backed by the operating system credential store.

API keys and tokens must remain usable by the app, so hashing is not an
option.  The OS keychain (macOS Keychain, Windows Credential Locker, Linux
Secret Service) gives us encryption at rest, user-session protection, and
per-application access control without keeping the key beside the ciphertext.
"""

from __future__ import annotations

import json
import os

from src.utils.logger import logger
from src.utils.path_utils import get_user_data_dir

try:
    import keyring
    from keyring.errors import KeyringError

    KEYRING_AVAILABLE = True
except ImportError:  # pragma: no cover - keyring is a production dependency
    keyring = None
    KeyringError = Exception
    KEYRING_AVAILABLE = False


SERVICE_NAME = "ChessAnalyzerPro"


class SecretStore:
    """Stores secrets in the OS keychain, with a 0600 file only as fallback."""

    FILE = "secrets.json"

    def __init__(self, path: str | None = None) -> None:
        self.path = path or os.path.join(get_user_data_dir(), self.FILE)
        self._data: dict[str, str] = self._load_legacy_file()
        self._migrate_legacy_file()

    # ------------------------------------------------------------------
    # Keychain-backed API
    # ------------------------------------------------------------------
    def _load_legacy_file(self) -> dict[str, str]:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, encoding="utf-8") as handle:
                data = json.load(handle)
            return {str(k): str(v) for k, v in data.items() if v}
        except Exception as exc:
            logger.error("Failed to load legacy secrets file: %s", exc)
            return {}

    def _migrate_legacy_file(self) -> None:
        """Move any previously stored plaintext secrets into the keychain."""
        if not KEYRING_AVAILABLE or not self._data:
            return
        try:
            for key, value in list(self._data.items()):
                keyring.set_password(SERVICE_NAME, key, value)
        except KeyringError as exc:
            logger.warning("Could not migrate secrets to OS keychain: %s", exc)
            return

        try:
            os.remove(self.path)
        except OSError:
            pass
        self._data.clear()
        logger.info("Migrated local secrets into the OS credential store.")

    def reload(self) -> None:
        self._data = self._load_legacy_file()
        self._migrate_legacy_file()

    def get(self, key: str, default: str = "") -> str:
        if KEYRING_AVAILABLE:
            try:
                value = keyring.get_password(SERVICE_NAME, key)
                if value is not None:
                    return value
            except KeyringError as exc:
                logger.warning("OS keychain read failed: %s", exc)
        return self._data.get(key, default)

    def set(self, key: str, value: str) -> None:
        value = (value or "").strip()
        if not value:
            self.delete(key)
            return

        if KEYRING_AVAILABLE:
            try:
                keyring.set_password(SERVICE_NAME, key, value)
                self._data.pop(key, None)
                return
            except KeyringError as exc:
                logger.warning("OS keychain write failed, using local fallback: %s", exc)

        self._data[key] = value
        self._save_fallback()

    def delete(self, key: str) -> None:
        if KEYRING_AVAILABLE:
            try:
                keyring.delete_password(SERVICE_NAME, key)
            except KeyringError:
                pass
        if key in self._data:
            self._data.pop(key, None)
            self._save_fallback()

    # ------------------------------------------------------------------
    # Fallback for environments without a working keychain backend
    # ------------------------------------------------------------------
    def _save_fallback(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            temp_path = f"{self.path}.tmp"
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump(self._data, handle, indent=2)
            os.replace(temp_path, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        except Exception as exc:
            logger.error("Failed to save fallback secrets file: %s", exc)

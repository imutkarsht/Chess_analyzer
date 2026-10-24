"""Tiny permission-restricted secret store for API tokens."""

from __future__ import annotations

import json
import os

from src.utils.logger import logger
from src.utils.path_utils import get_user_data_dir


class SecretStore:
    """Stores secrets separately from ``config.json`` with 0600 permissions."""

    FILE = "secrets.json"

    def __init__(self, path: str | None = None) -> None:
        self.path = path or os.path.join(get_user_data_dir(), self.FILE)
        self._data: dict[str, str] = self._load()

    def _load(self) -> dict[str, str]:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, encoding="utf-8") as handle:
                data = json.load(handle)
            return {str(k): str(v) for k, v in data.items() if v}
        except Exception as exc:
            logger.error("Failed to load secrets store: %s", exc)
            return {}

    def reload(self) -> None:
        self._data = self._load()

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key, default)

    def set(self, key: str, value: str) -> None:
        value = (value or "").strip()
        if value:
            self._data[key] = value
        else:
            self._data.pop(key, None)
        self._save()

    def delete(self, key: str) -> None:
        if key in self._data:
            self._data.pop(key, None)
            self._save()

    def _save(self) -> None:
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
            logger.error("Failed to save secrets store: %s", exc)

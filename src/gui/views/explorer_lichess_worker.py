"""Background worker for the Lichess opening explorer.

Lichess requires an authenticated account for explorer requests (since March
2026), so every live fetch sends the user's personal API token. The worker
still reads the local cache before checking the token, keeping cached positions
available offline. Transport and auth failures are reported distinctly so the
view can fall back to the local book and stop retrying when appropriate.
"""

import json
import urllib.parse

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from src.backend.api.base_api import BaseChessAPI
from src.constants import LICHESS_EXPLORER_URL


class LichessExplorerWorker(QThread):
    loaded = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        fen: str,
        cache_enabled: bool,
        history_manager,
        token: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.fen = fen
        self.cache_enabled = cache_enabled
        self.history_manager = history_manager
        self.token = (token or "").strip()

    def run(self):
        try:
            parts = self.fen.split()
            norm_fen = " ".join(parts[:4])

            if self.cache_enabled:
                cached = self.history_manager.get_explorer_cache(norm_fen)
                if cached:
                    try:
                        self.loaded.emit(json.loads(cached))
                        return
                    except (TypeError, ValueError):
                        # Corrupt cache row: fall through and fetch fresh data.
                        pass

            # The view gates on a token, but a worker can still be started
            # directly (see close/retire paths); fail fast instead of issuing
            # an anonymous request that Lichess rejects.
            if not self.token:
                self.error.emit("unauthorized")
                return

            encoded_fen = urllib.parse.quote(self.fen)
            url = (
                f"{LICHESS_EXPLORER_URL}"
                f"?fen={encoded_fen}"
                "&speeds=blitz,rapid,classical"
                "&ratings=1600,1800,2000,2200,2500"
            )
            headers = dict(BaseChessAPI.DEFAULT_HEADERS)
            headers["Authorization"] = f"Bearer {self.token}"
            resp = requests.get(url, headers=headers, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                if self.cache_enabled:
                    self.history_manager.save_explorer_cache(
                        norm_fen, json.dumps(data)
                    )
                self.loaded.emit(data)
            elif resp.status_code in (401, 403):
                self.error.emit("unauthorized")
            elif resp.status_code == 429:
                self.error.emit("rate_limited")
            else:
                self.error.emit(f"HTTP {resp.status_code}")
        except requests.exceptions.RequestException:
            self.error.emit("offline")
        except Exception as e:
            self.error.emit(str(e))

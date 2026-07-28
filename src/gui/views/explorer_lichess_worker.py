from PyQt6.QtCore import QThread, pyqtSignal


class LichessExplorerWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, fen: str, cache_enabled: bool, history_manager, token: str = "", parent=None):
        super().__init__(parent)
        self.fen = fen
        self.cache_enabled = cache_enabled
        self.history_manager = history_manager
        self.token = token

    def run(self):
        try:
            import requests
            import urllib.parse
            import json
            parts = self.fen.split()
            norm_fen = " ".join(parts[:4])

            if self.cache_enabled:
                cached = self.history_manager.get_explorer_cache(norm_fen)
                if cached:
                    self.finished.emit(json.loads(cached))
                    return

            encoded_fen = urllib.parse.quote(self.fen)
            url = f"https://explorer.lichess.ovh/lichess?fen={encoded_fen}&speeds=blitz,rapid,classical&ratings=1600,1800,2000,2200,2500"
            headers = {"User-Agent": "ChessAnalyzer/1.0"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if self.cache_enabled:
                    self.history_manager.save_explorer_cache(norm_fen, json.dumps(data))
                self.finished.emit(data)
            else:
                self.error.emit(f"HTTP Error {resp.status_code}")
        except Exception as e:
            self.error.emit(str(e))

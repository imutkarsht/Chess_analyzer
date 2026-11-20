# SPDX-License-Identifier: GPL-3.0-only
"""Background LLM connection-test workers."""

import time

from PyQt6.QtCore import QThread, pyqtSignal


class LLMTestWorker(QThread):
    """Minimal connection test used by the setup wizard."""

    finished = pyqtSignal(bool, str)

    def __init__(self, api_key: str, base_url: str, model: str, parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def run(self):
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=self.api_key or "not-needed",
                base_url=self.base_url,
            )
            client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Reply with just the word: ok"}],
                max_tokens=10,
                timeout=15.0,
            )
            self.finished.emit(True, "Connection successful")
        except Exception as exc:
            self.finished.emit(False, str(exc))


class LLMProfileTestWorker(QThread):
    """Profile/tuning-aware test used by API settings."""

    done = pyqtSignal(bool, str, str, float)

    def __init__(self, profile: dict, tuning: tuple, test_callable, parent=None):
        super().__init__(parent)
        self._profile = profile
        self._tuning = tuning
        self._test_callable = test_callable

    def run(self):
        start = time.perf_counter()
        ok, short, full = self._test_callable(self._profile, self._tuning)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.done.emit(ok, short, full, elapsed_ms)


__all__ = ["LLMProfileTestWorker", "LLMTestWorker"]

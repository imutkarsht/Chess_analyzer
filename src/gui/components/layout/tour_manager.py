from dataclasses import dataclass

from PyQt6.QtWidgets import QWidget


@dataclass
class TourStep:
    target: QWidget
    text: str
    position: str = "above"  # above | below | left | right
    page_index: int = 0
    title: str = ""
    tour_key: str = ""


LEGACY_TOUR_MAP: dict[str, str] = {
    "0": "analysis",
    "1": "explorer",
    "2": "history",
    "3": "metrics",
    "4": "settings",
}
INVERSE_LEGACY_MAP: dict[str, str] = {v: k for k, v in LEGACY_TOUR_MAP.items()}


class TourManager:
    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        self._current_step = 0
        self._steps: list[TourStep] = []
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    @property
    def current_step(self) -> int:
        return self._current_step

    @property
    def total_steps(self) -> int:
        return len(self._steps)

    @property
    def current(self) -> TourStep | None:
        if 0 <= self._current_step < len(self._steps):
            return self._steps[self._current_step]
        return None

    def start(self, steps: list[TourStep]) -> None:
        self._steps = list(steps)
        self._current_step = 0
        self._active = True

    def next(self) -> bool:
        if self._current_step < len(self._steps) - 1:
            self._current_step += 1
            return True
        self._active = False
        return False

    def prev(self) -> bool:
        if self._current_step > 0:
            self._current_step -= 1
            return True
        return False

    def stop(self) -> None:
        self._active = False
        self._current_step = 0

    def has_seen_tour(self, key: str | int) -> bool:
        if self.config_manager is None:
            return True
        seen = self.config_manager.get("tour_seen_pages", {})
        str_key = str(key)
        if seen.get(str_key, False):
            return True
        # Check mapped legacy key (e.g. if key is "analysis", check legacy "0")
        legacy_key = INVERSE_LEGACY_MAP.get(str_key)
        if legacy_key and seen.get(legacy_key, False):
            seen[str_key] = True
            self.config_manager.set("tour_seen_pages", seen)
            return True
        # Check mapped modern key (e.g. if legacy integer 1 passed, check "explorer")
        modern_key = LEGACY_TOUR_MAP.get(str_key)
        if modern_key and seen.get(modern_key, False):
            return True
        return bool(modern_key and seen.get(modern_key, False))

    def mark_seen(self, key: str | int) -> None:
        if self.config_manager is None:
            return
        seen = self.config_manager.get("tour_seen_pages", {})
        str_key = str(key)
        actual_key = LEGACY_TOUR_MAP.get(str_key, str_key)
        seen[actual_key] = True
        self.config_manager.set("tour_seen_pages", seen)

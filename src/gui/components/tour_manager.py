from dataclasses import dataclass, field
from typing import Optional
from PyQt6.QtWidgets import QWidget


@dataclass
class TourStep:
    target: QWidget
    text: str
    position: str = "above"  # above | below | left | right
    page_index: int = 0


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
    def current(self) -> Optional[TourStep]:
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

    def has_seen_tour(self, page_index: int) -> bool:
        if self.config_manager is None:
            return True
        seen = self.config_manager.get("tour_seen_pages", {})
        return seen.get(str(page_index), False)

    def mark_seen(self, page_index: int) -> None:
        if self.config_manager is None:
            return
        seen = self.config_manager.get("tour_seen_pages", {})
        seen[str(page_index)] = True
        self.config_manager.set("tour_seen_pages", seen)

"""Central motion system: durations, easings and animation helpers.

Every animated surface in the GUI pulls its timing from this module, so the app
shares one motion language, one place to change it, and one "reduce motion"
contract. Call sites must not hardcode millisecond values or easing curves.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QEasingCurve, QObject, QPropertyAnimation, QVariantAnimation
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QScrollBar


class MotionDuration:
    """One-shot transition lengths, in milliseconds."""

    INSTANT = 90
    FAST = 140
    BASE = 190
    SLOW = 260

    # Looping indicators (skeletons, shimmer, pulses) are intentionally slow so
    # they read as ambient progress rather than as content movement.
    LOOP = 1200
    LOOP_SLOW = 2000
    PULSE = 900


class MotionEasing:
    """Easing curves grouped by intent instead of by curve name."""

    ENTER = QEasingCurve.Type.OutCubic
    EXIT = QEasingCurve.Type.InCubic
    STATE = QEasingCurve.Type.InOutQuad
    LOOP = QEasingCurve.Type.InOutSine
    LINEAR = QEasingCurve.Type.Linear


class Motion:
    """Animation factory that keeps at most one animation per (object, property).

    Retargeting is the reason this exists: a new wheel notch, hover or layout
    change stops the in-flight animation and restarts from the *current* value
    instead of from the previous target, which is what makes motion feel
    interruptible rather than queued.
    """

    _enabled: bool | None = None
    _running: dict[tuple[int, bytes], QPropertyAnimation] = {}

    # -- enablement ---------------------------------------------------------

    @classmethod
    def set_enabled(cls, enabled: bool | None) -> None:
        """Force motion on/off; ``None`` restores automatic detection."""
        cls._enabled = None if enabled is None else bool(enabled)

    @classmethod
    def enabled(cls) -> bool:
        """False under tests/offscreen so the suite never waits on animation."""
        if cls._enabled is not None:
            return cls._enabled
        if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
            return False
        app = QGuiApplication.instance()
        return not (app is not None and app.platformName() == "offscreen")

    # -- one-shot property tweens ------------------------------------------

    @classmethod
    def animate(
        cls,
        target: QObject,
        prop: bytes,
        to: Any,
        *,
        duration: int = MotionDuration.FAST,
        easing: QEasingCurve.Type = MotionEasing.STATE,
        start: Any = None,
    ) -> QPropertyAnimation | None:
        """Tween ``prop`` on ``target``, replacing any animation already running."""
        key = (id(target), bytes(prop))
        cls._take(key)
        if not cls.enabled():
            target.setProperty(prop.decode(), to)
            return None

        animation = QPropertyAnimation(target, prop, target)
        animation.setDuration(duration)
        animation.setEasingCurve(easing)
        if start is not None:
            animation.setStartValue(start)
        animation.setEndValue(to)
        animation.finished.connect(lambda: cls._forget(key, animation))
        animation.destroyed.connect(lambda *_: cls._forget(key, animation))
        cls._running[key] = animation
        animation.start()
        return animation

    @classmethod
    def animate_value(
        cls,
        parent: QObject,
        start: Any,
        end: Any,
        on_value: Callable[[Any], None],
        *,
        duration: int,
        easing: QEasingCurve.Type = MotionEasing.STATE,
        loops: int = 1,
    ) -> QVariantAnimation | None:
        """Tween a bare value (no Qt property) and feed it to ``on_value``."""
        if not cls.enabled():
            on_value(end)
            return None

        animation = QVariantAnimation(parent)
        animation.setDuration(duration)
        animation.setEasingCurve(easing)
        animation.setStartValue(start)
        animation.setEndValue(end)
        animation.setLoopCount(loops)
        animation.valueChanged.connect(on_value)
        animation.start()
        return animation

    # -- scrolling ----------------------------------------------------------

    @classmethod
    def scroll_to(
        cls,
        bar: QScrollBar,
        value: int,
        *,
        duration: int = MotionDuration.FAST,
    ) -> QPropertyAnimation | None:
        """Ease a scroll bar to ``value``, clamped to its valid range."""
        target = max(bar.minimum(), min(bar.maximum(), int(value)))
        return cls.animate(bar, b"value", target, duration=duration, easing=MotionEasing.ENTER)

    @classmethod
    def stop(cls, target: QObject, prop: bytes) -> None:
        """Cancel a running tween without jumping to its end value."""
        cls._take((id(target), bytes(prop)))

    # -- internals ----------------------------------------------------------

    @classmethod
    def _take(cls, key: tuple[int, bytes]) -> QPropertyAnimation | None:
        animation = cls._running.pop(key, None)
        if animation is None:
            return None
        try:
            animation.stop()
            animation.deleteLater()
        except RuntimeError:  # underlying C++ object already destroyed
            pass
        return animation

    @classmethod
    def _forget(cls, key: tuple[int, bytes], animation: QPropertyAnimation) -> None:
        if cls._running.get(key) is animation:
            cls._running.pop(key, None)
        try:
            animation.deleteLater()
        except RuntimeError:
            pass

"""Page container with a snapshot cross-fade between pages.

The fade runs on a single pre-rendered pixmap of the outgoing page instead of a
``QGraphicsOpacityEffect`` over the live page tree. That keeps the cost of a
page transition constant: the history page carries ~200 styled widgets and the
stats dashboard embeds matplotlib canvases, but the animation only composites
one image, so every page transitions at the same frame rate.
"""

from __future__ import annotations

import os
import sys

from PyQt6.QtCore import QPropertyAnimation, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QLabel, QStackedWidget

from src.gui.theme.motion import MotionDuration, MotionEasing


class FadedStackedWidget(QStackedWidget):
    """Stacked pages that cross-fade through a snapshot overlay."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fade: QPropertyAnimation | None = None
        self._overlay: QLabel | None = None

    def _should_animate(self) -> bool:
        if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
            return False
        app = QGuiApplication.instance()
        return not (app and app.platformName() == "offscreen")

    def setCurrentIndex(self, index):  # noqa: N802 - Qt override
        if index < 0 or index >= self.count():
            return
        if index == self.currentIndex():
            return

        outgoing = self.currentWidget()
        snapshot = None
        if outgoing is not None and outgoing.isVisible():
            snapshot = outgoing.grab()

        self._clear_overlay()
        super().setCurrentIndex(index)

        if snapshot is None or snapshot.isNull() or not self._should_animate():
            return
        self._crossfade(snapshot)

    def _crossfade(self, snapshot) -> None:
        overlay = QLabel(self)
        overlay.setObjectName("PageTransitionOverlay")
        overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        overlay.setPixmap(snapshot)
        overlay.setGeometry(self.rect())
        overlay.show()
        overlay.raise_()

        effect = QGraphicsOpacityEffect(overlay)
        effect.setOpacity(1.0)
        overlay.setGraphicsEffect(effect)

        animation = QPropertyAnimation(effect, b"opacity", overlay)
        animation.setDuration(MotionDuration.FAST)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(MotionEasing.ENTER)
        animation.finished.connect(self._clear_overlay)

        self._overlay = overlay
        self._fade = animation
        animation.start()

    def _clear_overlay(self) -> None:
        if self._fade is not None:
            self._fade.stop()
            self._fade.deleteLater()
            self._fade = None
        if self._overlay is not None:
            self._overlay.deleteLater()
            self._overlay = None

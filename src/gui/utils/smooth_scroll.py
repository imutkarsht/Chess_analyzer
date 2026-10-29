"""Shared wheel scrolling for every scrollable surface in the app.

``SmoothScroll`` owns the behaviour: trackpads scroll pixel-for-pixel, discrete
wheel notches scroll one row/card with an ease, and at a range edge the event is
handed back so a nested outer scroll area can continue. ``SmoothScrollRouter``
installs that behaviour application-wide once, so pages, dialogs and Qt's own
popups do not each re-implement scrolling.

Opt a surface out with :meth:`SmoothScroll.disable` when it owns wheel input
(canvas panning, dropdown value cycling). Areas whose scroll bars are both
``ScrollBarAlwaysOff`` are skipped automatically because they scroll themselves.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QApplication,
    QWidget,
)

from src.gui.theme.motion import Motion

_MIN_STEP = 32
_MAX_STEP = 160
_MIN_DURATION = 90
_MAX_DURATION = 220
_DEFAULT_STEP = 48


def _clamp(value: float, low: int, high: int) -> int:
    return int(max(low, min(high, value)))


class SmoothScroll(QObject):
    """Eased, pixel-precise wheel scrolling for one scroll area."""

    def __init__(self, area: QAbstractScrollArea, *, step: int | None = None):
        super().__init__(area)
        self.setObjectName("SmoothScroll")
        self._area = area
        self._step = step
        area.setProperty("smoothScroll", True)
        if isinstance(area, QAbstractItemView):
            # Qt's per-item mode quantises every wheel event to whole rows.
            area.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

    @staticmethod
    def disable(widget: QWidget) -> None:
        """Exclude a widget and its subtree from routed smooth scrolling."""
        widget.setProperty("smoothScroll", False)

    def handle(self, event) -> bool:
        """Consume a wheel event, or return False to let it propagate."""
        vertical = self._area.verticalScrollBar()
        horizontal = self._area.horizontalScrollBar()
        pixel = event.pixelDelta()
        angle = event.angleDelta()
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

        if shift and horizontal.maximum() > 0:
            delta = pixel.x() or pixel.y()
            return self._apply(horizontal, delta, angle.y(), event)
        return self._apply(vertical, pixel.y(), angle.y(), event)

    def _apply(self, bar, pixel_delta: int, angle_delta: int, event) -> bool:
        if pixel_delta:
            # Trackpads already deliver pixel-precise deltas: never add easing.
            Motion.stop(bar, b"value")
            bar.setValue(bar.value() - pixel_delta)
            event.accept()
            return True

        if not angle_delta:
            return False

        step = self._step or _clamp(bar.singleStep() or _DEFAULT_STEP, _MIN_STEP, _MAX_STEP)
        target = bar.value() - (step if angle_delta > 0 else -step)
        target = _clamp(target, bar.minimum(), bar.maximum())
        if target == bar.value():
            event.ignore()  # at an edge: let an outer scroll area take over
            return False

        distance = abs(target - bar.value())
        duration = _clamp(_MIN_DURATION + distance * 0.35, _MIN_DURATION, _MAX_DURATION)
        Motion.scroll_to(bar, target, duration=duration)
        event.accept()
        return True


def _scrolling_area(widget: QWidget) -> QAbstractScrollArea | None:
    """Nearest scroll area above ``widget`` that is allowed to smooth-scroll."""
    node: QWidget | None = widget
    while node is not None:
        if node.property("smoothScroll") is False:
            return None
        if isinstance(node, QAbstractScrollArea):
            self_managed = (
                node.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                and node.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            return None if self_managed else node
        node = node.parentWidget()
    return None


def scroller_for(area: QAbstractScrollArea) -> SmoothScroll:
    """Return the area's own scroller, attaching one on first use.

    The lookup must be direct-children-only: a recursive ``findChild`` happily
    returns a scroller attached to a *nested* area (e.g. the sortable list inside
    a settings card), which would leave the visible page unable to scroll.
    """
    scroller = area.findChild(
        SmoothScroll,
        "SmoothScroll",
        Qt.FindChildOption.FindDirectChildrenOnly,
    )
    if scroller is None:
        scroller = SmoothScroll(area)
    return scroller


class SmoothScrollRouter(QObject):
    """Application-wide wheel router: one install covers every scroll surface."""

    def __init__(self, app: QApplication):
        super().__init__(app)
        self.setObjectName("SmoothScrollRouter")

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 - Qt override
        if event.type() is not QEvent.Type.Wheel or not isinstance(obj, QWidget):
            return False
        area = _scrolling_area(obj)
        if area is None:
            return False
        return scroller_for(area).handle(event)


def install_smooth_scrolling(app: QApplication | None = None) -> SmoothScrollRouter | None:
    """Install the router once on the application (idempotent)."""
    app = app or QApplication.instance()
    if app is None:
        return None
    router = app.findChild(SmoothScrollRouter, "SmoothScrollRouter")
    if router is None:
        router = SmoothScrollRouter(app)
        app.installEventFilter(router)
    return router

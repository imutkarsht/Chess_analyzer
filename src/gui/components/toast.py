"""Single toast notification system for the whole app.

One widget and one manager replace the ad-hoc floating labels that every view
used to create itself. The look follows the notification references: a neutral
elevated surface, hairline border, outline glyph, and a close affordance.

Key behaviours:

* five variants — success, warning (``"warn"`` alias), info, error, loading
* a loading toast can morph in place into success/error/info via a handle
* one transparent host per top-level window, so toasts stack, survive page
  changes, and never block clicks outside the stack
* every visual and behavioural detail is configurable per toast or globally

Call sites never construct :class:`Toast` directly; they use
:class:`ToastManager`, which keeps duration defaults, dedupe, and positioning
consistent. See ``ToastOptions`` for the full configuration surface.
"""

from __future__ import annotations

import time
import weakref
from collections.abc import Callable
from dataclasses import dataclass, fields, replace
from enum import StrEnum

from PyQt6.QtCore import QEasingCurve, QSize, Qt, QTimer, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QIcon, QPainter
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from src.gui.components.button import Button, ButtonSize, ButtonVariant
from src.gui.components.toast_icons import toast_icon
from src.gui.styles import Styles
from src.gui.theme import ThemeManager

try:
    import qtawesome as qta
except ImportError:  # pragma: no cover - QtAwesome ships with the app
    qta = None


class ToastVariant(StrEnum):
    SUCCESS = "success"
    WARNING = "warning"
    INFO = "info"
    ERROR = "error"
    LOADING = "loading"


class ToastPosition(StrEnum):
    TOP_RIGHT = "top_right"
    TOP_CENTER = "top_center"
    TOP_LEFT = "top_left"
    BOTTOM_RIGHT = "bottom_right"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_LEFT = "bottom_left"


_VARIANT_ALIASES = {
    "success": ToastVariant.SUCCESS,
    "warn": ToastVariant.WARNING,
    "warning": ToastVariant.WARNING,
    "info": ToastVariant.INFO,
    "error": ToastVariant.ERROR,
    "loading": ToastVariant.LOADING,
}

_POSITION_ALIASES = {
    "top_right": ToastPosition.TOP_RIGHT,
    "top-right": ToastPosition.TOP_RIGHT,
    "topright": ToastPosition.TOP_RIGHT,
    "top_center": ToastPosition.TOP_CENTER,
    "top-center": ToastPosition.TOP_CENTER,
    "topcenter": ToastPosition.TOP_CENTER,
    "top_left": ToastPosition.TOP_LEFT,
    "top-left": ToastPosition.TOP_LEFT,
    "topleft": ToastPosition.TOP_LEFT,
    "bottom_right": ToastPosition.BOTTOM_RIGHT,
    "bottom-right": ToastPosition.BOTTOM_RIGHT,
    "bottomright": ToastPosition.BOTTOM_RIGHT,
    "bottom_center": ToastPosition.BOTTOM_CENTER,
    "bottom-center": ToastPosition.BOTTOM_CENTER,
    "bottomcenter": ToastPosition.BOTTOM_CENTER,
    "bottom_left": ToastPosition.BOTTOM_LEFT,
    "bottom-left": ToastPosition.BOTTOM_LEFT,
    "bottomleft": ToastPosition.BOTTOM_LEFT,
}

_TOP_POSITIONS = frozenset(
    {ToastPosition.TOP_LEFT, ToastPosition.TOP_CENTER, ToastPosition.TOP_RIGHT}
)

# How long each variant stays on screen. Loading is persistent until the caller
# updates or dismisses it; a timer would risk hiding work that is still running.
_VARIANT_DURATIONS: dict[ToastVariant, int] = {
    ToastVariant.SUCCESS: 3000,
    ToastVariant.INFO: 3500,
    ToastVariant.WARNING: 4500,
    ToastVariant.ERROR: 6000,
    ToastVariant.LOADING: 0,
}

_UNSET = object()

_SHADOW_MARGIN = 8
_EDGE_OFFSET = 12
_STACK_SPACING = 2
_DEDUPE_WINDOW_S = 0.8


def coerce_variant(value: ToastVariant | str) -> ToastVariant:
    """Normalise a variant, accepting the legacy ``"warn"`` spelling."""
    if isinstance(value, ToastVariant):
        return value
    try:
        return _VARIANT_ALIASES[str(value).strip().lower()]
    except KeyError as exc:
        raise ValueError(f"Unknown toast variant: {value!r}") from exc


def coerce_position(value: ToastPosition | str) -> ToastPosition:
    if isinstance(value, ToastPosition):
        return value
    try:
        return _POSITION_ALIASES[str(value).strip().lower()]
    except KeyError as exc:
        raise ValueError(f"Unknown toast position: {value!r}") from exc


@dataclass(frozen=True)
class ToastOptions:
    """Complete configuration surface for one toast.

    ``None`` means "inherit the global default" for appearance fields and
    "variant default" for ``duration``. ``duration=0`` makes a toast persist
    until dismissed, which is the loading default.
    """

    title: str | None = None
    duration: int | None = None
    icon: str | QIcon | None = None
    closable: bool = True
    dismiss_on_click: bool = False
    pause_on_hover: bool = True
    position: ToastPosition | str | None = None
    min_width: int = 300
    max_width: int = 440
    radius: int | None = None
    font_size: int | None = None
    icon_size: int | None = None
    background: str | None = None
    border: str | None = None
    text_color: str | None = None
    icon_color: str | None = None
    semantic_icons: bool = False
    elevation: int | None = 1
    show_progress: bool = False
    action: tuple[str, Callable[[], None]] | None = None
    dedupe: bool = True
    max_visible: int = 3


def _merge_options(
    base: ToastOptions, changes: dict | None = None
) -> ToastOptions:
    """Validate and merge per-call overrides onto ``base``."""
    if not changes:
        return base
    known = {field.name for field in fields(ToastOptions)}
    unknown = set(changes) - known
    if unknown:
        raise TypeError(f"Unknown toast option(s): {', '.join(sorted(unknown))}")
    updates = dict(changes)
    if updates.get("position") is not None:
        updates["position"] = coerce_position(updates["position"])
    return replace(base, **updates)


class Toast(QWidget):
    """One floating notification.

    Instances live inside a :class:`_ToastHost`; the host owns stacking and
    placement. ``dismissed`` fires once, immediately before deletion.
    """

    dismissed = pyqtSignal(object)

    def __init__(
        self,
        message: str,
        variant: ToastVariant | str = ToastVariant.INFO,
        options: ToastOptions | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._variant = coerce_variant(variant)
        self._options = options or ToastManager.defaults()
        self._message_text = message
        self._dismissing = False
        self._fade = 0.0
        self._angle = 0.0
        self._remaining_ms = 0
        self._deadline = 0.0
        self.created_at = time.monotonic()
        self.duration = self._resolve_duration(self._options.duration)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName(f"{self._variant.value.capitalize()} notification")

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)

        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(70)
        self._spin_timer.timeout.connect(self._advance_spinner)

        self._build_ui()
        self._apply_options()
        self._start_timer()
        self._fade_animation = QVariantAnimation(self)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_animation.valueChanged.connect(self._set_fade)

        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)
        ThemeManager.instance().accent_changed.connect(self._on_theme_changed)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(
            _SHADOW_MARGIN, _SHADOW_MARGIN, _SHADOW_MARGIN, _SHADOW_MARGIN
        )
        root.setSpacing(0)

        self._surface = QFrame(self)
        self._surface.setObjectName("ToastSurface")
        self._surface.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root.addWidget(self._surface)

        surface_layout = QVBoxLayout(self._surface)
        surface_layout.setContentsMargins(0, 0, 0, 0)
        surface_layout.setSpacing(0)

        self._body = QWidget(self._surface)
        self._body.setObjectName("ToastBody")
        body = QHBoxLayout(self._body)
        body.setContentsMargins(16, 12, 12, 12)
        body.setSpacing(12)

        self._icon_label = QLabel(self._body)
        self._icon_label.setObjectName("ToastIcon")
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self._text_box = QWidget(self._body)
        self._text_box.setObjectName("ToastText")
        text_layout = QVBoxLayout(self._text_box)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self._title_label = QLabel(self._text_box)
        self._title_label.setObjectName("ToastTitle")
        self._title_label.setWordWrap(True)
        self._title_label.hide()
        text_layout.addWidget(self._title_label)

        self._message_label = QLabel(self._text_box)
        self._message_label.setObjectName("ToastMessage")
        self._message_label.setWordWrap(True)
        text_layout.addWidget(self._message_label)
        body.addWidget(self._text_box, 1)

        self._action_button = Button(
            "",
            ButtonVariant.LINK,
            ButtonSize.XS,
            on_click=self._run_action,
            parent=self._body,
        )
        self._action_button.hide()
        body.addWidget(self._action_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self._close_button = Button(
            variant=ButtonVariant.GHOST,
            size=ButtonSize.XS,
            icon="fa5s.times",
            icon_position="only",
            icon_size=13,
            tooltip="Dismiss notification",
            on_click=self.dismiss,
            parent=self._body,
        )
        self._close_button.setAccessibleName("Dismiss notification")
        body.addWidget(self._close_button, 0, Qt.AlignmentFlag.AlignVCenter)

        surface_layout.addWidget(self._body)

        self._progress_area = QWidget(self._surface)
        self._progress_area.setObjectName("ToastProgressArea")
        progress_layout = QHBoxLayout(self._progress_area)
        progress_layout.setContentsMargins(14, 0, 14, 9)
        progress_layout.setSpacing(0)
        self._progress = QProgressBar(self._progress_area)
        self._progress.setObjectName("ToastProgress")
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(2)
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)
        progress_layout.addWidget(self._progress)
        self._progress_area.hide()
        surface_layout.addWidget(self._progress_area)

        self._opacity = QGraphicsOpacityEffect(self._surface)
        self._opacity.setOpacity(0.0)
        self._surface.setGraphicsEffect(self._opacity)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    @property
    def variant(self) -> ToastVariant:
        return self._variant

    @property
    def message(self) -> str:
        return self._message_text

    @property
    def is_dismissing(self) -> bool:
        return self._dismissing

    @property
    def is_loading(self) -> bool:
        return self._variant is ToastVariant.LOADING

    @property
    def is_counting_down(self) -> bool:
        """True while an auto-dismiss timer is running (paused on hover)."""
        return self._timer.isActive()

    @property
    def options(self) -> ToastOptions:
        return self._options

    def _resolve_duration(self, duration: int | None) -> int:
        if duration is None:
            return _VARIANT_DURATIONS[self._variant]
        return max(0, int(duration))

    def _apply_options(self) -> None:
        options = self._options
        self._font_size = options.font_size or 13
        self._icon_size = options.icon_size or 20
        self._radius = options.radius or 16
        self.setAccessibleName(
            f"{self._variant.value.capitalize()} notification: {self._message_text}"
        )

        self._surface.setStyleSheet(
            Styles.get_toast_qss(
                background=options.background,
                border=options.border,
                text_color=options.text_color,
                radius=self._radius,
            )
        )

        title_font = QFont(self._title_label.font())
        title_font.setPixelSize(self._font_size)
        title_font.setWeight(QFont.Weight.DemiBold)
        self._title_label.setFont(title_font)

        message_font = QFont(self._message_label.font())
        message_font.setPixelSize(self._font_size)
        message_font.setWeight(QFont.Weight.Normal)
        self._message_label.setFont(message_font)

        self._icon_label.setFixedSize(self._icon_size, self._icon_size)
        self._title_label.setText(options.title or "")
        self._title_label.setVisible(bool(options.title))
        self._message_label.setText(self._message_text)
        self._close_button.setVisible(options.closable)
        self._configure_action()
        self._progress_area.setVisible(
            options.show_progress or not self._progress_area.isHidden()
        )
        self._refresh_icon()
        self._apply_width()

    def _configure_action(self) -> None:
        action = self._options.action
        if not action:
            self._action_button.hide()
            return
        label, _callback = action
        self._action_button.setText(label)
        self._action_button.show()

    def _run_action(self) -> None:
        action = self._options.action
        if action is not None:
            action[1]()

    def _refresh_icon(self) -> None:
        options = self._options
        color = options.icon_color or Styles.get_toast_icon_color(
            self._variant.value, semantic=options.semantic_icons
        )
        icon = options.icon
        if isinstance(icon, QIcon):
            rendered = icon
        elif isinstance(icon, str) and qta is not None:
            try:
                rendered = qta.icon(icon, color=color)
            except Exception:  # pragma: no cover - invalid icon name
                rendered = toast_icon(
                    self._variant.value, color, self._icon_size, self._angle
                )
        else:
            rendered = toast_icon(
                self._variant.value, color, self._icon_size, self._angle
            )
        self._icon_label.setPixmap(
            rendered.pixmap(QSize(self._icon_size, self._icon_size))
        )

    def _apply_width(self) -> None:
        options = self._options
        self._message_label.ensurePolished()
        text_width = self._message_label.fontMetrics().horizontalAdvance(
            self._message_text
        )
        if options.title:
            self._title_label.ensurePolished()
            text_width = max(
                text_width,
                self._title_label.fontMetrics().horizontalAdvance(options.title),
            )
        # A few pixels of slack keep the label from wrapping on a one-line
        # message because the layout rounds its spacing down.
        text_width += 6

        chrome = 16 + self._icon_size + 12 + 12  # padding, icon, two gaps
        if options.closable:
            chrome += 22 + 12
        if options.action:
            chrome += self._action_button.sizeHint().width() + 12

        width = max(options.min_width, text_width + chrome)
        self.setFixedWidth(min(options.max_width, width) + 2 * _SHADOW_MARGIN)

    def set_progress(self, value: float | None) -> None:
        """Show a hairline progress bar; ``None`` hides it, negative is busy."""
        if value is None:
            self._progress_area.hide()
            return
        self._progress_area.show()
        if value < 0:
            self._progress.setRange(0, 0)
            return
        self._progress.setRange(0, 1000)
        self._progress.setValue(int(max(0.0, min(1.0, float(value))) * 1000))

    def update_state(
        self,
        message: str | None = None,
        variant: ToastVariant | str | None = None,
        *,
        title: str | None | object = _UNSET,
        duration: int | None | object = _UNSET,
        progress: float | None | object = _UNSET,
        **option_changes,
    ) -> None:
        """Morph this toast in place (used for loading → result transitions)."""
        if self._dismissing:
            return

        if variant is not None:
            self._variant = coerce_variant(variant)

        if title is not _UNSET:
            option_changes["title"] = title
        if duration is not _UNSET:
            option_changes["duration"] = duration
        elif variant is not None:
            # A variant change must pick up that variant's default duration.
            option_changes["duration"] = None

        if option_changes:
            self._options = _merge_options(self._options, option_changes)

        if message is not None:
            self._message_text = message
            self.setAccessibleName(
                f"{self._variant.value.capitalize()} notification: {message}"
            )

        self.duration = self._resolve_duration(self._options.duration)
        self._apply_options()
        self._sync_loading_animation()
        self._start_timer()

        if progress is not _UNSET:
            self.set_progress(progress)
        elif self._options.show_progress:
            self._progress_area.show()

    # ------------------------------------------------------------------
    # Lifetime
    # ------------------------------------------------------------------
    def showEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        self._fade_in()
        self._sync_loading_animation()

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._spin_timer.stop()
        super().hideEvent(event)

    def _sync_loading_animation(self) -> None:
        if self.is_loading and self.isVisible():
            if not self._spin_timer.isActive():
                self._spin_timer.start()
        else:
            self._spin_timer.stop()
            if not self.is_loading:
                self._angle = 0.0

    def _advance_spinner(self) -> None:
        self._angle = (self._angle + 20) % 360
        self._refresh_icon()

    def _fade_in(self) -> None:
        self._fade_animation.stop()
        self._fade_animation.setDuration(170)
        self._fade_animation.setStartValue(self._fade)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.start()

    def _set_fade(self, value) -> None:
        self._fade = float(value)
        self._opacity.setOpacity(self._fade)
        self.update()

    def _start_timer(self) -> None:
        self._timer.stop()
        self._remaining_ms = self.duration
        if self.duration > 0:
            self._deadline = time.monotonic() + self.duration / 1000
            self._timer.start(self.duration)

    def restart_timer(self) -> None:
        """Restart the countdown (used when deduping repeated messages)."""
        self.created_at = time.monotonic()
        self._start_timer()

    def _pause_timer(self) -> None:
        if not self._timer.isActive():
            return
        self._timer.stop()
        self._remaining_ms = max(
            0, int((self._deadline - time.monotonic()) * 1000)
        )

    def _resume_timer(self) -> None:
        if self._dismissing or self.duration <= 0 or self._timer.isActive():
            return
        remaining = max(1, self._remaining_ms)
        self._deadline = time.monotonic() + remaining / 1000
        self._timer.start(remaining)

    def _on_timeout(self) -> None:
        self.dismiss()

    def dismiss(self, immediate: bool = False) -> None:
        if self._dismissing:
            return
        self._dismissing = True
        self._timer.stop()
        self._spin_timer.stop()
        self._fade_animation.stop()

        if immediate:
            self.dismissed.emit(self)
            self.deleteLater()
            return

        animation = QVariantAnimation(self)
        animation.setDuration(180)
        animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        animation.setStartValue(self._fade)
        animation.setEndValue(0.0)
        animation.valueChanged.connect(self._set_fade)
        animation.finished.connect(self._finish_dismiss)
        # Keep a reference so the animation is not collected mid-flight.
        self._dismiss_animation = animation
        animation.start()

    def _finish_dismiss(self) -> None:
        self.dismissed.emit(self)
        self.deleteLater()

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def enterEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().enterEvent(event)
        if self._options.pause_on_hover:
            self._pause_timer()

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().leaveEvent(event)
        if not self._options.pause_on_hover:
            return
        # Moving onto a child fires the parent's leave event; keep the timer
        # paused while the cursor is still inside the toast.
        if self.rect().contains(self.mapFromGlobal(QCursor.pos())):
            return
        self._resume_timer()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self._options.dismiss_on_click:
            self.dismiss()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.key() == Qt.Key.Key_Escape:
            self.dismiss()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        # A soft painted shadow keeps the fade (surface opacity effect) and the
        # depth cue in one widget without stacking two graphics effects.
        if not self._options.elevation or self._fade <= 0:
            return
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(Qt.PenStyle.NoPen)
            geometry = self._surface.geometry()
            layers = 5
            for step in range(layers, 0, -1):
                alpha = int(9 * self._fade * (layers - step + 1) / layers)
                if alpha <= 0:
                    continue
                painter.setBrush(QColor(0, 0, 0, alpha))
                spread = step * 2
                painter.drawRoundedRect(
                    geometry.adjusted(-spread, -spread + 3, spread, spread + 3),
                    self._radius + spread,
                    self._radius + spread,
                )
        finally:
            painter.end()

    def _on_theme_changed(self, *_args) -> None:
        self._apply_options()


class ToastHandle:
    """Mutable handle returned by :class:`ToastManager`."""

    def __init__(self, toast: Toast | None) -> None:
        self._toast = toast
        if toast is not None:
            toast.dismissed.connect(self._on_dismissed)

    def _on_dismissed(self, *_args) -> None:
        self._toast = None

    @property
    def active(self) -> bool:
        return self._toast is not None

    @property
    def toast(self) -> Toast | None:
        return self._toast

    def update(
        self,
        message: str | None = None,
        variant: ToastVariant | str | None = None,
        **kwargs,
    ) -> ToastHandle:
        if self._toast is not None:
            try:
                self._toast.update_state(message, variant, **kwargs)
            except RuntimeError:  # pragma: no cover - Qt deleted mid-update
                self._toast = None
        return self

    def set_progress(self, value: float | None) -> ToastHandle:
        if self._toast is not None:
            try:
                self._toast.set_progress(value)
            except RuntimeError:  # pragma: no cover
                self._toast = None
        return self

    def dismiss(self, immediate: bool = False) -> None:
        if self._toast is not None:
            try:
                self._toast.dismiss(immediate)
            except RuntimeError:  # pragma: no cover
                self._toast = None

    def __bool__(self) -> bool:
        return self.active


class _ToastHost(QWidget):
    """Transparent, content-sized stack anchored to one corner of a window."""

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window
        self._toasts: list[Toast] = []
        self._position = ToastPosition.TOP_RIGHT
        self._max_visible = 3
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(_STACK_SPACING)
        window.installEventFilter(self)
        self.hide()

    # ------------------------------------------------------------------
    # Stack management
    # ------------------------------------------------------------------
    @property
    def toasts(self) -> list[Toast]:
        return list(self._toasts)

    def add(self, toast: Toast, position: ToastPosition, max_visible: int) -> None:
        self._position = position
        self._max_visible = max(1, max_visible)
        self._toasts.append(toast)
        if position in _TOP_POSITIONS:
            self._layout.insertWidget(0, toast)
        else:
            self._layout.addWidget(toast)
        toast.dismissed.connect(self._on_dismissed)
        toast.show()

        while len(self._toasts) > self._max_visible:
            self._toasts[0].dismiss(immediate=True)

        self._reposition()

    def find_duplicate(
        self, message: str, variant: ToastVariant
    ) -> Toast | None:
        now = time.monotonic()
        for toast in reversed(self._toasts):
            if (
                not toast.is_dismissing
                and toast.message == message
                and toast.variant is variant
                and now - toast.created_at <= _DEDUPE_WINDOW_S
            ):
                return toast
        return None

    def clear(self, immediate: bool = True) -> None:
        for toast in list(self._toasts):
            toast.dismiss(immediate=immediate)

    def _on_dismissed(self, toast: Toast) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
        self._layout.removeWidget(toast)
        toast.setParent(None)
        if self._toasts:
            self._reposition()
        else:
            self.hide()

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------
    def eventFilter(self, obj, event):  # noqa: N802 - Qt override
        if obj is self._window and event.type() in (
            event.Type.Resize,
            event.Type.Show,
        ):
            self._reposition()
        return super().eventFilter(obj, event)

    def _reposition(self) -> None:
        if not self._toasts:
            self.hide()
            return

        self._layout.activate()
        self.resize(self._layout.sizeHint())

        width = self._window.width()
        height = self._window.height()
        x = _EDGE_OFFSET
        if self._position in (ToastPosition.TOP_RIGHT, ToastPosition.BOTTOM_RIGHT):
            x = max(_EDGE_OFFSET, width - self.width() - _EDGE_OFFSET)
        elif self._position in (
            ToastPosition.TOP_CENTER,
            ToastPosition.BOTTOM_CENTER,
        ):
            x = max(_EDGE_OFFSET, (width - self.width()) // 2)

        if self._position in _TOP_POSITIONS:
            y = _EDGE_OFFSET
        else:
            y = max(_EDGE_OFFSET, height - self.height() - _EDGE_OFFSET)

        self.move(x, y)
        self.show()
        self.raise_()
        for toast in self._toasts:
            toast.raise_()


class ToastManager:
    """The app's only toast entry point.

    Hosts are cached per top-level window so toasts follow dialogs and page
    navigation, and stack instead of overlapping. All methods are classmethods
    because toasts are global UI, not view state.
    """

    _defaults = ToastOptions(position=ToastPosition.TOP_RIGHT)
    _hosts: dict[int, tuple[weakref.ref, _ToastHost]] = {}

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    @classmethod
    def defaults(cls) -> ToastOptions:
        return cls._defaults

    @classmethod
    def configure(cls, **changes) -> ToastOptions:
        """Update global defaults (position, widths, durations, ...)."""
        cls._defaults = _merge_options(cls._defaults, changes)
        return cls._defaults

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @classmethod
    def show(
        cls,
        widget: QWidget,
        message: str,
        variant: ToastVariant | str = ToastVariant.INFO,
        **options,
    ) -> ToastHandle:
        resolved_variant = coerce_variant(variant)
        opts = _merge_options(cls._defaults, options)
        window = cls._resolve_window(widget)
        if window is None:
            return ToastHandle(None)

        host = cls._host_for(window)
        position = coerce_position(opts.position or ToastPosition.TOP_RIGHT)

        if opts.dedupe:
            duplicate = host.find_duplicate(message, resolved_variant)
            if duplicate is not None:
                duplicate.restart_timer()
                return ToastHandle(duplicate)

        toast = Toast(message, resolved_variant, opts, host)
        handle = ToastHandle(toast)
        if opts.show_progress:
            toast.set_progress(0.0)
        host.add(toast, position, opts.max_visible)
        return handle

    @classmethod
    def success(cls, widget: QWidget, message: str, **options) -> ToastHandle:
        return cls.show(widget, message, ToastVariant.SUCCESS, **options)

    @classmethod
    def warning(cls, widget: QWidget, message: str, **options) -> ToastHandle:
        return cls.show(widget, message, ToastVariant.WARNING, **options)

    @classmethod
    def info(cls, widget: QWidget, message: str, **options) -> ToastHandle:
        return cls.show(widget, message, ToastVariant.INFO, **options)

    @classmethod
    def error(cls, widget: QWidget, message: str, **options) -> ToastHandle:
        return cls.show(widget, message, ToastVariant.ERROR, **options)

    @classmethod
    def loading(cls, widget: QWidget, message: str, **options) -> ToastHandle:
        return cls.show(widget, message, ToastVariant.LOADING, **options)

    @classmethod
    def active_toasts(cls, widget: QWidget) -> list[Toast]:
        """Toasts currently stacked on ``widget``'s window (tests/diagnostics)."""
        window = cls._resolve_window(widget)
        if window is None:
            return []
        host = cls._existing_host(window)
        return host.toasts if host is not None else []

    @classmethod
    def clear(cls, widget: QWidget | None = None, *, immediate: bool = True) -> None:
        if widget is not None:
            window = cls._resolve_window(widget)
            host = cls._existing_host(window) if window is not None else None
            if host is not None:
                host.clear(immediate=immediate)
            return
        for _ref, host in list(cls._hosts.values()):
            try:
                host.clear(immediate=immediate)
            except RuntimeError:  # pragma: no cover - host already deleted
                pass

    # ------------------------------------------------------------------
    # Host plumbing
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_window(widget: QWidget | None) -> QWidget | None:
        if not isinstance(widget, QWidget):
            return None
        try:
            return widget.window()
        except RuntimeError:  # pragma: no cover - deleted widget
            return None

    @classmethod
    def _existing_host(cls, window: QWidget) -> _ToastHost | None:
        entry = cls._hosts.get(id(window))
        if entry is not None:
            ref, host = entry
            if ref() is window:
                return host
        return None

    @classmethod
    def _host_for(cls, window: QWidget) -> _ToastHost:
        key = id(window)

        def _cleanup(_ref, *, host_key: int = key) -> None:
            cls._hosts.pop(host_key, None)

        existing = cls._hosts.get(key)
        if existing is not None:
            ref, host = existing
            if ref() is window:
                try:
                    host.objectName()
                    return host
                except RuntimeError:  # pragma: no cover - host deleted
                    pass

        host = _ToastHost(window)
        cls._hosts[key] = (weakref.ref(window, _cleanup), host)
        return host

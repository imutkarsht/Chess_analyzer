# SPDX-License-Identifier: GPL-3.0-only
"""One tooltip surface for the whole application.

Native ``QToolTip`` chrome cannot express the caret, inverted surface, shadow,
or fade-and-zoom language used by the rest of the interface. This module owns
one reusable popup plus a manager that renders every tooltip through it.

The manager consumes Qt's normal ``QEvent.ToolTip`` flow, so existing
``setToolTip(...)`` call sites keep working while copy is migrated area by
area. Call sites that need semantic copy use :func:`attach_tooltip` with one of
the :class:`Tooltip` factories.

Keyboard focus, item-view ``ToolTipRole`` data, tab-bar tooltips, menu actions,
disabled controls, screen-edge clamping, and multi-monitor placement are
handled here rather than in individual widgets.
"""

from __future__ import annotations

import re
import weakref
from dataclasses import dataclass
from enum import StrEnum

from PyQt6 import sip
from PyQt6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    Qt,
    QTimer,
)
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QFocusEvent,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QHelpEvent,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QGraphicsOpacityEffect,
    QMenu,
    QTabBar,
    QWidget,
)

from src.gui.theme import Motion, MotionDuration, MotionEasing, ThemeManager
from src.gui.theme.tokens import Radius
from src.utils.logger import logger

MAX_TEXT_WIDTH_PX = 320
MAX_TEXT_CHARS = 160

_TOOLTIP_FONT_SIZE = 12
_PADDING_X = 12
_PADDING_Y = 8
_RADIUS = Radius.MD
_CARET_WIDTH = 10
_CARET_HEIGHT = 5
_ANCHOR_GAP = 6
_SHADOW_MARGIN = 14
_SHADOW_LAYERS = 9
_SCREEN_MARGIN = 4

_FOCUS_DELAY_MS = 500
_HIDE_GRACE_MS = 100
_SAFETY_MS = 9000

_KEYBOARD_FOCUS_REASONS = frozenset(
    {
        Qt.FocusReason.TabFocusReason,
        Qt.FocusReason.BacktabFocusReason,
        Qt.FocusReason.ShortcutFocusReason,
    }
)

_LEAD_INS = (
    "click to ",
    "click here to ",
    "press here to ",
    "this button ",
)
_WHITESPACE = re.compile(r"[ \t]+")
_PAWN_MOVE = re.compile(r"^[a-h](?:x?[a-h]?[1-8])?\b")


class TooltipKind(StrEnum):
    """Copy intent, not a visual variant.

    Every kind shares the shadcn-style inverted bubble; the distinction keeps
    copy rules and call-site intent explicit.
    """

    ACTION = "action"
    NAVIGATION = "navigation"
    STATE = "state"
    SHORTCUT = "shortcut"
    EXPLANATION = "explanation"
    DISABLED = "disabled"


def _normalise_text(text: str) -> str:
    lines: list[str] = []
    for raw_line in str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = _WHITESPACE.sub(" ", raw_line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _strip_lead_in(text: str) -> tuple[str, bool]:
    folded = text.casefold()
    for prefix in _LEAD_INS:
        if folded.startswith(prefix):
            return text[len(prefix) :].lstrip(), True
    return text, False


def _sentence_case(text: str) -> str:
    if not text or not text[0].islower():
        return text
    # Never capitalise algebraic notation: "e4 is best" must stay "e4 is best".
    if _PAWN_MOVE.match(text):
        return text
    return text[0].upper() + text[1:]


def _trim_terminal_period(text: str) -> str:
    while text.endswith(".") and not text.endswith("..."):
        text = text[:-1].rstrip()
    return text


def _warn_if_long(text: str) -> None:
    if len(text) > MAX_TEXT_CHARS:
        logger.warning(
            "Tooltip copy is %s characters (max %s): %r",
            len(text),
            MAX_TEXT_CHARS,
            text,
        )


def format_shortcut(shortcut: str) -> str:
    """Render a shortcut using the platform's native notation."""
    value = str(shortcut).strip()
    if not value:
        return ""
    native = QKeySequence(value).toString(QKeySequence.SequenceFormat.NativeText)
    return native or value


def _append_shortcut(text: str, shortcut: str | None) -> str:
    if not shortcut:
        return text
    rendered = format_shortcut(shortcut)
    if not rendered:
        return text
    return f"{text} ({rendered})" if text else rendered


def format_action(text: str) -> str:
    """Normalise verb-first action copy: no lead-in, no terminal period."""
    text = _normalise_text(text)
    text, stripped_lead_in = _strip_lead_in(text)
    if stripped_lead_in:
        text = _sentence_case(text)
    text = _trim_terminal_period(text.replace("\n", " · "))
    _warn_if_long(text)
    return text


def format_navigation(text: str) -> str:
    """Navigation copy uses the same voice as actions."""
    return format_action(text)


def format_explanation(text: str) -> str:
    """Normalise a short explanation; line breaks are preserved."""
    text = _normalise_text(text)
    text, stripped_lead_in = _strip_lead_in(text)
    if stripped_lead_in:
        text = _sentence_case(text)
    text = _trim_terminal_period(text)
    _warn_if_long(text)
    return text


def format_state(text: str) -> str:
    """State copy reads as a compact factual line, not a sentence."""
    text = _trim_terminal_period(_normalise_text(text))
    _warn_if_long(text)
    return text


def format_disabled(text: str) -> str:
    """A disabled reason states the precondition, never ``Disabled``."""
    text = _normalise_text(text)
    text, _ = _strip_lead_in(text)
    text = _trim_terminal_period(text)
    _warn_if_long(text)
    return text


_FORMATTERS = {
    TooltipKind.ACTION: format_action,
    TooltipKind.NAVIGATION: format_navigation,
    TooltipKind.STATE: format_state,
    TooltipKind.SHORTCUT: format_action,
    TooltipKind.EXPLANATION: format_explanation,
    TooltipKind.DISABLED: format_disabled,
}


class Tooltip:
    """A tooltip payload attached to a widget.

    The text is validated at construction time. Dynamic state tooltips can be
    refreshed with :meth:`set_text`; :meth:`clear` turns the payload into a
    no-op without detaching the widget.
    """

    __slots__ = ("kind", "shortcut", "text")

    def __init__(
        self,
        text: str = "",
        kind: TooltipKind | str = TooltipKind.ACTION,
        shortcut: str | None = None,
    ) -> None:
        self.kind = TooltipKind(kind)
        self.text = str(text)
        self.shortcut = str(shortcut).strip() if shortcut else None

    @classmethod
    def for_action(cls, text: str, shortcut: str | None = None) -> Tooltip:
        return cls(format_action(text), TooltipKind.ACTION, shortcut)

    @classmethod
    def for_navigation(cls, text: str, shortcut: str | None = None) -> Tooltip:
        return cls(format_navigation(text), TooltipKind.NAVIGATION, shortcut)

    @classmethod
    def for_state(cls, text: str) -> Tooltip:
        return cls(format_state(text), TooltipKind.STATE)

    @classmethod
    def for_shortcut(cls, text: str, shortcut: str) -> Tooltip:
        return cls(format_action(text), TooltipKind.SHORTCUT, shortcut)

    @classmethod
    def for_explanation(cls, text: str, shortcut: str | None = None) -> Tooltip:
        return cls(format_explanation(text), TooltipKind.EXPLANATION, shortcut)

    @classmethod
    def for_disabled(cls, reason: str) -> Tooltip:
        return cls(format_disabled(reason), TooltipKind.DISABLED)

    def set_text(self, text: str) -> Tooltip:
        self.text = _FORMATTERS[self.kind](str(text))
        return self

    def clear(self) -> Tooltip:
        self.text = ""
        self.shortcut = None
        return self

    def display_text(self) -> str:
        return _append_shortcut(self.text, self.shortcut)

    def __bool__(self) -> bool:
        return bool(self.display_text())

    def __repr__(self) -> str:
        return (
            f"Tooltip(kind={self.kind.value!r}, text={self.text!r}, "
            f"shortcut={self.shortcut!r})"
        )


_ATTACHED: weakref.WeakKeyDictionary[QWidget, Tooltip] = weakref.WeakKeyDictionary()


def attach_tooltip(widget: QWidget, tooltip: Tooltip | str) -> Tooltip:
    """Attach a semantic payload to ``widget`` and mirror it into Qt.

    Mirroring into ``QWidget.setToolTip`` is what makes Qt emit the normal
    ``QEvent.ToolTip`` event; the manager replaces the native popup when it is
    installed.
    """
    if not isinstance(tooltip, Tooltip):
        tooltip = Tooltip(str(tooltip))
    _ATTACHED[widget] = tooltip
    widget.setToolTip(tooltip.display_text())
    return tooltip


def detach_tooltip(widget: QWidget) -> None:
    _ATTACHED.pop(widget, None)
    widget.setToolTip("")


def tooltip_for(widget: QWidget) -> Tooltip | None:
    return _ATTACHED.get(widget)


@dataclass(frozen=True)
class _ResolvedTooltip:
    widget: QWidget
    anchor: QRect
    tooltip: Tooltip


def _global_rect(widget: QWidget) -> QRect:
    # ``Button.size`` is a component property, so use ``rect()`` rather than
    # the shadowed ``QWidget.size()`` method.
    return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.rect().size())


def _cursor_position() -> QPoint:
    """Seam for tests that need to simulate leaving a target."""
    return QCursor.pos()


def _clamp(value: int, low: int, high: int) -> int:
    if high < low:
        return low
    return max(low, min(value, high))


class TooltipManager(QObject):
    """Application-wide tooltip driver.

    Install once after ``QApplication`` exists. The manager intercepts
    ``ToolTip`` events, resolves the right copy (widget, item view, tab, menu,
    or disabled child), suppresses Qt's native popup, and drives one shared
    :class:`_TooltipPopup`.
    """

    _instance: TooltipManager | None = None

    def __init__(self, app: QApplication | None = None) -> None:
        super().__init__(app)
        self._app = app or QApplication.instance()
        if self._app is None:
            raise RuntimeError("TooltipManager requires a QApplication")
        self._installed = False
        self._owner: QWidget | None = None
        self._anchor = QRect()
        self._focus_candidate: QWidget | None = None

        self._popup = _TooltipPopup()

        self._focus_timer = QTimer(self)
        self._focus_timer.setSingleShot(True)
        self._focus_timer.setInterval(_FOCUS_DELAY_MS)
        self._focus_timer.timeout.connect(self._show_focused)

        self._grace_timer = QTimer(self)
        self._grace_timer.setSingleShot(True)
        self._grace_timer.setInterval(_HIDE_GRACE_MS)
        self._grace_timer.timeout.connect(self._hide_after_leave)

        self._safety_timer = QTimer(self)
        self._safety_timer.setSingleShot(True)
        self._safety_timer.setInterval(_SAFETY_MS)
        self._safety_timer.timeout.connect(self._hide_now)

        theme_manager = ThemeManager.instance()
        theme_manager.theme_changed.connect(self._on_theme_changed)
        theme_manager.accent_changed.connect(self._on_theme_changed)

    @classmethod
    def instance(cls, app: QApplication | None = None) -> TooltipManager:
        if cls._instance is None:
            cls._instance = cls(app)
        return cls._instance

    @property
    def popup(self) -> _TooltipPopup:
        return self._popup

    @property
    def is_installed(self) -> bool:
        return self._installed

    def install(self) -> TooltipManager:
        if not self._installed:
            self._app.installEventFilter(self)
            self._installed = True
        return self

    def shutdown(self) -> None:
        if self._installed:
            self._app.removeEventFilter(self)
            self._installed = False
        theme_manager = ThemeManager.instance()
        for signal in (theme_manager.theme_changed, theme_manager.accent_changed):
            try:
                signal.disconnect(self._on_theme_changed)
            except TypeError:
                pass
        self._hide_now()
        self._popup.deleteLater()
        if TooltipManager._instance is self:
            TooltipManager._instance = None

    def show_for(
        self,
        widget: QWidget,
        tooltip: Tooltip | str,
        *,
        side: str | None = None,
        animate: bool = True,
    ) -> None:
        """Show a tooltip immediately; used by the preview and by tests."""
        if not isinstance(tooltip, Tooltip):
            tooltip = Tooltip(str(tooltip))
        self._show(
            _ResolvedTooltip(widget, _global_rect(widget), tooltip),
            side=side,
            animate=animate,
        )

    def hide(self) -> None:
        self._hide_now()

    # ------------------------------------------------------------------
    # Event routing
    # ------------------------------------------------------------------
    def eventFilter(self, obj, event) -> bool:
        if not self._installed or not isinstance(obj, QWidget):
            return False
        if obj is self._popup or self._popup.isAncestorOf(obj):
            return False

        event_type = event.type()
        if event_type == QEvent.Type.ToolTip:
            if not isinstance(event, QHelpEvent):
                return False
            resolved = self._resolve(obj, event.globalPos())
            if resolved is None:
                return False
            self._show(resolved)
            return True

        if event_type == QEvent.Type.Leave:
            owner = self._owner
            if owner is not None and (
                obj is owner
                or owner.isAncestorOf(obj)
                or obj.isAncestorOf(owner)
            ):
                # Leave can arrive before the platform cursor position has
                # settled, so re-check just before hiding instead of trusting
                # QCursor.pos() here.
                self._schedule_hide()
            return False

        if event_type == QEvent.Type.Enter:
            owner = self._owner
            if owner is not None:
                if obj is owner or owner.isAncestorOf(obj):
                    self._grace_timer.stop()
                else:
                    # Entering any other widget — sibling, parent, or unrelated
                    # surface — means the pointer left the owner even if the
                    # corresponding Leave was coalesced away.
                    self._schedule_hide()
            return False

        if event_type == QEvent.Type.MouseMove:
            if self._owner is not None:
                if self._cursor_inside_anchor():
                    self._grace_timer.stop()
                else:
                    self._schedule_hide()
            return False

        if event_type in (QEvent.Type.MouseButtonPress, QEvent.Type.Wheel):
            self._hide_now()
            return False

        if event_type == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self._hide_now()
            return False

        if event_type in (
            QEvent.Type.WindowDeactivate,
            QEvent.Type.ApplicationDeactivate,
        ):
            self._hide_now()
            return False

        if event_type == QEvent.Type.FocusIn:
            if isinstance(event, QFocusEvent) and event.reason() in _KEYBOARD_FOCUS_REASONS:
                self._focus_candidate = obj
                self._focus_timer.start()
            return False

        if event_type == QEvent.Type.FocusOut:
            if obj is self._focus_candidate:
                self._focus_candidate = None
                self._focus_timer.stop()
            if obj is self._owner:
                self._hide_now()
            return False

        if event_type == QEvent.Type.Hide and obj is self._owner:
            self._hide_now()
        return False

    def _show(
        self,
        resolved: _ResolvedTooltip,
        *,
        side: str | None = None,
        animate: bool = True,
    ) -> None:
        if not resolved.tooltip:
            return
        self._focus_timer.stop()
        self._grace_timer.stop()
        self._owner = resolved.widget
        self._anchor = resolved.anchor
        self._popup.show_for(
            resolved.anchor,
            resolved.tooltip,
            side=side,
            animate=animate,
        )
        self._safety_timer.start()

    def _schedule_hide(self) -> None:
        # Do not push the deadline forward on every mouse-move event; once the
        # pointer is outside the anchor, the grace period should expire even
        # while the user keeps moving.
        if self._owner is not None and not self._grace_timer.isActive():
            self._grace_timer.start()

    def _hide_after_leave(self) -> None:
        if self._owner is not None and not self._cursor_inside_anchor():
            self._hide_now()

    def _hide_now(self) -> None:
        self._focus_timer.stop()
        self._grace_timer.stop()
        self._safety_timer.stop()
        self._owner = None
        self._focus_candidate = None
        self._popup.hide_animated()

    def _show_focused(self) -> None:
        candidate = self._focus_candidate
        if candidate is None or not candidate.hasFocus():
            return
        resolved = self._resolve(candidate, candidate.mapToGlobal(candidate.rect().center()))
        if resolved is not None:
            self._show(resolved)

    def _cursor_inside_anchor(self) -> bool:
        return not self._anchor.isNull() and self._anchor.contains(_cursor_position())

    def _on_theme_changed(self, *_args) -> None:
        self._hide_now()

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------
    def _resolve(self, obj: QWidget, global_pos: QPoint) -> _ResolvedTooltip | None:
        attached = _ATTACHED.get(obj)
        if attached is not None:
            anchor_widget = obj
            if attached.kind is TooltipKind.DISABLED:
                disabled = self._disabled_child_under(obj, global_pos)
                if disabled is not None:
                    anchor_widget = disabled
            return _ResolvedTooltip(anchor_widget, _global_rect(anchor_widget), attached)

        parent = obj.parentWidget()
        if parent is not None:
            parent_tooltip = _ATTACHED.get(parent)
            if parent_tooltip is not None and parent_tooltip.kind is TooltipKind.DISABLED:
                return _ResolvedTooltip(obj, _global_rect(obj), parent_tooltip)

        item_view = self._item_view_for(obj)
        if item_view is not None:
            resolved = self._resolve_item_view(item_view, global_pos)
            if resolved is not None:
                return resolved

        if isinstance(obj, QTabBar):
            resolved = self._resolve_tab_bar(obj, global_pos)
            if resolved is not None:
                return resolved

        if isinstance(obj, QMenu):
            resolved = self._resolve_menu(obj, global_pos)
            if resolved is not None:
                return resolved

        text = obj.toolTip()
        if text:
            return _ResolvedTooltip(obj, _global_rect(obj), Tooltip(text))
        return None

    def _disabled_child_under(
        self, container: QWidget, global_pos: QPoint
    ) -> QWidget | None:
        child = container.childAt(container.mapFromGlobal(global_pos))
        while child is not None and child is not container:
            if child.isVisible() and not child.isEnabled():
                return child
            child = child.childAt(child.mapFromGlobal(global_pos))
        return None

    @staticmethod
    def _item_view_for(obj: QWidget) -> QAbstractItemView | None:
        if isinstance(obj, QAbstractItemView):
            view = obj
        else:
            parent = obj.parentWidget()
            if isinstance(parent, QAbstractItemView) and obj is parent.viewport():
                view = parent
            else:
                return None
        # Qt creates the popup views of combo boxes and other internal
        # controls in C++. PyQt refuses protected calls such as indexAt() on
        # those wrappers, so resolve only views the application created.
        if not sip.ispycreated(view):
            return None
        return view

    @staticmethod
    def _resolve_item_view(
        view: QAbstractItemView, global_pos: QPoint
    ) -> _ResolvedTooltip | None:
        model = view.model()
        if model is None:
            return None
        position = view.viewport().mapFromGlobal(global_pos)
        index = view.indexAt(position)
        if not index.isValid():
            return None
        value = model.data(index, Qt.ItemDataRole.ToolTipRole)
        if not value:
            return None
        rect = view.visualRect(index)
        anchor = QRect(view.viewport().mapToGlobal(rect.topLeft()), rect.size())
        return _ResolvedTooltip(
            view.viewport(),
            anchor,
            Tooltip(str(value)),
        )

    @staticmethod
    def _resolve_tab_bar(tab_bar: QTabBar, global_pos: QPoint) -> _ResolvedTooltip | None:
        index = tab_bar.tabAt(tab_bar.mapFromGlobal(global_pos))
        if index < 0:
            return None
        text = tab_bar.tabToolTip(index)
        if not text:
            return None
        rect = tab_bar.tabRect(index)
        anchor = QRect(tab_bar.mapToGlobal(rect.topLeft()), rect.size())
        return _ResolvedTooltip(tab_bar, anchor, Tooltip(text, TooltipKind.NAVIGATION))

    @staticmethod
    def _resolve_menu(menu: QMenu, global_pos: QPoint) -> _ResolvedTooltip | None:
        action = menu.actionAt(menu.mapFromGlobal(global_pos))
        if action is None:
            return None
        text = action.toolTip() or action.text()
        if not text:
            return None
        rect = menu.actionGeometry(action)
        anchor = QRect(menu.mapToGlobal(rect.topLeft()), rect.size())
        return _ResolvedTooltip(menu, anchor, Tooltip(text, TooltipKind.NAVIGATION))


class _TooltipSurface(QWidget):
    """Transparent child that paints the bubble and owns the fade effect."""

    def __init__(self, popup: _TooltipPopup) -> None:
        super().__init__(popup)
        self._popup = popup
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAutoFillBackground(False)

    def paintEvent(self, event) -> None:
        self._popup.paint_surface(self)


class _TooltipPopup(QWidget):
    """Frameless, click-through tooltip window with a painted caret."""

    def __init__(self) -> None:
        flags = (
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._surface = _TooltipSurface(self)
        self._opacity = QGraphicsOpacityEffect(self._surface)
        self._opacity.setOpacity(1.0)
        self._surface.setGraphicsEffect(self._opacity)

        self._text = ""
        self._kind = TooltipKind.ACTION
        self._font = QFont()
        self._side = "top"
        self._arrow_offset = 0
        self._bubble_rect = QRect()
        self._text_rect = QRect()
        self._origin = QPoint()
        self._hide_token = 0

    # ------------------------------------------------------------------
    # Public read-only state (tests and the preview harness)
    # ------------------------------------------------------------------
    @property
    def current_text(self) -> str:
        return self._text

    @property
    def current_kind(self) -> TooltipKind:
        return self._kind

    @property
    def current_side(self) -> str:
        return self._side

    @property
    def bubble_rect(self) -> QRect:
        return self._bubble_rect

    # ------------------------------------------------------------------
    # Presentation
    # ------------------------------------------------------------------
    def show_for(
        self,
        anchor: QRect,
        tooltip: Tooltip,
        *,
        side: str | None = None,
        animate: bool = True,
    ) -> None:
        text = tooltip.display_text()
        if not text:
            self.hide_animated()
            return

        self._hide_token += 1
        self._text = text
        self._kind = tooltip.kind
        self._font = QFont(QApplication.font())
        self._font.setPixelSize(_TOOLTIP_FONT_SIZE)
        self._font.setWeight(QFont.Weight.Normal)
        self.setFont(self._font)

        width, height, text_rect = self._measure(text)
        final, bubble, chosen_side, arrow, origin = self._geometry_for(
            anchor, width, height, side
        )
        self._side = chosen_side
        self._bubble_rect = bubble
        self._arrow_offset = arrow
        self._origin = origin
        self._text_rect = text_rect.translated(bubble.topLeft())

        self._opacity.setOpacity(1.0)
        self.setGeometry(final)
        self._surface.setGeometry(self.rect())
        self._surface.update()
        self.show()
        if QGuiApplication.platformName() != "offscreen":
            self.raise_()

        if animate and Motion.enabled():
            start = self._scaled_rect(final, origin, 0.96)
            self.setGeometry(start)
            self._surface.setGeometry(self.rect())
            self._opacity.setOpacity(0.0)
            Motion.animate(
                self,
                b"geometry",
                final,
                duration=MotionDuration.FAST,
                easing=MotionEasing.ENTER,
                start=start,
            )
            Motion.animate(
                self._opacity,
                b"opacity",
                1.0,
                duration=MotionDuration.FAST,
                easing=MotionEasing.ENTER,
                start=0.0,
            )
        else:
            self.setGeometry(final)
            self._surface.setGeometry(self.rect())
            self._opacity.setOpacity(1.0)

    def hide_animated(self) -> None:
        if not self.isVisible():
            return
        self._hide_token += 1
        token = self._hide_token
        Motion.stop(self, b"geometry")
        if not Motion.enabled():
            self.hide()
            return
        animation = Motion.animate(
            self._opacity,
            b"opacity",
            0.0,
            duration=MotionDuration.INSTANT,
            easing=MotionEasing.EXIT,
            start=self._opacity.opacity(),
        )
        if animation is None:
            self.hide()
        else:
            animation.finished.connect(lambda: self._finish_hide(token))

    def hide(self) -> None:
        Motion.stop(self, b"geometry")
        super().hide()

    def _finish_hide(self, token: int) -> None:
        if token == self._hide_token:
            self.hide()

    def resizeEvent(self, event) -> None:
        self._surface.setGeometry(self.rect())
        super().resizeEvent(event)

    def _measure(self, text: str) -> tuple[int, int, QRect]:
        metrics = QFontMetrics(self._font)
        bounds = metrics.boundingRect(
            QRect(0, 0, MAX_TEXT_WIDTH_PX, 10_000),
            Qt.TextFlag.TextWordWrap,
            text,
        )
        text_width = min(MAX_TEXT_WIDTH_PX, max(1, bounds.width()))
        text_height = max(metrics.height(), bounds.height())
        width = max(48, text_width + 2 * _PADDING_X)
        height = text_height + 2 * _PADDING_Y
        text_rect = QRect(
            _PADDING_X,
            _PADDING_Y,
            width - 2 * _PADDING_X,
            height - 2 * _PADDING_Y,
        )
        return width, height, text_rect

    def _choose_side(
        self, anchor: QRect, width: int, height: int, available: QRect
    ) -> str:
        need_v = height + _CARET_HEIGHT + _ANCHOR_GAP + _SHADOW_MARGIN
        need_h = width + _CARET_HEIGHT + _ANCHOR_GAP + _SHADOW_MARGIN
        spaces = {
            "top": anchor.top() - available.top(),
            "bottom": available.bottom() - anchor.bottom(),
            "left": anchor.left() - available.left(),
            "right": available.right() - anchor.right(),
        }
        if spaces["top"] >= need_v:
            return "top"
        if spaces["bottom"] >= need_v:
            return "bottom"
        if spaces["right"] >= need_h:
            return "right"
        if spaces["left"] >= need_h:
            return "left"
        return max(spaces, key=spaces.get)

    def _geometry_for(
        self,
        anchor: QRect,
        width: int,
        height: int,
        side: str | None,
    ) -> tuple[QRect, QRect, str, int, QPoint]:
        screen = QGuiApplication.screenAt(anchor.center()) or QGuiApplication.primaryScreen()
        available = (
            screen.availableGeometry()
            if screen is not None
            else QRect(0, 0, 1920, 1080)
        )
        if side not in {"top", "bottom", "left", "right"}:
            side = self._choose_side(anchor, width, height, available)

        if side in {"top", "bottom"}:
            window_width = width + 2 * _SHADOW_MARGIN
            window_height = height + 2 * _SHADOW_MARGIN + _CARET_HEIGHT
            bubble_x = anchor.center().x() - width // 2
            bubble_x = _clamp(
                bubble_x,
                available.left() + _SHADOW_MARGIN + _SCREEN_MARGIN,
                available.right()
                - width
                - _SHADOW_MARGIN
                - _SCREEN_MARGIN
                + 1,
            )
            if side == "top":
                bubble_y = anchor.top() - _ANCHOR_GAP - height
            else:
                bubble_y = anchor.bottom() + _ANCHOR_GAP
            bubble_y = _clamp(
                bubble_y,
                available.top() + _SHADOW_MARGIN + _SCREEN_MARGIN,
                available.bottom()
                - height
                - _SHADOW_MARGIN
                - _SCREEN_MARGIN
                + 1,
            )
            window_x = bubble_x - _SHADOW_MARGIN
            window_y = bubble_y - _SHADOW_MARGIN
            if side == "bottom":
                window_y -= _CARET_HEIGHT
        else:
            window_width = width + 2 * _SHADOW_MARGIN + _CARET_HEIGHT
            window_height = height + 2 * _SHADOW_MARGIN
            bubble_y = anchor.center().y() - height // 2
            bubble_y = _clamp(
                bubble_y,
                available.top() + _SHADOW_MARGIN + _SCREEN_MARGIN,
                available.bottom()
                - height
                - _SHADOW_MARGIN
                - _SCREEN_MARGIN
                + 1,
            )
            if side == "left":
                bubble_x = anchor.left() - _ANCHOR_GAP - width
            else:
                bubble_x = anchor.right() + _ANCHOR_GAP
            bubble_x = _clamp(
                bubble_x,
                available.left() + _SHADOW_MARGIN + _SCREEN_MARGIN,
                available.right()
                - width
                - _SHADOW_MARGIN
                - _SCREEN_MARGIN
                + 1,
            )
            window_x = bubble_x - _SHADOW_MARGIN
            window_y = bubble_y - _SHADOW_MARGIN
            if side == "right":
                window_x -= _CARET_HEIGHT

        window_x = _clamp(
            window_x,
            available.left() + _SCREEN_MARGIN,
            available.right() - window_width - _SCREEN_MARGIN + 1,
        )
        window_y = _clamp(
            window_y,
            available.top() + _SCREEN_MARGIN,
            available.bottom() - window_height - _SCREEN_MARGIN + 1,
        )
        window = QRect(window_x, window_y, window_width, window_height)

        bubble_local = QRect(
            _SHADOW_MARGIN + (_CARET_HEIGHT if side == "right" else 0),
            _SHADOW_MARGIN + (_CARET_HEIGHT if side == "bottom" else 0),
            width,
            height,
        )
        bubble_global_x = window_x + bubble_local.x()
        bubble_global_y = window_y + bubble_local.y()

        if side in {"top", "bottom"}:
            arrow = _clamp(
                anchor.center().x() - bubble_global_x,
                _RADIUS + _CARET_WIDTH // 2,
                width - _RADIUS - _CARET_WIDTH // 2,
            )
            origin_y = (
                bubble_global_y + height + _CARET_HEIGHT
                if side == "top"
                else bubble_global_y - _CARET_HEIGHT
            )
            origin = QPoint(bubble_global_x + arrow, origin_y)
        else:
            arrow = _clamp(
                anchor.center().y() - bubble_global_y,
                _RADIUS + _CARET_WIDTH // 2,
                height - _RADIUS - _CARET_WIDTH // 2,
            )
            origin_x = (
                bubble_global_x + width + _CARET_HEIGHT
                if side == "left"
                else bubble_global_x - _CARET_HEIGHT
            )
            origin = QPoint(origin_x, bubble_global_y + arrow)

        return window, bubble_local, side, arrow, origin

    @staticmethod
    def _scaled_rect(rect: QRect, origin: QPoint, scale: float) -> QRect:
        width = max(1, round(rect.width() * scale))
        height = max(1, round(rect.height() * scale))
        x = origin.x() + round((rect.x() - origin.x()) * scale)
        y = origin.y() + round((rect.y() - origin.y()) * scale)
        return QRect(x, y, width, height)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------
    def paint_surface(self, widget: QWidget) -> None:
        palette = ThemeManager.palette()
        painter = QPainter(widget)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        bubble = QRectF(self._bubble_rect)
        self._paint_shadow(painter, palette, bubble)

        bubble_path = QPainterPath()
        bubble_path.addRoundedRect(bubble, _RADIUS, _RADIUS)
        caret_path = QPainterPath()
        caret_path.addPolygon(QPolygonF(self._caret_points(bubble)))
        shape = bubble_path.united(caret_path)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(palette.tooltip_surface))
        painter.drawPath(shape)

        border = QColor(palette.tooltip_text)
        border.setAlphaF(0.10)
        pen = QPen(border)
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(shape)

        painter.setPen(QColor(palette.tooltip_text))
        painter.setFont(self._font)
        flags = (
            int(Qt.AlignmentFlag.AlignLeft)
            | int(Qt.AlignmentFlag.AlignVCenter)
            | int(Qt.TextFlag.TextWordWrap)
        )
        painter.drawText(self._text_rect, flags, self._text)
        painter.end()

    def _paint_shadow(
        self, painter: QPainter, palette: object, bubble: QRectF
    ) -> None:
        base = QColor(palette.tooltip_shadow)
        painter.setPen(Qt.PenStyle.NoPen)
        for layer in range(_SHADOW_LAYERS, 0, -1):
            alpha = palette.tooltip_shadow_alpha * (
                0.035 + 0.045 * (1.0 - layer / _SHADOW_LAYERS)
            )
            color = QColor(base)
            color.setAlphaF(max(0.0, min(1.0, alpha)))
            rect = bubble.adjusted(-layer, -layer + 2, layer, layer + 2)
            painter.setBrush(color)
            painter.drawRoundedRect(rect, _RADIUS + layer, _RADIUS + layer)

    def _caret_points(self, bubble: QRectF) -> list[QPointF]:
        half = _CARET_WIDTH / 2
        if self._side == "top":
            base_y = bubble.bottom() - 1.0
            tip_y = bubble.bottom() + _CARET_HEIGHT
            center_x = bubble.left() + self._arrow_offset
            return [
                QPointF(center_x - half, base_y),
                QPointF(center_x + half, base_y),
                QPointF(center_x, tip_y),
            ]
        if self._side == "bottom":
            base_y = bubble.top() + 1.0
            tip_y = bubble.top() - _CARET_HEIGHT
            center_x = bubble.left() + self._arrow_offset
            return [
                QPointF(center_x - half, base_y),
                QPointF(center_x + half, base_y),
                QPointF(center_x, tip_y),
            ]
        if self._side == "left":
            base_x = bubble.right() - 1.0
            tip_x = bubble.right() + _CARET_HEIGHT
            center_y = bubble.top() + self._arrow_offset
            return [
                QPointF(base_x, center_y - half),
                QPointF(base_x, center_y + half),
                QPointF(tip_x, center_y),
            ]
        base_x = bubble.left() + 1.0
        tip_x = bubble.left() - _CARET_HEIGHT
        center_y = bubble.top() + self._arrow_offset
        return [
            QPointF(base_x, center_y - half),
            QPointF(base_x, center_y + half),
            QPointF(tip_x, center_y),
        ]


__all__ = [
    "MAX_TEXT_CHARS",
    "MAX_TEXT_WIDTH_PX",
    "Tooltip",
    "TooltipKind",
    "TooltipManager",
    "attach_tooltip",
    "detach_tooltip",
    "format_action",
    "format_disabled",
    "format_explanation",
    "format_navigation",
    "format_shortcut",
    "format_state",
    "tooltip_for",
]

# SPDX-License-Identifier: GPL-3.0-only
"""Modal-stack controller for in-window overlay dialogs.

A child overlay is not OS-modal, so this manager supplies the behaviour a real
dialog gets for free: focus trapping, focus restoration, Escape handling,
shortcut suspension, backdrop policy, window activation and nested stacks.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QEventLoop, QObject, Qt, QTimer
from PyQt6.QtGui import QShortcut
from PyQt6.QtWidgets import QAbstractScrollArea, QApplication, QScrollBar, QWidget

from src.gui.components.feedback.overlay_card import OverlayCard, OverlayResult
from src.gui.components.feedback.overlay_host import OverlayHost, _CardLayer
from src.utils.logger import logger


@dataclass
class _OverlayEntry:
    card: OverlayCard
    layer: _CardLayer
    on_result: Callable[[OverlayResult], None] | None
    focus_before: QWidget | None


class OverlayManager(QObject):
    """One manager (and one host) per top-level window."""

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window
        self._host = OverlayHost(window)
        self._host.backdrop_clicked.connect(self._on_backdrop_clicked)
        self._stack: list[_OverlayEntry] = []
        self._loops: list[QEventLoop] = []
        self._suspended_shortcuts: list[tuple[QShortcut, bool]] = []
        self._filter_installed = False
        self._shutting_down = False

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    @classmethod
    def for_window(cls, widget: QWidget) -> OverlayManager:
        """Return the manager owned by ``widget``'s top-level window."""
        window = widget.window() if widget is not None else None
        if window is None:
            raise ValueError("OverlayManager requires a windowed widget")
        manager = getattr(window, "_overlay_manager", None)
        if manager is None or sip.isdeleted(manager):
            manager = cls(window)
            window._overlay_manager = manager
        return manager

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return bool(self._stack)

    @property
    def top_card(self) -> OverlayCard | None:
        return self._stack[-1].card if self._stack else None

    def create_card(self, **kwargs) -> OverlayCard:
        """Create an ``OverlayCard`` bound to this window's overlay host."""
        kwargs.setdefault("parent", self._host)
        return OverlayCard(**kwargs)

    def open(
        self,
        card: OverlayCard,
        *,
        on_result: Callable[[OverlayResult], None] | None = None,
    ) -> None:
        """Show ``card`` above the current overlay stack."""
        if self._shutting_down:
            return
        if card in [entry.card for entry in self._stack]:
            return

        popup = QApplication.activePopupWidget()
        if popup is not None:
            popup.close()

        from src.gui.components.feedback.tooltip import TooltipManager

        if TooltipManager._instance is not None:
            TooltipManager._instance.hide()

        focus_before = self._focus_widget()

        if not self._stack:
            self._suspend_shortcuts()
            self._install_filter()
            self._host.setGeometry(self._window.rect())

        layer = self._host.push_card(card)
        entry = _OverlayEntry(
            card=card,
            layer=layer,
            on_result=on_result,
            focus_before=focus_before,
        )
        self._stack.append(entry)

        card.result_requested.connect(
            lambda result, card=card: self._on_card_result(card, result)
        )
        card.close_requested.connect(
            lambda card=card: self._on_card_result(card, OverlayResult.REJECTED)
        )

        self._host.raise_()
        QTimer.singleShot(0, self._focus_top_card)

    def close_top(self, result: OverlayResult = OverlayResult.DISMISSED) -> None:
        if not self._stack:
            return
        self._finish_entry(self._stack[-1], result, notify=True)

    def set_blur_enabled(self, enabled: bool) -> None:
        """Toggle the background snapshot blur (scrim stays either way)."""
        self._host.set_blur_enabled(enabled)

    def open_blocking(self, card: OverlayCard) -> OverlayResult:
        """Synchronous migration bridge for legacy ``dialog.exec()`` callers."""
        if self._shutting_down:
            return OverlayResult.DISMISSED
        loop = QEventLoop(self)
        self._loops.append(loop)
        results: list[OverlayResult] = []

        def on_result(result: OverlayResult) -> None:
            results.append(result)
            if loop.isRunning():
                loop.quit()

        self.open(card, on_result=on_result)
        loop.exec()
        if loop in self._loops:
            self._loops.remove(loop)
        loop.deleteLater()
        return results[0] if results else OverlayResult.DISMISSED

    def shutdown(self) -> None:
        """Close everything without notifying panels (window teardown)."""
        if self._shutting_down:
            return
        self._shutting_down = True
        for entry in list(reversed(self._stack)):
            self._finish_entry(entry, OverlayResult.DISMISSED, notify=False)
        for loop in list(self._loops):
            if loop.isRunning():
                loop.quit()
        self._loops.clear()
        self._restore_shortcuts()
        self._remove_filter()
        self._host.hide()
        self._host.deleteLater()

    # ------------------------------------------------------------------
    # Stack lifecycle
    # ------------------------------------------------------------------

    def _on_card_result(self, card: OverlayCard, result: OverlayResult) -> None:
        for entry in self._stack:
            if entry.card is card:
                self._finish_entry(entry, result, notify=True)
                return

    def _finish_entry(
        self,
        entry: _OverlayEntry,
        result: OverlayResult,
        *,
        notify: bool,
    ) -> None:
        if entry not in self._stack:
            return
        is_top = self._stack[-1] is entry
        self._stack.remove(entry)

        self._host.pop_layer(
            entry.layer,
            animate=not self._shutting_down,
            on_finished=None,
        )

        try:
            entry.card.run_cleanup()
        except Exception:
            logger.error("Overlay cleanup callback failed", exc_info=True)

        restore_target = self._restore_target_for(entry)
        if (is_top or not self._stack) and restore_target is not None:
            restore_target.setFocus(Qt.FocusReason.PopupFocusReason)

        if not self._stack:
            self._restore_shortcuts()
            self._remove_filter()

        if notify and entry.on_result is not None:
            try:
                entry.on_result(result)
            except Exception:
                logger.error("Overlay result callback failed", exc_info=True)

    def _restore_target_for(self, entry: _OverlayEntry) -> QWidget | None:
        candidate = entry.focus_before
        if candidate is not None and (
            sip.isdeleted(candidate) or not candidate.isVisible()
        ):
            candidate = None

        top = self.top_card
        if top is not None:
            if candidate is not None and (
                candidate is top or top.isAncestorOf(candidate)
            ):
                return candidate
            return top

        if candidate is not None and candidate.window() is self._window:
            return candidate
        central = getattr(self._window, "centralWidget", None)
        if callable(central):
            widget = central()
            if widget is not None:
                return widget
        return self._window

    # ------------------------------------------------------------------
    # Focus trap
    # ------------------------------------------------------------------

    def _focus_widget(self) -> QWidget | None:
        focus = QApplication.focusWidget()
        if focus is not None and focus.window() is self._window:
            return focus
        return self._window.focusWidget()

    def _focus_top_card(self) -> None:
        card = self.top_card
        if card is None or not card.isVisible():
            return
        target = card.initial_focus
        if target is not None and target is not card and not self._inside_card(card, target):
            target = card
        target.setFocus(Qt.FocusReason.PopupFocusReason)
        self._ensure_visible(target)

    def _focusables(self, card: OverlayCard) -> list[QWidget]:
        found: list[QWidget] = []
        for widget in card.findChildren(QWidget):
            if isinstance(widget, QScrollBar) or widget.focusProxy() is not None:
                continue
            if not widget.isVisibleTo(card) or not widget.isEnabled():
                continue
            policy = widget.focusPolicy()
            if policy == Qt.FocusPolicy.NoFocus:
                continue
            if policy & (
                Qt.FocusPolicy.TabFocus
                | Qt.FocusPolicy.ClickFocus
                | Qt.FocusPolicy.StrongFocus
                | Qt.FocusPolicy.WheelFocus
            ):
                found.append(widget)
        return found

    def _move_focus(self, *, backwards: bool) -> None:
        card = self.top_card
        if card is None:
            return
        targets = self._focusables(card)
        if not targets:
            card.setFocus(Qt.FocusReason.PopupFocusReason)
            return

        focus = self._focus_widget()
        if focus not in targets:
            index = len(targets) - 1 if backwards else 0
        else:
            step = -1 if backwards else 1
            index = (targets.index(focus) + step) % len(targets)

        target = targets[index]
        target.setFocus(Qt.FocusReason.PopupFocusReason)
        self._ensure_visible(target)

    @staticmethod
    def _inside_card(card: OverlayCard, widget: QWidget) -> bool:
        return widget is card or card.isAncestorOf(widget)

    @staticmethod
    def _ensure_visible(widget: QWidget) -> None:
        parent = widget.parentWidget()
        while parent is not None:
            if isinstance(parent, QAbstractScrollArea):
                parent.ensureWidgetVisible(widget, 8, 8)
                return
            parent = parent.parentWidget()

    # ------------------------------------------------------------------
    # Event filtering
    # ------------------------------------------------------------------

    def _install_filter(self) -> None:
        app = QApplication.instance()
        if app is not None and not self._filter_installed:
            app.installEventFilter(self)
            self._filter_installed = True

    def _remove_filter(self) -> None:
        app = QApplication.instance()
        if app is not None and self._filter_installed:
            app.removeEventFilter(self)
            self._filter_installed = False

    def eventFilter(self, obj, event):
        if not self._stack:
            return False
        event_type = event.type()

        if event_type in (
            QEvent.Type.ApplicationActivate,
            QEvent.Type.WindowActivate,
        ):
            if obj is self._window or event_type == QEvent.Type.ApplicationActivate:
                QTimer.singleShot(0, self._focus_if_outside)
            return False

        if not isinstance(obj, QWidget) or obj.window() is not self._window:
            return False

        if event_type == QEvent.Type.ShortcutOverride:
            event.accept()
            return True

        if event_type == QEvent.Type.KeyPress:
            if QApplication.activePopupWidget() is not None:
                return False
            if event.key() == Qt.Key.Key_Escape:
                card = self.top_card
                if card is not None and card.dismiss_on_escape:
                    self.close_top(OverlayResult.DISMISSED)
                    return True
            elif event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                backwards = event.key() == Qt.Key.Key_Backtab or bool(
                    event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                )
                self._move_focus(backwards=backwards)
                return True

        if event_type == QEvent.Type.FocusIn:
            if QApplication.activePopupWidget() is not None:
                return False
            focus = self._focus_widget()
            card = self.top_card
            if (
                focus is not None
                and card is not None
                and focus.window() is self._window
                and not self._inside_card(card, focus)
            ):
                QTimer.singleShot(0, self._focus_if_outside)
        return False

    def _focus_if_outside(self) -> None:
        card = self.top_card
        if card is None:
            return
        focus = self._focus_widget()
        if focus is None or not self._inside_card(card, focus):
            self._focus_top_card()

    # ------------------------------------------------------------------
    # Backdrop
    # ------------------------------------------------------------------

    def _on_backdrop_clicked(self) -> None:
        card = self.top_card
        if card is not None and card.dismiss_on_backdrop:
            self.close_top(OverlayResult.DISMISSED)

    # ------------------------------------------------------------------
    # Shortcut suspension
    # ------------------------------------------------------------------

    def _suspend_shortcuts(self) -> None:
        manager = getattr(self._window, "shortcut_manager", None)
        managed: set[QShortcut] = set()
        if manager is not None and hasattr(manager, "set_suspended"):
            owned = getattr(manager, "owned_shortcuts", None)
            if callable(owned):
                managed = set(owned())
            manager.set_suspended(True)

        self._suspended_shortcuts = []
        for shortcut in self._window.findChildren(QShortcut):
            if shortcut in managed:
                continue
            self._suspended_shortcuts.append((shortcut, shortcut.isEnabled()))
            shortcut.setEnabled(False)

    def _restore_shortcuts(self) -> None:
        manager = getattr(self._window, "shortcut_manager", None)
        if manager is not None and hasattr(manager, "set_suspended"):
            manager.set_suspended(False)

        for shortcut, was_enabled in self._suspended_shortcuts:
            if not sip.isdeleted(shortcut):
                shortcut.setEnabled(was_enabled)
        self._suspended_shortcuts = []

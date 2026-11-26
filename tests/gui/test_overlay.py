# SPDX-License-Identifier: GPL-3.0-only
"""Behaviour of the shared in-window overlay dialog system."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from src.gui.components import (
    Button,
    ButtonVariant,
    Input,
    Label,
    OverlayCard,
    OverlayManager,
    OverlayResult,
)
from src.gui.theme import ThemeManager
from src.gui.utils.shortcut_manager import ShortcutManager


@pytest.fixture
def overlay_window(qtbot, qapp):
    window = QMainWindow()
    central = QWidget()
    layout = QVBoxLayout(central)
    trigger = Button("Open", ButtonVariant.FILLED)
    layout.addWidget(trigger)
    layout.addWidget(Label("Background content"))
    window.setCentralWidget(central)
    window.resize(1000, 700)
    window.show()
    qtbot.addWidget(window)
    qapp.processEvents()

    manager = OverlayManager.for_window(window)
    yield window, manager, trigger

    manager.shutdown()
    window.close()


def make_card(*, title="Dialog", actions=True, **kwargs) -> OverlayCard:
    card = OverlayCard(title=title, description="Supporting copy.", **kwargs)
    body = QWidget()
    layout = QVBoxLayout(body)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(Label("Dialog body"))
    layout.addWidget(Input(placeholder="Type here"))
    card.set_content(body)
    if actions:
        card.add_action(Button("Cancel", ButtonVariant.OUTLINED, on_click=card.reject))
        card.add_action(Button("Continue", ButtonVariant.PRIMARY, on_click=card.accept), primary=True)
    return card


def test_open_covers_window_and_focuses_card(qapp, overlay_window):
    window, manager, _trigger = overlay_window
    card = make_card()

    manager.open(card)
    qapp.processEvents()

    assert manager.is_open is True
    assert manager.top_card is card
    assert card.isVisible()
    assert manager._host.isVisible()
    assert manager._host.geometry() == window.rect()
    assert window.focusWidget() is card

    # The host sits above the background across the whole window.
    corner = window.centralWidget().mapTo(window, QPoint(4, 4))
    assert window.childAt(corner) is manager._host


def test_close_restores_focus_to_trigger(qapp, overlay_window):
    window, manager, trigger = overlay_window
    trigger.setFocus()
    qapp.processEvents()
    assert window.focusWidget() is trigger

    card = make_card()
    manager.open(card)
    qapp.processEvents()
    assert window.focusWidget() is card

    card.reject()
    qapp.processEvents()

    assert manager.is_open is False
    assert window.focusWidget() is trigger


def test_escape_closes_non_destructive_card(qapp, overlay_window):
    _window, manager, _trigger = overlay_window
    card = make_card()
    result: list[OverlayResult] = []
    manager.open(card, on_result=result.append)
    qapp.processEvents()

    QTest.keyClick(card, Qt.Key.Key_Escape)
    qapp.processEvents()

    assert manager.is_open is False
    assert result == [OverlayResult.DISMISSED]


def test_backdrop_click_closes_information_card(qapp, overlay_window):
    _window, manager, _trigger = overlay_window
    card = make_card()
    manager.open(card)
    qapp.processEvents()

    QTest.mouseClick(
        manager._host,
        Qt.MouseButton.LeftButton,
        pos=QPoint(4, 4),
    )
    qapp.processEvents()

    assert manager.is_open is False


def test_backdrop_click_never_confirms_destructive_card(qapp, overlay_window):
    _window, manager, _trigger = overlay_window
    card = make_card(destructive=True, dismiss_on_backdrop=False)
    accepted: list[OverlayResult] = []
    manager.open(card, on_result=accepted.append)
    qapp.processEvents()

    QTest.mouseClick(
        manager._host,
        Qt.MouseButton.LeftButton,
        pos=QPoint(4, 4),
    )
    qapp.processEvents()

    assert manager.is_open is True
    assert accepted == []


def test_tab_focus_stays_inside_card(qapp, overlay_window):
    window, manager, _trigger = overlay_window
    card = make_card()
    manager.open(card)
    qapp.processEvents()

    focusables = manager._focusables(card)
    assert focusables

    for _ in range(len(focusables) + 3):
        QTest.keyClick(card, Qt.Key.Key_Tab)
        qapp.processEvents()
        focus = window.focusWidget()
        assert focus is card or card.isAncestorOf(focus)

    QTest.keyClick(card, Qt.Key.Key_Backtab)
    qapp.processEvents()
    focus = window.focusWidget()
    assert focus is card or card.isAncestorOf(focus)


def test_nested_overlay_restores_previous_card_and_focus(qapp, overlay_window):
    window, manager, _trigger = overlay_window
    first = make_card(title="First")
    manager.open(first)
    qapp.processEvents()

    opener = first.findChildren(Button)[-1]
    opener.setFocus()
    qapp.processEvents()

    second = make_card(title="Second")
    manager.open(second)
    qapp.processEvents()
    assert manager.top_card is second
    assert first.isVisible() is False

    second.reject()
    qapp.processEvents()

    assert manager.top_card is first
    assert first.isVisible() is True
    assert window.focusWidget() is opener


def test_resize_keeps_card_inside_window(qapp, overlay_window):
    window, manager, _trigger = overlay_window
    card = make_card(max_width=720)
    manager.open(card)
    qapp.processEvents()

    window.resize(620, 480)
    qapp.processEvents()

    host_rect = manager._host.rect()
    card_topleft = card.mapTo(manager._host, QPoint(0, 0))
    assert host_rect.contains(card_topleft)
    assert card.width() <= host_rect.width()
    assert card.width() <= card.max_width
    assert manager._host.geometry() == window.rect()


def test_window_shortcuts_are_suspended_while_open(qapp, overlay_window):
    window, manager, _trigger = overlay_window
    shortcut_manager = ShortcutManager(window)
    window.shortcut_manager = shortcut_manager
    fired: list[bool] = []
    shortcut_manager.register("test", "Test action", "F", lambda: fired.append(True))

    card = make_card()
    manager.open(card)
    qapp.processEvents()

    shortcut = shortcut_manager.owned_shortcuts()[0]
    assert shortcut_manager.suspended is True
    assert shortcut.isEnabled() is False

    # Focusing a text field inside the card must not re-enable bindings.
    text = card.findChildren(Input)[0]
    text.setFocus()
    qapp.processEvents()
    assert shortcut.isEnabled() is False

    card.reject()
    qapp.processEvents()
    assert shortcut_manager.suspended is False
    assert shortcut.isEnabled() is True


def test_plain_window_shortcut_is_restored(qapp, overlay_window):
    window, manager, _trigger = overlay_window
    shortcut = QShortcut(QKeySequence("J"), window)
    card = make_card()
    manager.open(card)
    qapp.processEvents()

    assert shortcut.isEnabled() is False

    card.reject()
    qapp.processEvents()
    assert shortcut.isEnabled() is True


def test_blocking_bridge_returns_result(qapp, overlay_window):
    _window, manager, _trigger = overlay_window
    card = make_card()
    QTimer.singleShot(0, card.accept)

    result = manager.open_blocking(card)
    qapp.processEvents()

    assert result is OverlayResult.ACCEPTED
    assert manager.is_open is False


def test_blur_snapshot_is_cached_and_can_fall_back(qapp, overlay_window, mocker):
    window, manager, _trigger = overlay_window
    host = manager._host
    host.set_blur_enabled(True)
    card = make_card()
    manager.open(card)
    qapp.processEvents()

    dpr = window.devicePixelRatioF()
    assert host._background is not None
    assert host._background.width() == round(window.centralWidget().width() * dpr)
    assert host._background.height() == round(window.centralWidget().height() * dpr)

    card.reject()
    qapp.processEvents()

    mocker.patch.object(host, "_blur_pixmap", side_effect=RuntimeError("no blur"))
    second = make_card(title="Fallback")
    manager.open(second)
    qapp.processEvents()

    assert manager.is_open is True
    assert host._background is None


def test_theme_change_while_open_keeps_card_alive(qapp, overlay_window):
    window, manager, _trigger = overlay_window
    previous_mode = ThemeManager.mode()
    card = make_card()
    manager.open(card)
    qapp.processEvents()

    try:
        ThemeManager.set_mode("light" if previous_mode != "light" else "dark")
        qapp.processEvents()
        assert manager.is_open is True
        assert card.isVisible()
        assert window.centralWidget() is not None
    finally:
        ThemeManager.set_mode(previous_mode)
        qapp.processEvents()

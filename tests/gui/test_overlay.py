# SPDX-License-Identifier: GPL-3.0-only
"""Behaviour of the shared in-window overlay dialog system."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, QObject, QPoint, Qt, QTimer
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


def test_header_only_card_hides_body_scroll(qapp, overlay_window):
    _window, manager, _trigger = overlay_window
    card = OverlayCard(title="Confirm", description="Proceed?")
    card.add_action(Button("Cancel", ButtonVariant.HOLLOW, on_click=card.reject))
    card.add_action(Button("OK", ButtonVariant.PRIMARY, on_click=card.accept), primary=True)

    manager.open(card)
    qapp.processEvents()

    assert card.body_scroll.isHidden() is True
    assert card.preferred_height() < 200


def test_cleanup_runs_on_shutdown(qapp, overlay_window):
    _window, manager, _trigger = overlay_window
    cleaned: list[bool] = []
    card = make_card()
    card.add_cleanup(lambda: cleaned.append(True))

    manager.open(card)
    qapp.processEvents()
    manager.shutdown()

    assert cleaned == [True]


def test_confirm_dialog_opens_in_window_overlay(qapp, overlay_window):
    window, manager, trigger = overlay_window
    trigger.setFocus()
    qapp.processEvents()

    from src.gui.components import confirm_dialog

    observed: dict[str, object] = {}

    def accept_overlay():
        card = manager.top_card
        try:
            observed["card"] = card
            observed["destructive"] = card.destructive if card else None
            observed["backdrop"] = card.dismiss_on_backdrop if card else None
            focus = window.focusWidget()
            observed["focus_text"] = focus.text() if focus is not None else None
        finally:
            if card is not None:
                card.accept()

    # Run on the tick after OverlayManager.open's singleShot(0, _focus_top_card).
    QTimer.singleShot(0, lambda: QTimer.singleShot(0, accept_overlay))
    assert confirm_dialog(trigger, "Delete item?", "Cannot be undone.", confirm_label="Delete") is True
    assert observed["card"] is not None
    assert observed["destructive"] is True
    assert observed["backdrop"] is False
    # Safe focus starts on Cancel for destructive confirmations.
    assert observed["focus_text"] == "Cancel"
    assert manager.is_open is False


def test_migrated_dialogs_open_as_overlays(qapp, overlay_window):
    from types import SimpleNamespace

    from src.gui.dialogs import (
        EngineNotFoundPanel,
        FeedbackPanel,
        LoadGamePanel,
        ReviewPromptPanel,
        ShortcutHelpPanel,
        UpdateNotificationPanel,
        open_engine_not_found,
        open_feedback_overlay,
        open_llm_not_configured,
        open_load_game_overlay,
        open_review_prompt,
        open_shortcut_help_overlay,
        open_update_overlay,
    )

    _window, manager, trigger = overlay_window

    # 1. ShortcutHelp
    open_shortcut_help_overlay(trigger, bindings=[])
    qapp.processEvents()
    assert isinstance(manager.top_card.content, ShortcutHelpPanel)
    manager.close_top()
    qapp.processEvents()

    # 2. Feedback (must not embed duplicate FeedbackHeader)
    open_feedback_overlay(trigger, initial_tab="feature")
    qapp.processEvents()
    assert isinstance(manager.top_card.content, FeedbackPanel)
    assert manager.top_card.findChild(QWidget, "FeedbackHeader") is None
    manager.close_top()
    qapp.processEvents()

    # 3. ReviewPrompt
    open_review_prompt(trigger, games_count=5)
    qapp.processEvents()
    assert isinstance(manager.top_card.content, ReviewPromptPanel)
    manager.close_top()
    qapp.processEvents()

    # 4. UpdateNotification
    fake_update = SimpleNamespace(
        current="2.5.0",
        latest="2.6.0",
        changelog="- Added overlays",
        html_url="https://example.com",
        download_url="",
        install_hint="",
    )
    open_update_overlay(fake_update, trigger)
    qapp.processEvents()
    assert isinstance(manager.top_card.content, UpdateNotificationPanel)
    manager.close_top()
    qapp.processEvents()

    # 5. LoadGame
    received_batches: list[object] = []
    open_load_game_overlay(trigger, on_batch=received_batches.append)
    qapp.processEvents()
    panel = manager.top_card.content
    assert isinstance(panel, LoadGamePanel)
    sentinel = object()
    panel.batch_ready.emit(sentinel)
    qapp.processEvents()
    assert received_batches == [sentinel]
    assert manager.is_open is False

    # 6. LlmNotConfigured (blocking bridge)
    def accept_llm():
        if manager.top_card is not None:
            manager.top_card.accept()

    QTimer.singleShot(0, lambda: QTimer.singleShot(0, accept_llm))
    assert open_llm_not_configured(trigger) is True
    qapp.processEvents()

    # 7. EngineNotFound (blocking bridge)
    seen_engine_panel: list[bool] = []

    def pick_engine():
        card = manager.top_card
        try:
            seen_engine_panel.append(
                card is not None and isinstance(card.content, EngineNotFoundPanel)
            )
        finally:
            if card is not None:
                card.reject()

    QTimer.singleShot(0, lambda: QTimer.singleShot(0, pick_engine))
    assert open_engine_not_found(trigger) is None
    assert seen_engine_panel == [True]
    qapp.processEvents()


def test_clicking_non_interactive_card_areas_does_not_close(qapp, overlay_window):
    _window, manager, _trigger = overlay_window
    card = make_card(title="Stay Open")
    manager.open(card)
    qapp.processEvents()

    # Clicking non-interactive labels, header, body, or padding inside the card
    # must never bubble up to OverlayHost's backdrop click handler.
    for target in (card.title_label, card.description_label, card.header, card.body, card):
        center = target.rect().center()
        QTest.mouseClick(target, Qt.MouseButton.LeftButton, pos=center)
        qapp.processEvents()
        assert manager.is_open is True

    # Clicking outside the card on the dimmed scrim still dismisses it.
    QTest.mouseClick(manager._host, Qt.MouseButton.LeftButton, pos=QPoint(4, 4))
    qapp.processEvents()
    assert manager.is_open is False


def test_create_card_is_parented_to_host_and_hidden(qapp, overlay_window):
    window, manager, _trigger = overlay_window
    card = manager.create_card(title="Parented", description="Never top-level")

    assert card.parent() is manager._host
    assert card.window() is window
    assert card.isVisible() is False

    # Mutating visibility before open must keep card parented and hidden.
    body = Label("Inside", parent=card)
    card.set_content(body)
    card.add_action(Button("OK", ButtonVariant.PRIMARY, on_click=card.accept), primary=True)
    assert card.window() is window
    assert card.isVisible() is False


def test_overlay_card_construction_never_shows_top_level_children(qapp, overlay_window):
    window, manager, _trigger = overlay_window
    top_level_shows: list[tuple[str, str]] = []

    class TopLevelShowSpy(QObject):
        def eventFilter(self, obj, event):
            if (
                event.type() == QEvent.Type.Show
                and getattr(obj, "isWindow", lambda: False)()
                and obj is not window
            ):
                top_level_shows.append((type(obj).__name__, obj.objectName()))
            return False

    spy = TopLevelShowSpy()
    qapp.installEventFilter(spy)
    try:
        # Both unparented OverlayCard and host-parented create_card with show_close=True
        # must keep close_button parented to header before setVisible(True) runs.
        standalone = OverlayCard(title="Standalone", description="Check close button", show_close=True)
        hosted = manager.create_card(title="Hosted", description="Check close button", show_close=True)
        qapp.processEvents()

        assert standalone.close_button.parentWidget() is standalone.header
        assert hosted.close_button.parentWidget() is hosted.header
        assert standalone.close_button.isWindow() is False
        assert hosted.close_button.isWindow() is False
        assert top_level_shows == []
    finally:
        qapp.removeEventFilter(spy)

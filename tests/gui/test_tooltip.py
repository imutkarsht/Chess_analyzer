# SPDX-License-Identifier: GPL-3.0-only
"""Behavioural tests for the shared tooltip surface and manager."""

from PyQt6.QtCore import QEvent, QPoint, QRect, Qt
from PyQt6.QtGui import QGuiApplication, QHelpEvent
from PyQt6.QtWidgets import (
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

import src.gui.components.feedback.tooltip as tooltip_module
from src.gui.components import (
    Tooltip,
    TooltipKind,
    TooltipManager,
    attach_tooltip,
    detach_tooltip,
    format_action,
    format_shortcut,
    tooltip_for,
)
from src.gui.theme.palette import DARK, LIGHT


def test_action_copy_normalises_lead_ins_and_periods():
    tooltip = Tooltip.for_action("click to reanalyze game.", shortcut="F5")

    assert tooltip.kind is TooltipKind.ACTION
    assert tooltip.text == "Reanalyze game"
    assert tooltip.display_text() == f"Reanalyze game ({format_shortcut('F5')})"


def test_explanation_copy_keeps_move_notation_but_fixes_sentence_case():
    tooltip = Tooltip.for_explanation("Click to open the analysis board.")
    assert tooltip.text == "Open the analysis board"

    move_note = Tooltip.for_explanation("e4 is best because it controls d5.")
    assert move_note.text == "e4 is best because it controls d5"


def test_state_and_disabled_copy_have_no_terminal_period():
    state = Tooltip.for_state("Stockfish 17 · depth 22.")
    disabled = Tooltip.for_disabled("Analyze the game before exporting PGN.")

    assert state.text == "Stockfish 17 · depth 22"
    assert disabled.kind is TooltipKind.DISABLED
    assert disabled.text == "Analyze the game before exporting PGN"


def test_set_text_uses_the_payload_formatter():
    tooltip = Tooltip.for_action("Reanalyze game")
    tooltip.set_text("click to stop analysis.")

    assert tooltip.text == "Stop analysis"


def test_attach_and_detach_mirror_the_text_into_qt(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)

    payload = attach_tooltip(widget, Tooltip.for_action("Delete game"))
    assert tooltip_for(widget) is payload
    assert widget.toolTip() == "Delete game"

    detach_tooltip(widget)
    assert tooltip_for(widget) is None
    assert widget.toolTip() == ""


def test_format_action_keeps_short_chess_notation():
    assert format_action("e4 is best") == "e4 is best"
    assert format_action("exd5 wins material") == "exd5 wins material"


def test_theme_palette_inverts_the_tooltip_surface():
    assert DARK.tooltip_surface == DARK.text_primary
    assert DARK.tooltip_text != DARK.tooltip_surface
    assert LIGHT.tooltip_surface == LIGHT.text_primary
    assert LIGHT.tooltip_text != LIGHT.tooltip_surface


def test_manager_uses_the_custom_popup_for_plain_tooltips(qtbot, qapp):
    window = QWidget()
    qtbot.addWidget(window)
    window.resize(600, 400)
    window.show()
    qapp.processEvents()

    target = QWidget(window)
    target.setGeometry(40, 40, 140, 32)
    target.setToolTip("Legacy tooltip")
    target.show()

    manager = TooltipManager.instance(qapp).install()
    try:
        event = QHelpEvent(
            QEvent.Type.ToolTip,
            target.rect().center(),
            target.mapToGlobal(target.rect().center()),
        )
        qapp.sendEvent(target, event)

        assert manager.popup.isVisible()
        assert manager.popup.current_text == "Legacy tooltip"

        manager.hide()
        assert manager.popup.isVisible() is False
    finally:
        manager.shutdown()


def test_manager_resolves_item_view_tooltip_roles(qtbot, qapp):
    window = QWidget()
    qtbot.addWidget(window)
    window.resize(600, 400)
    window.show()

    table = QTableWidget(1, 1, window)
    table.setGeometry(20, 20, 300, 160)
    item = QTableWidgetItem("e4")
    item.setToolTip("Played e4 · Best")
    table.setItem(0, 0, item)
    table.show()
    qapp.processEvents()

    manager = TooltipManager.instance(qapp).install()
    try:
        position = table.visualItemRect(item).center()
        global_position = table.viewport().mapToGlobal(position)
        event = QHelpEvent(
            QEvent.Type.ToolTip,
            table.viewport().mapFromGlobal(global_position),
            global_position,
        )
        qapp.sendEvent(table.viewport(), event)

        assert manager.popup.isVisible()
        assert manager.popup.current_text == "Played e4 · Best"
    finally:
        manager.shutdown()


def test_disabled_child_uses_the_container_reason(qtbot, qapp):
    window = QWidget()
    qtbot.addWidget(window)
    window.resize(600, 400)
    window.show()

    container = QWidget(window)
    container.setGeometry(30, 30, 240, 80)
    button = QPushButton("Export PGN", container)
    button.setGeometry(12, 18, 160, 36)
    button.setEnabled(False)
    container.show()
    button.show()

    attach_tooltip(
        container,
        Tooltip.for_disabled("Analyze the game before exporting PGN"),
    )

    manager = TooltipManager.instance(qapp).install()
    try:
        global_position = button.mapToGlobal(button.rect().center())
        event = QHelpEvent(
            QEvent.Type.ToolTip,
            container.mapFromGlobal(global_position),
            global_position,
        )
        qapp.sendEvent(container, event)

        assert manager.popup.isVisible()
        assert manager.popup.current_text == "Analyze the game before exporting PGN"
    finally:
        manager.shutdown()


def test_tooltip_hides_after_the_pointer_leaves_the_owner(
    qtbot, qapp, monkeypatch
):
    window = QWidget()
    qtbot.addWidget(window)
    window.resize(600, 400)
    window.show()

    target = QWidget(window)
    target.setGeometry(180, 180, 120, 32)
    target.show()
    qapp.processEvents()

    manager = TooltipManager.instance(qapp).install()
    try:
        manager.show_for(target, Tooltip.for_action("Delete game"))
        assert manager.popup.isVisible()

        monkeypatch.setattr(tooltip_module, "_cursor_position", lambda: QPoint(0, 0))
        manager._anchor = QRect(180, 180, 120, 32)
        manager._schedule_hide()

        qtbot.waitUntil(lambda: not manager.popup.isVisible(), timeout=1000)
    finally:
        manager.shutdown()


def test_entering_a_sibling_starts_the_dismiss_timer(qtbot, qapp, monkeypatch):
    window = QWidget()
    qtbot.addWidget(window)
    window.resize(600, 400)
    window.show()

    target = QWidget(window)
    target.setGeometry(20, 20, 120, 32)
    sibling = QWidget(window)
    sibling.setGeometry(20, 80, 120, 32)
    target.show()
    sibling.show()
    qapp.processEvents()

    manager = TooltipManager.instance(qapp).install()
    try:
        manager.show_for(target, Tooltip.for_action("Delete game"))
        assert manager.popup.isVisible()

        monkeypatch.setattr(tooltip_module, "_cursor_position", lambda: QPoint(0, 0))
        manager._anchor = QRect(20, 20, 120, 32)
        qapp.sendEvent(sibling, QEvent(QEvent.Type.Enter))

        qtbot.waitUntil(lambda: not manager.popup.isVisible(), timeout=1000)
    finally:
        manager.shutdown()


def test_popup_clamps_to_the_available_screen(qapp):
    manager = TooltipManager.instance(qapp).install()
    try:
        anchor = QRect(0, 0, 10, 10)
        screen = QGuiApplication.screenAt(anchor.center()) or QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else QRect()
        manager.popup.show_for(
            anchor,
            Tooltip.for_action("Edge-clamped tooltip"),
            side="top",
            animate=False,
        )

        assert available.contains(manager.popup.geometry())
        assert manager.popup.size().width() > 0
        assert manager.popup.size().height() > 0
    finally:
        manager.shutdown()


def test_popup_is_click_through_and_frameless(qapp):
    manager = TooltipManager.instance(qapp).install()
    try:
        popup = manager.popup
        assert popup.testAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        assert popup.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        assert popup.windowFlags() & Qt.WindowType.FramelessWindowHint
    finally:
        manager.shutdown()

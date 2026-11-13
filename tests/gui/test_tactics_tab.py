# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the per-game Tactics tab widget."""

from __future__ import annotations

from PyQt6.QtCore import Qt

from src.backend.analysis.tactics.report import GameTacticEntry, GameTacticsReport
from src.gui.analysis.tactics_tab import TacticRow, TacticsTab
from src.gui.components import EmptyState, Label


def _entry(role: str, motif: str, index: int, label: str, summary: str) -> GameTacticEntry:
    return GameTacticEntry(
        role=role,
        motif=motif,
        move_index=index,
        ply=index,
        move_label=label,
        summary=summary,
        classification="Best",
        eval_text="+0.2 → +0.4",
    )


def _white_report() -> GameTacticsReport:
    return GameTacticsReport(
        side="white",
        executed=(
            _entry("executed", "fork", 0, "1. e4", "attacks d5 and f5"),
        ),
        allowed=(
            _entry("allowed", "pin", 1, "1... e5", "Allowed Nc6"),
        ),
        lost=(
            _entry("lost", "hanging_piece", 2, "2. Nf3", "Knight on f3 · Punished by Bg5"),
        ),
        won=(
            _entry("won", "hanging_piece", 3, "2... Nc6", "Won pawn on e5"),
        ),
    )


def test_tactics_tab_renders_sections_and_counts(qtbot):
    tab = TacticsTab()
    qtbot.addWidget(tab)
    tab.show()

    tab.set_reports(
        {"white": _white_report(), "black": GameTacticsReport(side="black")},
        "white",
        {"white": "Alice", "black": "Bob"},
        "1-0",
    )

    texts = {label.text() for label in tab.findChildren(Label)}
    assert "1. e4" in texts
    assert "EXECUTED TACTICS" in texts
    assert "TACTICS ALLOWED" in texts
    assert "PIECES LOST" in texts
    assert "PIECES WON" in texts
    assert tab.summary_label.text() == "1 executed · 1 allowed · 1 lost · 1 won"
    assert len(tab.findChildren(TacticRow)) == 4


def test_row_click_emits_move_index(qtbot):
    tab = TacticsTab()
    qtbot.addWidget(tab)
    tab.show()
    tab.set_reports(
        {"white": _white_report()},
        "white",
        {"white": "Alice"},
        "1-0",
    )

    rows = tab.findChildren(TacticRow)
    with qtbot.waitSignal(tab.move_requested) as blocker:
        qtbot.mouseClick(rows[0], Qt.MouseButton.LeftButton)

    assert blocker.args == [0]


def test_selected_move_marks_the_matching_row_active(qtbot):
    tab = TacticsTab()
    qtbot.addWidget(tab)
    tab.set_reports({"white": _white_report()}, "white", {}, "1-0")

    tab.set_selected_move(1)

    active = [
        row.entry.move_index
        for row in tab.findChildren(TacticRow)
        if bool(row.property("active"))
    ]
    assert active == [1]


def test_side_toggle_switches_to_the_other_report(qtbot):
    tab = TacticsTab()
    qtbot.addWidget(tab)
    tab.set_reports(
        {"white": _white_report(), "black": GameTacticsReport(side="black")},
        "white",
        {"white": "Alice", "black": "Bob"},
        "1-0",
    )

    tab.side_control.set_value("black", emit=True)

    assert tab.summary_label.text() == ""
    assert len(tab.findChildren(TacticRow)) == 0


def test_empty_state_is_shown_without_tactics(qtbot):
    tab = TacticsTab()
    qtbot.addWidget(tab)
    tab.show_empty("No tactics here.")

    assert len(tab.findChildren(EmptyState)) == 1


def test_refresh_styles_is_safe(qtbot):
    tab = TacticsTab()
    qtbot.addWidget(tab)
    tab.set_reports({"white": _white_report()}, "white", {}, "1-0")

    tab.refresh_styles()
    tab.refresh_styles()

    assert len(tab.findChildren(TacticRow)) == 4

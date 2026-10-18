"""
Tests for HistoryView, GameImportWorker, and CSV export/import fidelity.
"""

import csv

import pytest
from PyQt6.QtWidgets import QLabel, QPushButton

from src.backend.storage.game_history import GAME_CSV_COLUMNS, GameHistoryManager
from src.backend.storage.models import GameAnalysis, GameMetadata, MoveAnalysis
from src.gui.components.game_list_item_widget import GameListItemWidget
from src.gui.views.history_view import GameImportWorker, HistoryView


def test_game_import_worker_execution(tmp_path, qtbot):
    """Test that GameImportWorker parses CSV in background and bulk saves without error."""
    db_path = str(tmp_path / "test_import.db")
    manager = GameHistoryManager(db_path)

    # Pre-insert one game to test duplicate skipping
    meta_pre = GameMetadata(
        white="Pre", black="Existing", result="1-0", date="2024.01.01", event="Pre", headers={}
    )
    manager.save_game(
        GameAnalysis(game_id="pre_1", metadata=meta_pre, moves=[], pgn_content="pre"), "pre"
    )

    # Create CSV file with 3 rows: 1 duplicate, 2 new
    csv_file = tmp_path / "games_to_import.csv"
    fieldnames = GAME_CSV_COLUMNS
    rows = [
        {
            "id": "pre_1",
            "white": "Pre",
            "black": "Existing",
            "result": "1-0",
            "date": "2024.01.01",
            "event": "Pre",
            "speed_category": "Rapid",
            "pgn": "pre",
            "timestamp": "100.0",
        },
        {
            "id": "new_1",
            "white": "Magnus",
            "black": "Nakamura",
            "result": "1-0",
            "date": "2024.02.01",
            "event": "Speed",
            "speed_category": "Blitz",
            "pgn": "1. e4 e5 1-0",
            "timestamp": "200.0",
        },
        {
            "id": "new_2",
            "white": "Gukesh",
            "black": "Ding",
            "result": "1/2-1/2",
            "date": "2024.03.01",
            "event": "Candidates",
            "speed_category": "Classical",
            "pgn": "1. d4 d5 1/2-1/2",
            "timestamp": "300.0",
        },
    ]

    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    worker = GameImportWorker(manager, str(csv_file))

    with qtbot.waitSignal(worker.finished, timeout=5000) as blocker:
        worker.start()

    imported_cnt, skipped_cnt = blocker.args
    assert imported_cnt == 2
    assert skipped_cnt == 1

    # Verify both games exist in DB with preserved timestamps
    assert manager.game_exists("new_1")
    assert manager.game_exists("new_2")
    g1 = manager.get_game("new_1")
    assert g1["timestamp"] == 200.0
    assert g1["speed_category"] == "Blitz"


def test_history_view_load_history_fast_path(tmp_path, qtbot, qapp):
    """Test HistoryView load_history utilizes cached speed_category and termination_mode."""
    db_path = str(tmp_path / "test_load.db")
    manager = GameHistoryManager(db_path)

    row = {
        "id": "cached_meta_game",
        "white": "Player1",
        "black": "Player2",
        "result": "1-0",
        "date": "2024.04.01",
        "event": "Rapid Cup",
        "speed_category": "Rapid",
        "termination": "White won by resignation",
        "termination_mode": "resignation",
        "pgn": "1. e4 e5 1-0",
        "timestamp": 12345.0,
    }
    manager.save_games_bulk([row])

    view = HistoryView()
    qtbot.addWidget(view)
    view.history_manager = manager
    view.load_history()

    assert len(view.games) == 1
    assert view.games[0].metadata.speed_category == "Rapid"
    assert view.games[0].metadata.termination_mode == "resignation"
    assert view.games[0].metadata.termination_description == "White won by resignation"


@pytest.mark.parametrize(
    "status,expected_badge,expected_action",
    [
        ("completed", "Analyzed", "reanalyze"),
        ("paused", "Paused", "resume"),
        ("not_started", "Unanalyzed", "analyze"),
    ],
)
def test_game_list_item_action_and_badge(qtbot, status, expected_badge, expected_action):
    """Test GameListItemWidget displays appropriate badge and emits action_requested for all statuses."""
    meta = GameMetadata(
        white="Magnus", black="Hikaru", result="1-0", date="2024.01.01", event="Speed", headers={}
    )
    moves = (
        [
            MoveAnalysis(
                move_number=1,
                ply=1,
                san="e4",
                uci="e2e4",
                fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            )
        ]
        if status != "not_started"
        else []
    )
    if status == "completed":
        moves[0].eval_after_cp = 30
        summary = {"analysis_status": "completed"}
    elif status == "paused":
        summary = {"analysis_status": "paused"}
    else:
        summary = {}

    game = GameAnalysis(
        game_id="g1", metadata=meta, moves=moves, summary=summary, pgn_content="1. e4"
    )

    for mode in ("detailed", "compact"):
        widget = GameListItemWidget(game, usernames=["Magnus"], view_mode=mode)
        qtbot.addWidget(widget)

        # Verify badge text
        badges = [w.text() for w in widget.findChildren(QLabel) if expected_badge in w.text()]
        assert len(badges) >= 1

        # Verify action button tooltip and signal emission
        action_buttons = [
            btn
            for btn in widget.findChildren(QPushButton)
            if expected_action.capitalize() in btn.toolTip()
        ]
        assert len(action_buttons) == 1
        with qtbot.waitSignal(widget.action_requested, timeout=1000) as blocker:
            action_buttons[0].click()
        assert blocker.args == [game, expected_action]


def test_history_view_game_action_propagation(tmp_path, qtbot):
    """Test clicking action button on a card in HistoryView propagates game_action_requested."""
    db_path = str(tmp_path / "test_action_prop.db")
    manager = GameHistoryManager(db_path)
    meta = GameMetadata(
        white="P1", black="P2", result="1-0", date="2024.01.01", event="Test", headers={}
    )
    manager.save_game(
        GameAnalysis(
            game_id="g_paused",
            metadata=meta,
            moves=[
                MoveAnalysis(
                    move_number=1,
                    ply=1,
                    san="e4",
                    uci="e2e4",
                    fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                    eval_after_cp=20,
                )
            ],
            summary={"analysis_status": "paused"},
            pgn_content="1. e4",
        ),
        "1. e4",
    )

    view = HistoryView()
    qtbot.addWidget(view)
    view.history_manager = manager
    view.load_history()

    card = view.game_list.list_widget.itemWidget(view.game_list.list_widget.item(0))
    resume_btn = next(btn for btn in card.findChildren(QPushButton) if "Resume" in btn.toolTip())

    with qtbot.waitSignal(view.game_action_requested, timeout=1000) as blocker:
        resume_btn.click()

    emitted_game, action = blocker.args
    assert emitted_game.game_id == "g_paused"
    assert action == "resume"


def test_history_view_analyzing_status_and_action(tmp_path, qtbot):
    """Test that a game currently being analyzed shows 'Analyzing...' badge and emits view_analysis."""
    db_path = str(tmp_path / "test_analyzing.db")
    manager = GameHistoryManager(db_path)
    meta = GameMetadata(
        white="P1", black="P2", result="1-0", date="2024.01.01", event="Test", headers={}
    )
    manager.save_game(
        GameAnalysis(
            game_id="g_analyzing",
            metadata=meta,
            moves=[],
            summary={"analysis_status": "unanalyzed"},
            pgn_content="1. e4",
        ),
        "1. e4",
    )

    view = HistoryView()
    qtbot.addWidget(view)
    view.history_manager = manager
    view.set_analyzing_game_id("g_analyzing")
    view.load_history()

    card = view.game_list.list_widget.itemWidget(view.game_list.list_widget.item(0))
    badges = [lbl.text() for lbl in card.findChildren(QLabel)]
    assert "Analyzing..." in badges

    view_btn = next(
        btn for btn in card.findChildren(QPushButton) if "View ongoing analysis" in btn.toolTip()
    )
    assert view_btn is not None

    with qtbot.waitSignal(view.game_action_requested, timeout=1000) as blocker:
        view_btn.click()

    emitted_game, action = blocker.args
    assert emitted_game.game_id == "g_analyzing"
    assert action == "view_analysis"

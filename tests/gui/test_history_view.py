"""
Tests for HistoryView, GameImportWorker, and CSV export/import fidelity.
"""

import csv

from src.backend.storage.game_history import GAME_CSV_COLUMNS, GameHistoryManager
from src.backend.storage.models import GameAnalysis, GameMetadata
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
    loaded = view.games[0]
    assert loaded.metadata.speed_category == "Rapid"
    assert loaded.metadata.termination_mode == "resignation"
    assert loaded.metadata.termination_description == "White won by resignation"

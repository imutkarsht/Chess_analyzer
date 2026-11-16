"""History bulk-selection and batch-launch tests."""

import json

from src.backend.models.analysis_batch import AnalysisBatch, AnalysisBatchItem
from src.backend.storage.game_history import GameHistoryManager
from src.gui.components.feedback.toast import ToastManager
from src.gui.views.history_view import HistoryView


def _row(game_id: str, status: str, timestamp: int) -> dict:
    summary = {"analysis_status": status}
    return {
        "id": game_id,
        "white": f"White {game_id}",
        "black": f"Black {game_id}",
        "result": "1-0",
        "date": "2026.01.01",
        "event": "Rapid",
        "source": "chesscom",
        "pgn": "1. e4 *",
        "summary_json": json.dumps(summary),
        "analysis_status": status,
        "timestamp": timestamp,
    }


def _view_with_manager(qtbot, manager):
    view = HistoryView()
    qtbot.addWidget(view)
    view.history_manager = manager
    view.load_history()
    return view


def _click_row(view, row: int):
    item = view.game_list.list_widget.item(row)
    assert item is not None
    view.game_list.list_widget.itemClicked.emit(item)


def test_batch_button_visibility_and_bulk_mode_only_shows_batchable_games(
    qtbot, qapp, tmp_path
):
    manager = GameHistoryManager(str(tmp_path / "bulk.db"))
    manager.save_games_bulk(
        [
            _row("fresh_1", "not_started", 100),
            _row("done", "completed", 200),
        ]
    )
    view = _view_with_manager(qtbot, manager)

    assert view.btn_batch.isHidden()
    manager.save_games_bulk([_row("fresh_2", "not_started", 300)])
    view.load_history()
    assert not view.btn_batch.isHidden()

    view.btn_batch.click()
    assert view._bulk_mode is True
    assert view.filter_bar.analysis_filter.isEnabled() is False
    assert view.game_list.total_count == 2
    assert not view.batch_selection_bar.isHidden()
    assert view.btn_batch.text() == "Analyze games"
    assert view.btn_batch.isEnabled() is False

    view._exit_batch_mode()
    assert view._bulk_mode is False
    assert view.filter_bar.analysis_filter.isEnabled() is True
    assert view.game_list.total_count == 3


def test_selection_survives_sort_and_paging_and_clears_on_search(qtbot, qapp, tmp_path):
    manager = GameHistoryManager(str(tmp_path / "selection.db"))
    manager.save_games_bulk(
        [_row(f"g{index}", "not_started", 1000 + index) for index in range(20)]
    )
    view = _view_with_manager(qtbot, manager)
    view.btn_batch.click()
    assert len(view.games) == 15
    assert view.game_list.total_count == 20

    _click_row(view, 0)
    assert view.batch_selection_bar.count_label.text() == "1 selected"
    assert view.btn_batch.text() == "Analyze 1 game"

    view.sort_dropdown.set_current_value("oldest")
    assert len(view._selected_games) == 1
    assert view.batch_selection_bar.count_label.text() == "1 selected"

    view._load_more()
    assert view.game_list.total_count == 20
    assert len(view._selected_games) == 1

    view.search_input.setText("no-such-game")
    assert len(view._selected_games) == 0
    assert view.btn_batch.isEnabled() is False

    view.search_input.setText("")
    _click_row(view, 0)
    assert len(view._selected_games) == 1
    view.source_filter.set_current_value("lichess")
    assert len(view._selected_games) == 0
    assert view.btn_batch.isEnabled() is False


def test_select_page_confirmation_counts_and_delete_guards(
    qtbot, qapp, tmp_path, monkeypatch
):
    manager = GameHistoryManager(str(tmp_path / "confirm.db"))
    manager.save_games_bulk(
        [
            _row("paused", "paused", 3000),
            _row("fresh", "not_started", 2000),
            _row("done", "completed", 1000),
        ]
    )
    manager.save_analysis_batch(
        AnalysisBatch(
            items=[
                AnalysisBatchItem(game_id="paused", position=1),
                AnalysisBatchItem(game_id="fresh", position=2),
            ]
        )
    )
    view = _view_with_manager(qtbot, manager)
    view.btn_batch.click()

    view.batch_selection_bar.btn_select_page.click()
    assert len(view._selected_games) == 2
    assert view.btn_batch.text() == "Analyze 2 games"

    messages = []
    monkeypatch.setattr(
        "src.gui.utils.gui_utils.confirm_dialog",
        lambda _parent, _title, message, **_kwargs: messages.append(message) or True,
    )
    emitted = []
    view.batch_analysis_requested.connect(emitted.append)
    view.btn_batch.click()

    assert len(emitted) == 1
    assert emitted[0] == ["paused", "fresh"]
    assert "1 will be analyzed" in messages[0]
    assert "1 will resume from partial results" in messages[0]
    assert "0 already complete will be skipped" in messages[0]

    warnings = []
    monkeypatch.setattr(
        ToastManager, "warning", lambda *_args, **_kwargs: warnings.append(True)
    )
    view.set_batch_running(True, active_game_id="paused", queued_ids={"paused", "fresh"})
    view._on_game_delete_requested("paused")
    assert warnings
    assert manager.game_exists("paused")
    assert manager.get_analysis_batch().item("paused") is not None

    view._on_game_delete_requested("fresh")
    assert manager.game_exists("fresh") is False
    assert manager.get_analysis_batch().item("fresh") is None

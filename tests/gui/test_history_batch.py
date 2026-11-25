"""History bulk-selection and batch-launch tests."""

import json

from PyQt6.QtWidgets import QLabel

from src.backend.models.analysis_batch import (
    BATCH_COMPLETED,
    BATCH_PAUSED,
    BATCH_RUNNING,
    OUTCOME_COMPLETED,
    OUTCOME_FAILED,
    OUTCOME_SKIPPED,
    AnalysisBatch,
    AnalysisBatchItem,
)
from src.backend.storage.game_history import GameHistoryManager
from src.gui.components.feedback.toast import ToastManager
from src.gui.views.history_batch import (
    BatchQueueCard,
    BatchSelectionBar,
    UpNextEntry,
)
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
        "src.gui.views.history_view.confirm_dialog",
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

    view.on_batch_started(manager.get_analysis_batch())
    view.set_batch_active(
        "paused",
        "White paused vs Black paused",
        1,
        2,
        {"paused", "fresh"},
    )
    row_widgets = {
        game.game_id: view.game_list.list_widget.itemWidget(
            view.game_list.list_widget.item(index)
        )
        for index, game in enumerate(view.game_list.games)
    }
    active_badges = [
        label.text() for label in row_widgets["paused"].findChildren(QLabel)
    ]
    queued_badges = [
        label.text() for label in row_widgets["fresh"].findChildren(QLabel)
    ]
    assert "In batch · 1/2" in active_badges
    assert "Queued" in queued_badges

    view._collapse_batch()
    assert view.batch_queue_card.isHidden()
    assert not view.batch_collapsed_bar.isHidden()
    assert "Batch analysis" in view.batch_collapsed_bar.text()
    view._expand_batch()
    assert not view.batch_queue_card.isHidden()
    assert view.batch_collapsed_bar.isHidden()

    warnings = []
    monkeypatch.setattr(
        ToastManager, "warning", lambda *_args, **_kwargs: warnings.append(True)
    )
    view._on_game_delete_requested("paused")
    assert warnings
    assert manager.game_exists("paused")
    assert manager.get_analysis_batch().item("paused") is not None

    view._on_game_delete_requested("fresh")
    assert manager.game_exists("fresh") is False
    assert manager.get_analysis_batch().item("fresh") is None


def test_batch_controls_have_tooltips(qtbot):
    selection = BatchSelectionBar()
    qtbot.addWidget(selection)
    card = BatchQueueCard()
    qtbot.addWidget(card)

    for control in (
        selection.btn_select_page,
        selection.btn_clear,
        selection.btn_exit,
        card.btn_pause,
        card.btn_resume,
        card.btn_dismiss,
        card.btn_collapse,
        card.btn_cancel,
    ):
        assert control.toolTip()


def test_batch_queue_card_renders_running_paused_and_summary_states(qtbot, qapp):
    card = BatchQueueCard()
    qtbot.addWidget(card)
    items = [
        AnalysisBatchItem("g1", 1, outcome=OUTCOME_COMPLETED),
        AnalysisBatchItem("g2", 2),
        AnalysisBatchItem("g3", 3),
    ]

    card.show_batch(
        AnalysisBatch(state=BATCH_RUNNING, items=items),
        active_label="Alice vs Bob",
        position=2,
        move_current=5,
        move_total=10,
        elapsed_seconds=192,
        eta_seconds=600,
    )
    card.set_up_next(
        [
            UpNextEntry("g2", "Carol vs Dave", 34, 50),
            UpNextEntry("g3", "Eve vs Frank", 41, 65),
        ]
    )
    assert not card.isHidden()
    assert card.up_next_list.count() == 2
    removed = []
    card.remove_requested.connect(removed.append)
    first_row = card.up_next_list.itemWidget(card.up_next_list.item(0))
    first_row.remove_button.click()
    assert removed == ["g2"]
    assert card.title_label.text() == "Batch analysis"
    assert card.game_title.text() == "Alice vs Bob"
    assert card.game_position.text() == "Game 2 of 3"
    assert card.elapsed_value.text() == "03:12"
    assert card.eta_value.text() == "~10:00"
    assert card.finish_value.text() != "—"
    card.set_move_progress(5, 10, 33, 12.5)
    assert "Move 5 / 10" in card.move_label.text()
    assert "~00:33" in card.game_meta.text()
    assert not card.btn_pause.isHidden()
    assert card.btn_resume.isHidden()
    assert not card.btn_cancel.isHidden()
    assert card.btn_dismiss.isHidden()
    with qtbot.waitSignal(card.pause_requested, timeout=500):
        card.btn_pause.click()
    with qtbot.waitSignal(card.collapse_requested, timeout=500):
        card.btn_collapse.click()

    paused = AnalysisBatch(state=BATCH_PAUSED, items=items)
    card.show_batch(paused, active_label="Alice vs Bob")
    assert card.btn_pause.isHidden()
    assert not card.btn_resume.isHidden()
    assert card.elapsed_value.text() == "03:12"
    assert card.eta_value.text() == "—"
    assert "1 completed" in card.summary_label.text()
    assert "2 remaining" in card.summary_label.text()

    finished_items = [
        AnalysisBatchItem("g1", 1, outcome=OUTCOME_COMPLETED),
        AnalysisBatchItem("g2", 2, outcome=OUTCOME_SKIPPED),
        AnalysisBatchItem("g3", 3, outcome=OUTCOME_FAILED, error="bad"),
    ]
    card.show_batch(AnalysisBatch(state=BATCH_COMPLETED, items=finished_items))
    assert not card.btn_dismiss.isHidden()
    assert card.btn_cancel.isHidden()
    assert "1 completed" in card.summary_label.text()
    assert "1 skipped" in card.summary_label.text()
    assert "1 failed" in card.summary_label.text()

    card.show_batch(AnalysisBatch(state=BATCH_RUNNING, items=items))
    card.set_up_next([])
    assert card.up_next_container.isHidden()

    card.hide_card()
    card.set_up_next([UpNextEntry("later", "Later vs Game", 20, 30, 2)])
    assert card.up_next_list.count() == 0
    card.show()
    qtbot.waitUntil(lambda: card.up_next_list.count() == 1, timeout=500)

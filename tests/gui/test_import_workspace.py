"""Import workspace batch and table behaviour."""

import chess
from PyQt6.QtCore import Qt

from src.backend.models.game_info import GameInfo
from src.backend.storage.game_identity import game_identity_key
from src.backend.storage.pgn_parser import PGNParser
from src.gui.import_workspace import GameBatch, GameImportView
from src.gui.import_workspace.boards import (
    MiniBoardFenWorker,
    summarize_pgn,
)
from src.gui.import_workspace.model import (
    COL_BOARD,
    COL_DETAILS,
    COL_MOVES,
    COL_TERMINATION,
)
from src.gui.views.history_view import HistoryView


def _batch(saved_first: bool = True) -> GameBatch:
    pgn = (
        '[Event "One"]\n[White "Alice"]\n[Black "Bob"]\n[Result "1-0"]\n\n'
        "1. e4 e5 1-0\n\n"
        '[Event "Two"]\n[White "Carol"]\n[Black "Dave"]\n[Result "0-1"]\n\n'
        "1. d4 d5 0-1"
    )
    index = PGNParser.index_pgn_text(pgn)
    saved_keys = (
        {game_identity_key("?", "Alice", "Bob", "1-0")} if saved_first else set()
    )
    return GameBatch.from_pgn_index(index, saved_keys, "games.pgn")


def test_summarize_pgn_returns_the_final_position():
    pgn = (
        '[Event "One"]\n[White "Alice"]\n[Black "Bob"]\n[Result "1-0"]\n\n'
        "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0"
    )

    summary = summarize_pgn(pgn)

    assert summary.move_count == 3
    assert summary.last_fen is not None
    assert summary.last_move_uci == "a7a6"
    board = chess.Board(summary.last_fen)
    assert board.piece_at(chess.B5) is not None


def test_fen_worker_returns_the_final_move_for_lazy_rows(qapp):
    pgn = (
        '[Event "One"]\n[White "Alice"]\n[Black "Bob"]\n[Result "1-0"]\n\n'
        "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0"
    )
    emitted = []
    worker = MiniBoardFenWorker(9, [(3, pgn)])
    worker.completed.connect(lambda token, result: emitted.append((token, result)))

    worker.run()

    assert emitted[0][0] == 9
    position = emitted[0][1][3]
    assert position.last_move_uci == "a7a6"
    assert position.fen is not None


def test_batch_marks_saved_games_and_builds_candidates(qapp):
    batch = _batch()

    assert batch.label == "games.pgn"
    assert [c.in_history for c in batch.candidates] == [True, False]
    assert batch.candidates[0].move_count == 1
    assert "d4" in batch.candidates[1].pgn_text()


def test_view_opens_exactly_one_checked_game(qtbot):
    view = GameImportView()
    qtbot.addWidget(view)
    opened = []
    view.open_game_requested.connect(
        lambda pgn, source_data: opened.append(pgn)
    )

    view.set_batch(_batch())

    assert view.model.rowCount() == 2
    assert not view.btn_open.isEnabled()

    view.model.set_checked(1, True)

    assert view.btn_open.isEnabled()
    view.btn_open.click()
    assert len(opened) == 1
    assert "d4" in opened[0]


def test_single_candidate_is_checked_automatically(qtbot):
    view = GameImportView()
    qtbot.addWidget(view)
    index = PGNParser.index_pgn_text(
        '[Event "One"]\n[White "Alice"]\n[Black "Bob"]\n[Result "1-0"]\n\n'
        "1. e4 e5 1-0"
    )

    view.set_batch(GameBatch.from_pgn_index(index, set(), "one.pgn"))

    assert view.model.checked_count() == 1
    assert view.btn_open.isEnabled()


def test_check_state_can_be_set_by_the_table(qtbot):
    view = GameImportView()
    qtbot.addWidget(view)
    view.set_batch(_batch())

    index = view.model.index(1, 0)
    assert view.model.setData(
        index, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole
    )

    assert view.model.checked_count() == 1


def test_search_and_filters_narrow_the_table(qtbot):
    view = GameImportView()
    qtbot.addWidget(view)
    view.set_batch(_batch())

    view.search_input.setText("Carol")
    view._apply_filters()
    assert view.proxy.rowCount() == 1

    view.search_input.clear()
    view.history_filter.set_value("saved", emit=False)
    view._apply_filters()
    assert view.proxy.rowCount() == 1
    assert view.model.candidate_at(0).white == "Alice"

    view._on_header_toggled(True)
    assert view.model.checked_count() == 0

    view.history_filter.set_value("new", emit=False)
    view._apply_filters()
    view._on_header_toggled(True)
    assert view.model.checked_count() == 1


def test_missing_metadata_hides_columns_but_moves_stay_available(qtbot):
    view = GameImportView()
    qtbot.addWidget(view)
    index = PGNParser.index_pgn_text(
        '[Event "Rated Blitz game"]\n[White "Alice"]\n[Black "Bob"]\n'
        '[Result "1-0"]\n\n1. e4 e5 1-0'
    )
    view.set_batch(GameBatch.from_pgn_index(index, set(), "one.pgn"))

    assert not view.table.isColumnHidden(COL_MOVES)
    assert view.table.isColumnHidden(COL_DETAILS)
    assert view.table.isColumnHidden(COL_TERMINATION)


def test_saved_rows_are_not_selectable_and_multi_select_adds(qtbot):
    view = GameImportView()
    qtbot.addWidget(view)
    view.set_batch(_batch())
    assert not (
        view.model.flags(view.model.index(0, 0))
        & Qt.ItemFlag.ItemIsUserCheckable
    )
    assert (
        view.model.flags(view.model.index(1, 0))
        & Qt.ItemFlag.ItemIsUserCheckable
    )

    view.set_batch(_batch(saved_first=False))
    view.model.set_many_checked([0, 1], True)

    assert not view.btn_open.isEnabled()
    assert view.btn_add.isEnabled()
    assert "2" in view.btn_add.text()


def test_online_batch_falls_back_to_pgn_headers(qtbot):
    pgn = (
        '[Event "Club Championship"]\n[White "Alice"]\n[Black "Bob"]\n'
        '[Result "1-0"]\n[Opening "Italian Game"]\n[ECO "C50"]\n'
        '[Termination "Time forfeit"]\n[TimeControl "300+3"]\n\n'
        "1. e4 e5 2. Nf3 Nc6 3. Bc4 1-0"
    )
    info = GameInfo(
        game_id="x",
        source="lichess",
        white="Alice",
        black="Bob",
        result="1-0",
        date="2026-08-23",
        pgn=pgn,
        time_class="blitz",
        opening=None,
    )

    batch = GameBatch.from_game_infos([info], set(), "online")
    candidate = batch.candidates[0]

    assert candidate.opening == "Italian Game"
    assert candidate.eco == "C50"
    assert candidate.termination == "Time forfeit"
    assert candidate.event == "Club Championship"
    assert candidate.last_move_uci == "f1c4"


def test_result_filter_uses_saved_username_perspective(qtbot):
    view = GameImportView()
    qtbot.addWidget(view)
    original_username = view._config.get("lichess_username", "")
    view._config.set("lichess_username", "Alice")
    pgn = (
        '[Event "One"]\n[White "Alice"]\n[Black "Bob"]\n[Result "1-0"]\n\n'
        "1. e4 e5 1-0\n\n"
        '[Event "Two"]\n[White "Carol"]\n[Black "Alice"]\n[Result "1-0"]\n\n'
        "1. d4 d5 1-0\n\n"
        '[Event "Three"]\n[White "Carol"]\n[Black "Dave"]\n[Result "1-0"]\n\n'
        "1. c4 c5 1-0\n\n"
        '[Event "Four"]\n[White "Alice"]\n[Black "Bob"]\n[Result "1/2-1/2"]\n\n'
        "1. Nf3 Nf6 1/2-1/2"
    )
    index = PGNParser.index_pgn_text(pgn)
    view.set_batch(GameBatch.from_pgn_index(index, set(), "mixed.pgn"))

    def shown(value: str) -> int:
        assert view.result_filter.set_current_value(
            value, add_missing=False
        )
        view._apply_filters()
        return view.proxy.rowCount()

    assert shown("my_win") == 1
    assert shown("my_loss") == 1
    assert shown("my_draw") == 1
    assert shown("my_game") == 3
    assert shown("other") == 1

    view.result_filter.set_current_value("my_win", add_missing=False)
    view.color_filter.set_current_value("black", add_missing=False)
    view._apply_filters()
    assert view.proxy.rowCount() == 0
    view.color_filter.set_current_value("white", add_missing=False)
    view._apply_filters()
    assert view.proxy.rowCount() == 1
    view.color_filter.set_current_value("all", add_missing=False)
    view._apply_filters()

    view._config.set("lichess_username", original_username)


def test_no_matches_shows_the_shared_empty_state(qtbot):
    view = GameImportView()
    qtbot.addWidget(view)
    view.set_batch(_batch())

    view.search_input.setText("nobody")
    view._apply_filters()

    assert view.table_stack.currentWidget() is view.empty_state


def test_clear_filters_only_appears_when_needed(qtbot):
    view = GameImportView()
    qtbot.addWidget(view)
    view.set_batch(_batch())

    assert view.btn_clear_filters.isHidden()

    view.search_input.setText("Carol")
    view._apply_filters()
    assert not view.btn_clear_filters.isHidden()

    view._clear_filters()
    assert view.btn_clear_filters.isHidden()
    assert view.proxy.rowCount() == 2


def test_board_column_can_be_toggled(qtbot):
    view = GameImportView()
    qtbot.addWidget(view)
    view.set_batch(_batch())

    view.btn_boards.setChecked(False)
    view._on_boards_toggled()
    assert view.table.isColumnHidden(COL_BOARD)

    view.btn_boards.setChecked(True)
    view._on_boards_toggled()
    assert not view.table.isColumnHidden(COL_BOARD)


def test_history_hosts_and_closes_the_import_workspace(qtbot):
    view = HistoryView()
    qtbot.addWidget(view)

    view.show_import_workspace(_batch())

    assert view.page_stack.currentWidget() is view.import_view
    assert view.import_view.model.rowCount() == 2

    view.close_import_workspace()

    assert view.page_stack.currentWidget() is view.history_page

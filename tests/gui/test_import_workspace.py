"""Import workspace batch and table behaviour."""

import chess
from PyQt6.QtCore import Qt

from src.backend.storage.game_identity import game_identity_key
from src.backend.storage.pgn_parser import PGNParser
from src.gui.import_workspace import GameBatch, GameImportView
from src.gui.import_workspace.boards import summarize_pgn
from src.gui.import_workspace.model import COL_BOARD
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

    move_count, fen = summarize_pgn(pgn)

    assert move_count == 3
    assert fen is not None
    board = chess.Board(fen)
    assert board.piece_at(chess.B5) is not None


def test_batch_marks_saved_games_and_builds_candidates(qapp):
    batch = _batch()

    assert batch.label == "games.pgn"
    assert [c.in_history for c in batch.candidates] == [True, False]
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

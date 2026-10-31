"""Opening Explorer loading behaviour and book-row helpers."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import chess

from src.gui.views.explorer import (
    ExplorerBookMixin,
    ExplorerBookSkeleton,
    ExplorerOnlineMixin,
    ExplorerView,
)


def _update_view(*, online: bool, cached: bool):
    view = SimpleNamespace(
        board_widget=SimpleNamespace(
            board=chess.Board(), draw_interactive_overlays=MagicMock()
        ),
        opening_db=MagicMock(),
        opening_badge=SimpleNamespace(setText=MagicMock()),
        _explorer_pending_fen=None,
        _explorer_debounce=MagicMock(),
        _current_book_count=0,
        _explorer_enabled=lambda: True,
        _online_explorer_allowed=lambda: online,
        _render_cached_explorer=lambda _fen: cached,
        _update_explorer_hint=MagicMock(),
        _draw_local_book=MagicMock(),
        _show_book_skeleton=MagicMock(),
        _update_book_toggle=MagicMock(),
        lichess_attribution=SimpleNamespace(setVisible=MagicMock()),
    )
    view.opening_db.get_node_by_fen.return_value = None
    return view


def test_online_lookup_shows_skeleton_instead_of_local_book(qapp):
    view = _update_view(online=True, cached=False)

    ExplorerView.update_opening_db(view, chess.STARTING_FEN)

    view._draw_local_book.assert_not_called()
    view._show_book_skeleton.assert_called_once_with()
    view._explorer_debounce.start.assert_called_once()
    assert view._explorer_pending_fen == chess.STARTING_FEN


def test_offline_lookup_renders_local_book(qapp):
    view = _update_view(online=False, cached=False)

    ExplorerView.update_opening_db(view, chess.STARTING_FEN)

    view._draw_local_book.assert_called_once_with(None)
    view._show_book_skeleton.assert_not_called()
    view.lichess_attribution.setVisible.assert_called_with(False)


def test_cached_online_position_skips_skeleton_and_network(qapp):
    view = _update_view(online=True, cached=True)

    ExplorerView.update_opening_db(view, chess.STARTING_FEN)

    view._show_book_skeleton.assert_not_called()
    view._explorer_debounce.stop.assert_called_once()
    assert view._explorer_pending_fen is None


def test_stale_online_result_is_ignored(qapp):
    board = chess.Board()
    board.push_san("e4")
    worker = SimpleNamespace(fen=chess.STARTING_FEN)
    view = SimpleNamespace(
        _explorer_worker=worker,
        board_widget=SimpleNamespace(board=board),
        on_lichess_explorer_finished=MagicMock(),
        _draw_local_book_fallback=MagicMock(),
    )
    view._is_worker_current = lambda candidate: ExplorerOnlineMixin._is_worker_current(
        view, candidate
    )

    ExplorerOnlineMixin._on_explorer_data(
        view, worker, {"moves": [{"san": "e4", "white": 1, "draws": 0, "black": 0}]}
    )
    ExplorerOnlineMixin._on_explorer_error(view, worker, "offline")

    view.on_lichess_explorer_finished.assert_not_called()
    view._draw_local_book_fallback.assert_not_called()


def test_empty_online_result_falls_back_to_local_book(qapp):
    board = chess.Board()
    worker = SimpleNamespace(fen=board.fen())
    view = SimpleNamespace(
        _explorer_worker=worker,
        board_widget=SimpleNamespace(board=board),
        on_lichess_explorer_finished=MagicMock(),
        _draw_local_book_fallback=MagicMock(),
    )
    view._is_worker_current = lambda candidate: ExplorerOnlineMixin._is_worker_current(
        view, candidate
    )

    ExplorerOnlineMixin._on_explorer_data(view, worker, {"moves": []})

    view._draw_local_book_fallback.assert_called_once_with()
    view.on_lichess_explorer_finished.assert_not_called()


def test_sqlite_book_entries_do_not_mutate_the_live_board(qapp):
    board = chess.Board()
    fen_before = board.fen()
    opening_db = MagicMock()
    opening_db.get_children.return_value = ["e4", "d4", "NotAMove"]
    opening_db.get_node_by_fen.return_value = 2
    opening_db.get_openings_at_node.return_value = [("B00", "King's Pawn")]
    view = SimpleNamespace(
        board_widget=SimpleNamespace(board=board),
        opening_db=opening_db,
    )

    entries = ExplorerBookMixin._sqlite_book_entries(view, 1)

    assert [entry[0] for entry in entries] == ["e4", "d4"]
    assert all(entry[1] == "King's Pawn" for entry in entries)
    assert board.fen() == fen_before


def test_online_rows_are_finalized_and_attributed(qapp):
    view = SimpleNamespace(
        _clear_book_rows=MagicMock(),
        board_widget=SimpleNamespace(
            board=chess.Board(), draw_interactive_overlays=MagicMock()
        ),
        _create_book_row_widget=MagicMock(return_value=MagicMock()),
        book_layout=MagicMock(),
        _book_row_widgets=[],
        _current_book_count=0,
        _update_book_toggle=MagicMock(),
        lichess_attribution=SimpleNamespace(setVisible=MagicMock()),
        _finalize_book_layout=MagicMock(),
    )
    view._format_count = ExplorerBookMixin._format_count

    ExplorerBookMixin.on_lichess_explorer_finished(
        view, {"moves": [{"san": "e4", "white": 10, "draws": 5, "black": 5}]}
    )

    view._finalize_book_layout.assert_called_once_with()
    assert view._current_book_count == 1
    view.lichess_attribution.setVisible.assert_called_once_with(True)


def test_book_skeleton_lifecycle_and_rows(qapp):
    skeleton = ExplorerBookSkeleton()
    assert skeleton.layout().count() == ExplorerBookSkeleton.ROW_COUNT

    skeleton.start()
    assert not skeleton.is_animating()
    skeleton.stop()
    skeleton.refresh_styles()
    skeleton.deleteLater()

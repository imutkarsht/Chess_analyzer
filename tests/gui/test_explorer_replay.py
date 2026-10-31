"""Explorer replay must rebuild the full game, not just the current ply."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import chess

from src.backend.storage.models import MoveAnalysis
from src.gui.views.explorer import ExplorerView


class _BoardWidget:
    def __init__(self, board):
        self.board = board
        self.move_made = MagicMock()

    def load_fen(self, fen, *_args, chess960=None, **_kwargs):
        self.board = chess.Board(fen, chess960=bool(chess960))

    def set_best_move(self, *_args):
        pass

    def set_last_move_classification(self, *_args):
        pass

    def update_board(self):
        pass


def _make_moves(uci_moves, start_fen=chess.STARTING_FEN):
    board = chess.Board(start_fen)
    fens = [board.fen()]
    moves = []
    for index, uci in enumerate(uci_moves):
        move = chess.Move.from_uci(uci)
        moves.append(
            MoveAnalysis(
                move_number=index // 2 + 1,
                ply=index + 1,
                san=board.san(move),
                uci=uci,
                fen_before=board.fen(),
            )
        )
        board.push(move)
        fens.append(board.fen())
    return moves, fens


def _view(source_board):
    view = SimpleNamespace(
        is_chess960=False,
        starting_fen=source_board.starting_fen,
        board=source_board.copy(),
        board_widget=_BoardWidget(source_board.copy()),
        move_history=[],
        move_list_widget=MagicMock(),
        pending_classification_index=-1,
        last_eval=None,
        classify_enabled=False,
        chk_engine=MagicMock(isChecked=lambda: False),
        on_move_made=lambda _fen: None,
    )
    view.update_opening_db = lambda _fen: None
    view._update_material = lambda: None
    view._refresh_engine = lambda _fen: None
    view._start_backlog_classification = lambda: None
    return view


def test_replay_uses_displayed_ply_not_single_move_stack():
    """Regression: Board.set_position leaves one move on the stack.

    Replaying only that move from the starting FEN used to push an illegal
    late-game move (e.g. e5d4) and abort the app.
    """
    moves, fens = _make_moves(["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6"])
    target = 4
    source_board = chess.Board(moves[target].fen_before)
    source_board.push_uci(moves[target].uci)
    assert len(source_board.move_stack) == 1

    view = _view(source_board)
    ExplorerView.load_board_state(
        view, source_board, moves, move_index=target, starting_fen=None
    )

    assert view.board.fen() == fens[target + 1]
    assert view.board_widget.board.fen() == fens[target + 1]
    assert [entry[3] for entry in view.move_history] == [
        move.san for move in moves[: target + 1]
    ]


def test_replay_honours_a_non_standard_start_fen():
    start_fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
    moves, fens = _make_moves(["g1f3", "b8c6", "f1b5"], start_fen=start_fen)
    target = 2
    source_board = chess.Board(moves[target].fen_before)
    source_board.push_uci(moves[target].uci)

    view = _view(source_board)
    ExplorerView.load_board_state(
        view, source_board, moves, move_index=target, starting_fen=start_fen
    )

    assert view.board.fen() == fens[target + 1]
    assert len(view.move_history) == target + 1


def test_illegal_replay_stops_without_crashing():
    moves = [
        MoveAnalysis(
            move_number=1,
            ply=1,
            san="e5d4",
            uci="e5d4",
            fen_before=chess.STARTING_FEN,
        )
    ]
    source_board = chess.Board()

    view = _view(source_board)
    ExplorerView.load_board_state(view, source_board, moves, move_index=0)

    assert view.move_history == []
    assert view.board.fen() == chess.STARTING_FEN

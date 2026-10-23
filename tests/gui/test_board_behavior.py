"""Behavioural contract for the chess board.

These pin the interaction branches, the ``load_fen`` tri-state contract and the
``BoardConfig`` switches so a future board change fails here instead of in the app.
"""

import importlib

import chess
import pytest
from PyQt6.QtWidgets import QDialog

from src.gui.board import Board, BoardConfig

PROMOTION_FEN = "8/P7/8/8/8/8/8/K6k w - - 0 1"
# Fischer Random position 3: the king starts on f1 and castles to g1. Loading this
# without the Chess960 flag silently loses the castling right.
CHESS960_FEN = "bqnnrkrb/pppppppp/8/8/8/8/PPPPPPPP/BQNNRKRB w KQkq - 0 1"


def _make(board_factory=Board):
    """Create a visible, laid-out board so coordinate maths has real geometry."""
    board = board_factory()
    board.resize(400, 400)
    board.show()
    for _ in range(3):
        board.board_container.layout().activate()
        board._enforce_square_board()
    return board


@pytest.fixture
def board(qapp):
    widget = _make()
    yield widget
    widget.deleteLater()


def _square_center(widget, square):
    """Pixel centre of ``square`` inside the SVG layer, mirroring the hit-test maths."""
    if widget.svg_widget.width() <= 0:
        pytest.skip("board geometry unavailable")
    scale = widget.svg_widget.width() / 390.0
    file_idx = chess.square_file(square)
    rank_idx = chess.square_rank(square)
    if widget.is_flipped:
        grid_x, grid_y = 7 - file_idx, rank_idx
    else:
        grid_x, grid_y = file_idx, 7 - rank_idx
    return (
        (15 + grid_x * 45 + 22.5) * scale,
        (15 + grid_y * 45 + 22.5) * scale,
    )


def _press(widget, square):
    widget.handle_press(*_square_center(widget, square))


# --------------------------------------------------------------------------- interaction


def test_press_own_piece_selects_and_lists_legal_destinations(board):
    _press(board, chess.E2)

    assert board.selected_square == chess.E2
    assert set(board.legal_destinations) == {chess.E3, chess.E4}


def test_second_press_on_illegal_square_clears_selection_without_moving(board):
    _press(board, chess.E2)
    _press(board, chess.E5)

    assert board.selected_square is None
    assert board.legal_destinations == []
    assert board.board.fen() == chess.STARTING_FEN


def test_click_to_move_pushes_move_and_emits_fen(board):
    emitted = []
    board.move_made.connect(emitted.append)

    _press(board, chess.E2)
    _press(board, chess.E4)

    assert board.board.peek().uci() == "e2e4"
    assert board.selected_square is None
    assert emitted == [board.board.fen()]


def test_drag_below_threshold_keeps_click_semantics(board):
    x, y = _square_center(board, chess.E2)
    board.handle_press(x, y)
    board.handle_move(x + 2, y + 2)  # 2px < 5px threshold

    assert board.is_dragging is False


def test_drag_release_on_legal_square_pushes_move(board):
    start = _square_center(board, chess.E2)
    board.handle_press(*start)
    board.handle_move(start[0] + 40, start[1] - 40)

    assert board.is_dragging is True

    board.handle_release(*_square_center(board, chess.E4))

    assert board.board.peek().uci() == "e2e4"
    assert board.is_dragging is False


def test_drag_release_outside_destination_snaps_back(board):
    start = _square_center(board, chess.E2)
    board.handle_press(*start)
    board.handle_move(start[0] + 40, start[1] - 40)
    board.handle_release(*_square_center(board, chess.H5))

    assert board.board.fen() == chess.STARTING_FEN


def test_promotion_picks_piece_via_dialog(board, monkeypatch):
    module = importlib.import_module(type(board).__module__)

    class _AcceptingDialog:
        selected_piece = chess.QUEEN

        def __init__(self, color, parent=None):
            self.color = color

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(module, "PromotionDialog", _AcceptingDialog)
    board.load_fen(PROMOTION_FEN)

    board.attempt_move(chess.A7, chess.A8)

    promoted = board.board.piece_at(chess.A8)
    assert promoted is not None
    assert promoted.piece_type == chess.QUEEN
    assert promoted.color == chess.WHITE


def test_flip_board_keeps_hit_testing_aligned(board):
    board.flip_board()

    assert board.is_flipped is True

    _press(board, chess.E2)
    assert board.selected_square == chess.E2


# --------------------------------------------------------------------------- overlays


def test_legal_move_dots_one_overlay_per_destination(board):
    _press(board, chess.E2)

    assert board.overlay_layout.count() == len(board.legal_destinations)


def test_legal_dots_hidden_when_disabled(board):
    board.set_show_legal_moves(False)
    _press(board, chess.E2)

    assert board.overlay_layout.count() == 0


def test_classification_badge_only_drawn_for_last_move_overlay(qapp):
    """Analysis badges replayed moves; Explorer badges the move just played."""
    analysis = _make(Board)
    analysis.attempt_move(chess.E2, chess.E4)
    analysis.last_move_classification = "Blunder"
    analysis.draw_interactive_overlays()
    assert analysis.overlay_layout.count() == 0

    explorer = _make(lambda: Board(BoardConfig(classification_overlay="last_move")))
    explorer.attempt_move(chess.E2, chess.E4)
    explorer.set_last_move_classification("Blunder")
    assert explorer.overlay_layout.count() == 1


# --------------------------------------------------------------------------- load_fen
# Tri-state: an explicit ``flipped`` overrides orientation, an omitted one preserves
# it. ``chess960`` omitted resets to standard chess (historic-analysis contract).


def test_load_fen_uses_explicit_flip_flag(qapp):
    board = _make()

    board.load_fen(chess.STARTING_FEN, True)
    assert board.is_flipped is True

    board.load_fen(chess.STARTING_FEN, False)
    assert board.is_flipped is False


def test_load_fen_preserves_orientation_when_flip_omitted(qapp):
    board = _make()
    board.flip_board()

    board.load_fen(chess.STARTING_FEN, chess960=False)

    assert board.is_flipped is True


def test_load_fen_clears_chess960_and_replay_state_by_default(qapp):
    board = _make()
    board.load_analysis_position(CHESS960_FEN, chess960=True)
    assert board.is_chess960 is True

    board.load_fen(chess.STARTING_FEN)

    assert board.is_chess960 is False
    assert board.board.chess960 is False
    assert board.game_moves == []


def test_load_fen_honours_chess960(qapp):
    board = _make()

    board.load_fen(CHESS960_FEN, chess960=True)

    assert board.board.chess960 is True
    assert any(board.board.is_castling(move) for move in board.board.legal_moves)


# --------------------------------------------------------------------------- configuration


def test_drag_can_be_disabled_by_config(qapp):
    board = _make(lambda: Board(BoardConfig(drag_and_drop=False)))
    start = _square_center(board, chess.E2)

    board.handle_press(*start)
    board.handle_move(start[0] + 40, start[1] - 40)

    assert board.is_dragging is False


def test_click_to_move_can_be_disabled_by_config(qapp):
    board = _make(lambda: Board(BoardConfig(click_to_move=False)))

    _press(board, chess.E2)
    _press(board, chess.E4)

    assert board.selected_square is None
    assert board.board.fen() == chess.STARTING_FEN


def test_coordinates_and_last_move_highlight_are_toggleable(qapp):
    plain = _make(lambda: Board(BoardConfig(show_coordinates=False, show_last_move=False)))
    plain.attempt_move(chess.E2, chess.E4)

    plain_svg = plain._generate_custom_board_svg({"light": "#fff", "dark": "#000"}, "")
    assert b"<text" not in plain_svg
    assert b'opacity="0.35"' not in plain_svg

    decorated = _make()
    decorated.attempt_move(chess.E2, chess.E4)
    decorated_svg = decorated._generate_custom_board_svg({"light": "#fff", "dark": "#000"}, "")
    assert b"<text" in decorated_svg
    assert b'opacity="0.35"' in decorated_svg


def test_set_board_swaps_position_and_clears_analysis_state(qapp):
    board = _make()
    board.set_best_move("e2e4")
    board.last_move_classification = "Blunder"

    board.set_board(chess.Board(CHESS960_FEN, chess960=True))

    assert board.board.fen() == chess.Board(CHESS960_FEN, chess960=True).fen()
    assert board.is_chess960 is True
    assert board.best_move_uci is None
    assert board.last_move_classification is None
    assert board.selected_square is None

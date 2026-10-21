"""Variation mode: the playable analysis branch on the main board."""

import chess
from PyQt6.QtCore import QObject, pyqtSignal

from src.backend.storage.models import GameAnalysis, GameMetadata, MoveAnalysis
from src.gui.analysis.move_list_panel import MoveListPanel
from src.gui.analysis.variation_bar import VariationBar
from src.gui.analysis.variation_mode import VariationMode
from src.gui.board import BoardWidget
from src.gui.main_window import MainWindow

AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


class _StubMoveList(QObject):
    lines_updated = pyqtSignal(list, bool, str)

    def __init__(self):
        super().__init__()
        self.requests = []

    def begin_variation(self, fen, is_white):
        self.requests.append((fen, is_white))
        self.lines_updated.emit([], is_white, fen)

    def end_variation(self):
        self.requests.append((None, None))


def _mode():
    board = BoardWidget()
    panel = _StubMoveList()
    bar = VariationBar()
    return VariationMode(board, panel, bar), board, panel, bar


def test_entry_hints_the_move_without_playing_it(qapp):
    mode, board, panel, bar = _mode()

    assert mode.enter(chess.STARTING_FEN, "e2e4", return_index=4) is True

    assert board.dimmed is True
    assert board.interactive is True
    assert board.best_move_uci == "e2e4"
    assert board.board.fen() == chess.STARTING_FEN  # arrow only, nothing played
    assert bar.isHidden() is False
    assert panel.requests == [(chess.STARTING_FEN, True)]
    assert mode.sans == []


def test_illegal_or_invalid_suggestions_are_dropped(qapp):
    mode, board, _, _ = _mode()

    assert mode.enter(chess.STARTING_FEN, "e2e5", return_index=0) is True
    assert board.best_move_uci is None
    assert mode.enter("not a fen", "e2e4", return_index=0) is False


def test_playing_a_move_tracks_san_and_reanalyses(qapp):
    mode, board, panel, _ = _mode()
    mode.enter(chess.STARTING_FEN, "e2e4", return_index=2)
    panel.requests.clear()

    assert mode.play_uci("e2e4") is True

    assert mode.sans == ["e4"]
    assert board.board.fen() == AFTER_E4
    assert board.best_move_uci is None  # stale arrow cleared until the engine answers
    assert panel.requests[-1] == (AFTER_E4, False)
    assert board.eval_bar is not None


def test_playing_a_move_keeps_the_last_eval_until_the_engine_answers(qapp):
    """No artificial 0.0 dip while the new position is being analysed."""
    mode, board, _, _ = _mode()
    mode.enter(chess.STARTING_FEN, "e2e4", return_index=2)
    board.eval_bar.set_eval(320, None)

    mode.play_uci("e2e4")

    assert board.eval_bar.target_cp == 320


def test_engine_lines_drive_arrow_and_white_perspective_eval(qapp):
    mode, board, panel, _ = _mode()
    mode.enter(chess.STARTING_FEN, "e2e4", return_index=0)

    # Black to move: +120 for Black must read as -1.20 for White.
    panel.lines_updated.emit(
        [{"pv_uci": ["e7e5"], "cp": 120, "multipv": 1}], False, chess.STARTING_FEN
    )

    assert board.best_move_uci == "e7e5"
    assert board.eval_bar.target_cp == -120


def test_undo_and_reset_return_to_the_branch_point(qapp):
    mode, board, _, _ = _mode()
    mode.enter(chess.STARTING_FEN, "e2e4", return_index=6)
    mode.play_uci("e2e4")
    mode.play_uci("e7e5")
    assert mode.sans == ["e4", "e5"]

    mode.undo()
    assert mode.sans == ["e4"]
    assert board.board.fen() == AFTER_E4

    mode.undo()
    assert mode.sans == []
    assert board.board.fen() == chess.STARTING_FEN
    assert board.best_move_uci == "e2e4"

    mode.play_uci("d2d4")
    mode.reset()
    assert mode.sans == []
    assert board.board.fen() == chess.STARTING_FEN
    assert board.best_move_uci == "e2e4"


def test_exit_restores_the_caller_and_keeps_the_return_index(qapp):
    mode, board, panel, bar = _mode()
    restored = []
    mode.exited.connect(restored.append)

    mode.enter(chess.STARTING_FEN, "e2e4", return_index=7)
    # Branching from inside a variation must not lose the original exit point.
    mode.play_uci("e2e4")
    mode.enter(AFTER_E4, "e7e5", return_index=99)

    mode.exit()

    assert restored == [7]
    assert not mode.is_active
    assert board.dimmed is False
    assert board.best_move_uci is None
    assert board.interactive is False
    assert bar.isHidden() is True
    assert panel.requests[-1] == (None, None)


class _StubLiveWorker(QObject):
    info_ready = pyqtSignal(dict)
    thinking_started = pyqtSignal()
    thinking_stopped = pyqtSignal()

    def __init__(self, engine_path, config_manager=None):
        super().__init__()
        self.config_manager = config_manager
        self.calls = []

    def start(self):
        pass

    def stop(self):
        pass

    def set_position(self, fen, seq=0):
        self.calls.append((fen, seq))

    def set_chess960(self, enabled):
        pass


def test_move_list_variation_session_drops_stale_results(qapp, monkeypatch):
    monkeypatch.setattr("src.gui.analysis.move_list_panel.LiveAnalysisWorker", _StubLiveWorker)
    panel = MoveListPanel()
    emitted = []
    panel.lines_updated.connect(lambda *args: emitted.append(args))

    panel.begin_variation(chess.STARTING_FEN, True)
    fen, seq = panel.live_worker.calls[-1]
    assert fen == chess.STARTING_FEN
    assert emitted == [([], True, chess.STARTING_FEN)]

    # A result from the previous position must be ignored.
    panel.on_live_analysis_update({"seq": seq - 1, "multipv": 1, "pv_uci": ["e2e4"]})
    assert len(emitted) == 1

    panel.on_live_analysis_update({"seq": seq, "multipv": 1, "pv_uci": ["e2e4"], "cp": 10})
    assert emitted[-1][0][0]["pv_uci"] == ["e2e4"]
    assert emitted[-1][2] == chess.STARTING_FEN

    panel.end_variation()
    assert panel.live_worker.calls[-1][0] is None


def test_variation_flow_on_the_main_board(qapp, qtbot):
    """Window wiring: request → playable dimmed board → Esc restores the game."""
    window = MainWindow()
    qtbot.addWidget(window)
    meta = GameMetadata(white="W", black="B", result="1-0", headers={})
    game = GameAnalysis(
        game_id="",
        metadata=meta,
        moves=[MoveAnalysis(1, 1, "e4", "e2e4", chess.STARTING_FEN)],
        pgn_content="",
    )
    window.load_game(game)

    window._on_variation_requested(chess.STARTING_FEN, "e2e4")

    assert window.variation.is_active
    assert window.board_widget.dimmed is True
    assert window.board_widget.best_move_uci == "e2e4"
    assert window.variation_bar.isHidden() is False
    assert window.move_list_panel._variation_active is True
    assert window.analysis_panel.toggle_checkbox.isEnabled() is False

    assert window.variation.play_uci("e2e4")
    assert window.variation.sans == ["e4"]

    # The Exit button (not only Esc) must leave the variation.
    window.variation_bar.btn_exit.click()

    assert not window.variation.is_active
    assert window.board_widget.current_move_index == -1
    assert window.board_widget.interactive is False
    assert window.variation_bar.isHidden() is True
    assert window.analysis_panel.toggle_checkbox.isEnabled() is True

    # Esc remains the dedicated keyboard exit.
    window._on_variation_requested(chess.STARTING_FEN, "e2e4")
    window._on_escape()
    assert not window.variation.is_active

    # Flipping keeps one captured-pieces card on each side of the board.
    layout = window.center_layout
    window.flip_board()
    board_index = layout.indexOf(window.board_widget)
    assert layout.indexOf(window.captured_white) == board_index - 1
    assert layout.indexOf(window.captured_black) == board_index + 1

    window.flip_board()
    board_index = layout.indexOf(window.board_widget)
    assert layout.indexOf(window.captured_black) == board_index - 1
    assert layout.indexOf(window.captured_white) == board_index + 1

    # Loading a game drops the orientation inherited from historic positions.
    window.flip_board()
    window.load_game(game)
    assert window.board_widget.is_flipped is False
    board_index = layout.indexOf(window.board_widget)
    assert layout.indexOf(window.captured_black) == board_index - 1

    window.close()


def test_navigation_leaves_the_variation(qapp, qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    meta = GameMetadata(white="W", black="B", result="1-0", headers={})
    game = GameAnalysis(
        game_id="",
        metadata=meta,
        moves=[MoveAnalysis(1, 1, "e4", "e2e4", chess.STARTING_FEN)],
        pgn_content="",
    )
    window.load_game(game)

    window._on_variation_requested(chess.STARTING_FEN, "e2e4")
    window.on_move_selected(0)

    assert not window.variation.is_active
    assert window.board_widget.current_move_index == 0
    assert window.board_widget.board.peek().uci() == "e2e4"
    window.close()

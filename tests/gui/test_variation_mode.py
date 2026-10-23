"""Variation mode: persistent branches and auto-played engine lines."""

import chess
from PyQt6.QtCore import QObject, pyqtSignal

from src.gui.analysis.variation_graph import VariationGraph
from src.gui.analysis.variation_mode import VariationMode
from src.gui.board import Board

AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
AFTER_D4 = "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1"


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
    board = Board()
    panel = _StubMoveList()
    graph = VariationGraph()
    return VariationMode(board, panel, graph), board, panel, graph


def test_entry_autoplays_and_engine_updates_ghost_and_cache(qapp):
    mode, board, panel, graph = _mode()

    assert mode.enter(chess.STARTING_FEN, "e2e4", return_index=4) is True

    assert board.dimmed is True
    assert board.board.fen() == AFTER_E4
    assert graph.isHidden() is False
    assert len(mode.tree.branches) == 1
    assert mode.tree.branches[0].name == "e4"
    assert mode.sans == ["e4"]
    assert panel.requests[-1][0] == AFTER_E4

    # Black's +30cp is -0.30 from White's perspective, cached on the node.
    panel.lines_updated.emit([{"pv_uci": ["e7e5"], "cp": 30, "depth": 12}], False, AFTER_E4)
    assert mode._best_uci == "e7e5"
    assert mode.tree.active_node.eval_cp == -30
    assert graph._ghost_san == "e5"

    # Rewind and play a different first move: the old branch survives.
    mode.undo()
    mode.play_uci("d2d4")
    assert board.board.fen() == AFTER_D4
    assert [branch.name for branch in mode.tree.branches] == ["e4", "d4"]

    # Clicking the first branch chip checks out its tip.
    graph.branch_clicked.emit(mode.tree.branches[0].branch_id)
    assert board.board.fen() == AFTER_E4


def test_exit_keeps_the_tree_and_reentry_restores_it(qapp):
    mode, board, panel, graph = _mode()
    restored = []
    mode.exited.connect(restored.append)

    mode.enter(chess.STARTING_FEN, "e2e4", return_index=7)
    mode.undo()
    mode.play_uci("d2d4")
    tree = mode.tree

    mode.exit()

    assert restored == [7]
    assert mode.is_active is False
    assert graph.isHidden() is True
    assert board.interactive is False
    assert panel.requests[-1] == (None, None)

    assert mode.open_tree(chess.STARTING_FEN, return_index=3) is True
    assert mode.tree is tree
    assert len(mode.tree.branches) == 2
    assert board.board.fen() == AFTER_D4  # resumes at the last active node

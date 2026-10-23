"""Variation mode — a persistent, engine-backed branch tree on the board.

The controller is FEN-based: the tree is keyed by the canonical branch-point
FEN, so the same exploration is restored whether it was opened from an engine
line, Show best/refutation, or the move-list branch badge.
"""

from __future__ import annotations

import chess
from PyQt6.QtCore import QObject, pyqtSignal

from src.backend.analysis.variation_tree import (
    RecordStatus,
    VariationNode,
    VariationTree,
    canonical_fen,
)
from src.utils.logger import logger


class VariationMode(QObject):
    """Owns the board's analysis state while a variation tree is open."""

    entered = pyqtSignal()
    exited = pyqtSignal(int)  # game move index to restore
    position_changed = pyqtSignal(str)  # current variation FEN
    tree_changed = pyqtSignal()  # branch structure/count changed
    message = pyqtSignal(str, str)  # text, kind

    def __init__(self, board_widget, move_list_panel, graph, parent=None):
        super().__init__(parent)
        self.board_widget = board_widget
        self.move_list_panel = move_list_panel
        self.graph = graph

        self.return_index = -1
        self.tree: VariationTree | None = None
        self._trees: dict[str, VariationTree] = {}
        self._active = False
        self._chess960 = False
        self._root_fen: str | None = None
        self._root_label = ""
        self._best_uci: str | None = None
        self._best_san: str | None = None

        graph.play_best_requested.connect(self.play_best)
        graph.undo_requested.connect(self.undo)
        graph.reset_requested.connect(self.reset)
        graph.exit_requested.connect(self.exit)
        graph.ghost_clicked.connect(self.play_best)
        graph.node_clicked.connect(self.select_node)
        graph.branch_clicked.connect(self.select_branch)
        graph.branch_delete_requested.connect(self.delete_branch)
        graph.branch_rename_requested.connect(self.rename_branch)

        board_widget.move_made.connect(self._on_move_made)
        move_list_panel.lines_updated.connect(self._on_lines_updated)

    # ------------------------------------------------------------------ properties
    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def base_fen(self) -> str | None:
        return self.tree.root.fen if self.tree is not None else self._root_fen

    @property
    def sans(self) -> list[str]:
        if self.tree is None:
            return []
        return [node.san for node in self.tree.path_to(self.tree.active_node) if node.san]

    @property
    def can_go_back(self) -> bool:
        return self.tree is not None and self.tree.active_node.parent is not None

    @property
    def can_go_forward(self) -> bool:
        if self.tree is None:
            return False
        return bool(self.tree.active_node.children) or bool(self._best_uci)

    def tree_counts(self) -> dict[str, int]:
        return {
            fen: tree.branch_count() for fen, tree in self._trees.items() if tree.branch_count() > 0
        }

    # ------------------------------------------------------------------ entry / exit
    def enter(
        self,
        fen: str,
        suggestion_uci: str | None,
        return_index: int,
        chess960: bool = False,
        auto_play: bool = True,
        root_label: str = "",
    ) -> bool:
        """Open (or restore) the variation tree rooted at ``fen``.

        ``suggestion_uci`` is auto-played as the first branch move.  Pass
        ``auto_play=False`` when the caller only wants the position with an
        engine suggestion arrow.
        """
        try:
            chess.Board(fen, chess960=chess960)
        except ValueError as e:
            logger.warning("Cannot explore invalid FEN %s: %s", fen, e)
            return False

        tree = self._activate(fen, return_index, chess960, root_label)
        tree.select_node(tree.root)
        self.board_widget.load_analysis_position(tree.root.fen, chess960=chess960)
        self.board_widget.set_dimmed(True)

        suggestion = self._legal_uci(tree, suggestion_uci)
        if suggestion and auto_play:
            self._set_ghost(None, None)
            if not self.play_uci(suggestion):
                self._sync_view()
        else:
            self._sync_view()
            if suggestion:
                probe = chess.Board(tree.root.fen, chess960=chess960)
                move = chess.Move.from_uci(suggestion)
                self._set_ghost(suggestion, probe.san(move))
        self.entered.emit()
        return True

    def open_tree(
        self,
        fen: str,
        return_index: int,
        chess960: bool = False,
        root_label: str = "",
    ) -> bool:
        """Open an existing tree (move-list badge) at its last active node."""
        try:
            chess.Board(fen, chess960=chess960)
        except ValueError:
            return False
        tree = self._activate(fen, return_index, chess960, root_label)
        tree.select_node(tree.last_active_node)
        self._sync_view()
        self.entered.emit()
        return True

    def _activate(
        self, fen: str, return_index: int, chess960: bool, root_label: str
    ) -> VariationTree:
        if not self._active:
            self.return_index = return_index
        self._active = True
        self._chess960 = chess960
        key = canonical_fen(fen, chess960)
        self._root_fen = key
        self._root_label = root_label or ""
        tree = self._trees.get(key)
        if tree is None:
            tree = VariationTree(key, chess960=chess960)
            self._trees[key] = tree
        self.tree = tree
        self.board_widget.set_dimmed(True)
        self.graph.setVisible(True)
        self.graph.set_context(self._context_text())
        return tree

    def exit(self, notify: bool = True) -> None:
        """Leave variation mode.  The tree stays in the session store."""
        if not self._active:
            return
        self._active = False
        self.graph.setVisible(False)
        self.graph.clear()
        self.move_list_panel.end_variation()
        self.board_widget.set_best_move(None)
        self.board_widget.set_dimmed(False)
        self.board_widget.set_interactive(False)
        self._best_uci = None
        self._best_san = None
        self.tree = None
        if notify:
            self.exited.emit(self.return_index)

    def reset_session(self) -> None:
        self._trees.clear()
        self.tree = None
        self._root_fen = None
        if self._active:
            self.exit(notify=False)
        self.graph.clear()
        self.tree_changed.emit()

    # ------------------------------------------------------------------ navigation
    def select_node(self, node_id: int) -> None:
        if self.tree is None:
            return
        if self.tree.select_node_id(node_id) is None:
            return
        self._sync_view()

    def select_branch(self, branch_id: int) -> None:
        if self.tree is None:
            return
        if self.tree.select_branch_id(branch_id) is None:
            return
        self._sync_view()

    def cycle_sibling(self, direction: int) -> None:
        if self.tree is None:
            return
        branch = self.tree.cycle_sibling(direction)
        if branch is not None:
            self._sync_view()

    def undo(self) -> None:
        if not self._active or self.tree is None:
            return
        parent = self.tree.active_node.parent
        if parent is None:
            return
        self.tree.select_node(parent)
        self._sync_view()

    def forward(self) -> None:
        if not self._active or self.tree is None:
            return
        children = self.tree.active_node.children
        if children:
            child = max(children, key=lambda node: node.last_visit_seq)
            self.tree.select_node(child)
            self._sync_view()
            return
        self.play_best()

    def go_to_start(self) -> None:
        if not self._active or self.tree is None:
            return
        self.tree.select_node(self.tree.root)
        self._sync_view()

    def go_to_end(self) -> None:
        if not self._active or self.tree is None:
            return
        if self.tree.active_branch is not None:
            self.tree.select_branch(self.tree.active_branch)
        elif self.tree.branches:
            branch = max(self.tree.branches, key=lambda item: item.last_active_seq)
            self.tree.select_branch(branch)
        self._sync_view()

    def reset(self) -> None:
        self.go_to_start()

    def play_best(self) -> None:
        if self._best_uci:
            self.play_uci(self._best_uci)

    def play_uci(self, uci: str) -> bool:
        """Play a UCI move from the active node, forking when necessary."""
        if not self._active or self.tree is None or not uci:
            return False
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return False
        probe = chess.Board(self.tree.active_node.fen, chess960=self._chess960)
        if move not in probe.legal_moves:
            return False
        san = probe.san(move)
        probe.push(move)
        return self._record_and_sync(uci, san, probe.fen())

    # ------------------------------------------------------------------ mutation
    def _on_move_made(self, fen: str) -> None:
        if not self._active or self.tree is None:
            return
        board = self.board_widget.board
        if not board.move_stack:
            return
        move = board.peek()
        probe = board.copy()
        probe.pop()
        san = probe.san(move)
        if not self._record_and_sync(move.uci(), san, fen):
            # The tree rejected the move: undo it so the board never displays a
            # position that is absent from the tree. Cap eviction is silent.
            self.board_widget.undo_move()
            self._sync_view()
            logger.warning("Variation move rejected by the tree")

    def _record_and_sync(self, uci: str, san: str, fen_after: str) -> bool:
        if self.tree is None:
            return False
        result = self.tree.record_move(uci, san, fen_after)
        if result.status is RecordStatus.BLOCKED:
            logger.warning("No evictable branch at the variation cap")
            return False
        self._sync_view()
        self.tree_changed.emit()
        return True

    def delete_branch(self, branch_id: int) -> None:
        if self.tree is None:
            return
        if self.tree.delete_branch(branch_id):
            self._sync_view()
            self.tree_changed.emit()

    def rename_branch(self, branch_id: int, name: str) -> None:
        if self.tree is None:
            return
        if self.tree.rename_branch(branch_id, name):
            self._refresh_graph()


    # ------------------------------------------------------------------ view sync
    def _sync_view(self) -> None:
        if not self._active or self.tree is None:
            return
        node = self.tree.active_node
        self.board_widget.load_analysis_position(node.fen, chess960=self._chess960)
        self.board_widget.set_dimmed(True)
        if node.eval_cp is not None or node.eval_mate is not None:
            self.board_widget.eval_bar.set_eval(node.eval_cp, node.eval_mate)
        self.board_widget.set_best_move(None)
        self._best_uci = None
        self._best_san = None
        self.graph.set_context(self._context_text())
        self.graph.set_state(self.tree, node, self.tree.active_branch)
        self.move_list_panel.begin_variation(node.fen, self.board_widget.board.turn == chess.WHITE)
        self.position_changed.emit(node.fen)

    def _refresh_graph(self) -> None:
        if self.tree is None:
            return
        self.graph.set_context(self._context_text())
        self.graph.set_state(
            self.tree,
            self.tree.active_node,
            self.tree.active_branch,
            self._best_san,
        )
        if self._best_uci:
            self.graph.set_ghost(self._best_san, self._eval_text(self.tree.active_node))

    def _context_text(self) -> str:
        source = self._root_label or "this position"
        count = self.tree.branch_count() if self.tree is not None else 0
        return f"from {source} · {count} line{'s' if count != 1 else ''}"

    def _set_ghost(self, uci: str | None, san: str | None) -> None:
        self._best_uci = uci
        self._best_san = san
        self.board_widget.set_best_move(uci)
        self.graph.set_ghost(san, self._eval_text(self.tree.active_node) if self.tree else None)

    # ------------------------------------------------------------------ engine results
    def _on_lines_updated(self, lines: list, fen: str) -> None:
        if not self._active or self.tree is None or not lines:
            return
        node = self.tree.active_node
        try:
            if fen and canonical_fen(fen, self._chess960) != node.fen:
                return
        except ValueError:
            return

        top = lines[0]
        uci = top.first_move
        san = None
        if uci:
            try:
                move = chess.Move.from_uci(uci)
                probe = chess.Board(node.fen, chess960=self._chess960)
                if move in probe.legal_moves:
                    san = probe.san(move)
            except ValueError:
                san = None

        # Lines arrive White-perspective, so no side-to-move flip is needed.
        cp = top.cp
        mate = top.mate
        if cp is not None or mate is not None:
            self.tree.cache_eval(node, cp, mate, top.depth)
            self.board_widget.eval_bar.set_eval(cp, mate)
            eval_text = self._eval_text(node)
            if eval_text:
                self.graph.update_node_eval(node.node_id, eval_text)
        self._set_ghost(uci if san else None, san)

    @staticmethod
    def _eval_text(node: VariationNode | None) -> str:
        if node is None:
            return ""
        if node.eval_mate is not None:
            return f"{'+' if node.eval_mate > 0 else '-'}M{abs(node.eval_mate)}"
        if node.eval_cp is not None:
            return f"{node.eval_cp / 100:+.2f}"
        return ""

    @staticmethod
    def _legal_uci(tree: VariationTree, uci: str | None) -> str | None:
        if not uci:
            return None
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return None
        board = chess.Board(tree.root.fen, chess960=tree.chess960)
        return uci if move in board.legal_moves else None

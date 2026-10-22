"""Persistent variation tree for the analysis board.

The tree is deliberately Qt-free: it owns chess positions, branch labels and
lane assignment, while the GUI only renders the resulting state.  Every node is
a position *after* a move (the root is the branch point itself), which makes
navigation a matter of loading a FEN rather than replaying a move stack.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import chess

MAX_CHILDREN = 3


class RecordStatus(Enum):
    CREATED = "created"
    EXTENDED = "extended"
    SELECTED = "selected"
    EVICTED = "evicted"
    BLOCKED = "blocked"


@dataclass(slots=True)
class VariationNode:
    node_id: int
    parent: VariationNode | None
    fen: str
    move_uci: str | None
    san: str
    ply: int
    lane: int
    branch_id: int | None
    children: list[VariationNode] = field(default_factory=list)
    eval_cp: int | None = None
    eval_mate: int | None = None
    eval_depth: int | None = None
    last_visit_seq: int = 0
    created_seq: int = 0

    @property
    def is_root(self) -> bool:
        return self.parent is None


@dataclass(slots=True)
class VariationBranch:
    branch_id: int
    name: str
    custom_name: bool
    fork_node: VariationNode
    first_node: VariationNode
    tip: VariationNode
    lane: int
    color_index: int
    created_seq: int
    last_active_seq: int = 0


@dataclass(slots=True)
class RecordResult:
    status: RecordStatus
    node: VariationNode | None = None
    branch: VariationBranch | None = None
    evicted_name: str | None = None


def canonical_fen(fen: str, chess960: bool = False) -> str:
    """Normalize a FEN so equivalent positions compare by the same key."""
    return chess.Board(fen, chess960=chess960).fen()


class VariationTree:
    """A named, lane-aware move tree rooted at one analysis position."""

    def __init__(self, root_fen: str, chess960: bool = False):
        self.chess960 = chess960
        self.root = VariationNode(
            node_id=0,
            parent=None,
            fen=canonical_fen(root_fen, chess960),
            move_uci=None,
            san="",
            ply=0,
            lane=0,
            branch_id=None,
        )
        self.branches: list[VariationBranch] = []
        self.active_node = self.root
        self.active_branch: VariationBranch | None = None
        self.last_active_node = self.root
        self._next_node_id = 1
        self._next_branch_id = 1
        self._seq = 0

    # ------------------------------------------------------------------ lookup
    def next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def all_nodes(self) -> list[VariationNode]:
        result: list[VariationNode] = []
        stack = [self.root]
        while stack:
            node = stack.pop()
            result.append(node)
            stack.extend(reversed(node.children))
        return result

    def find_node(self, node_id: int) -> VariationNode | None:
        for node in self.all_nodes():
            if node.node_id == node_id:
                return node
        return None

    def find_node_by_fen(self, fen: str) -> VariationNode | None:
        try:
            target = canonical_fen(fen, self.chess960)
        except ValueError:
            return None
        for node in self.all_nodes():
            if node.fen == target:
                return node
        return None

    def find_child(self, node: VariationNode, uci: str) -> VariationNode | None:
        for child in node.children:
            if child.move_uci == uci:
                return child
        return None

    def branch_for_node(self, node: VariationNode | None) -> VariationBranch | None:
        if node is None or node.branch_id is None:
            return None
        for branch in self.branches:
            if branch.branch_id == node.branch_id:
                return branch
        return None

    def branch_for_id(self, branch_id: int) -> VariationBranch | None:
        for branch in self.branches:
            if branch.branch_id == branch_id:
                return branch
        return None

    def path_to(self, node: VariationNode) -> list[VariationNode]:
        path: list[VariationNode] = []
        current: VariationNode | None = node
        while current is not None:
            path.append(current)
            current = current.parent
        path.reverse()
        return path

    def branch_moves(self, branch: VariationBranch) -> list[VariationNode]:
        moves: list[VariationNode] = []
        current: VariationNode | None = branch.tip
        while current is not None:
            moves.append(current)
            if current is branch.first_node:
                break
            current = current.parent
        moves.reverse()
        return moves

    def branch_count(self) -> int:
        return len(self.branches)

    def max_depth(self) -> int:
        return max((node.ply for node in self.all_nodes()), default=0)

    def max_lane(self) -> int:
        return max((branch.lane for branch in self.branches), default=0)

    def subtree_size(self, node: VariationNode) -> int:
        return 1 + sum(self.subtree_size(child) for child in node.children)

    # ------------------------------------------------------------------ selection
    def _touch(self, node: VariationNode) -> None:
        seq = self.next_seq()
        node.last_visit_seq = seq
        self.active_node = node
        self.last_active_node = node
        branch = self.branch_for_node(node)
        self.active_branch = branch
        if branch is not None:
            branch.last_active_seq = seq

    def select_node(self, node: VariationNode) -> None:
        self._touch(node)

    def select_node_id(self, node_id: int) -> VariationNode | None:
        node = self.find_node(node_id)
        if node is None:
            return None
        self.select_node(node)
        return node

    def select_branch(self, branch: VariationBranch) -> VariationNode:
        self._touch(branch.tip)
        self.active_branch = branch
        return branch.tip

    def select_branch_id(self, branch_id: int) -> VariationNode | None:
        branch = self.branch_for_id(branch_id)
        if branch is None:
            return None
        return self.select_branch(branch)

    def sibling_branches(self, node: VariationNode | None = None) -> list[VariationBranch]:
        """Branches competing at the nearest fork to ``node``."""
        current = node or self.active_node
        fork: VariationNode | None = None
        if current.children and len(current.children) > 1:
            fork = current
        else:
            probe = current
            while probe.parent is not None:
                parent = probe.parent
                if len(parent.children) > 1:
                    fork = parent
                    break
                probe = parent
            if fork is None and self.root.children:
                fork = self.root

        if fork is None:
            return []
        result: list[VariationBranch] = []
        seen: set[int] = set()
        for child in fork.children:
            branch = self.branch_for_node(child)
            if branch is not None and branch.branch_id not in seen:
                seen.add(branch.branch_id)
                result.append(branch)
        return sorted(result, key=lambda branch: branch.lane)

    def cycle_sibling(self, direction: int) -> VariationBranch | None:
        siblings = self.sibling_branches()
        if len(siblings) < 2:
            return None
        current = self.active_branch
        try:
            index = siblings.index(current) if current is not None else -1
        except ValueError:
            index = -1
        target = siblings[(index + (1 if direction >= 0 else -1)) % len(siblings)]
        self.select_branch(target)
        return target

    # ------------------------------------------------------------------ mutation
    def record_move(self, uci: str, san: str, fen_after: str) -> RecordResult:
        """Add/select ``uci`` from the current active node.

        The caller is responsible for keeping the board in sync.  Returning
        ``BLOCKED`` means no tree mutation happened and the board move must be
        rolled back.
        """
        parent = self.active_node
        existing = self.find_child(parent, uci)
        if existing is not None:
            self.select_node(existing)
            return RecordResult(RecordStatus.SELECTED, existing, self.active_branch)

        evicted_name: str | None = None
        if len(parent.children) >= MAX_CHILDREN:
            victim = self._eviction_candidate(parent)
            if victim is None:
                return RecordResult(RecordStatus.BLOCKED)
            victim_branch = self.branch_for_node(victim)
            evicted_name = victim_branch.name if victim_branch is not None else victim.san
            self._remove_subtree(victim)

        extend = self.active_branch is not None and self.active_branch.tip is parent
        lane = self.active_branch.lane if extend else self._allocate_lane()
        node = VariationNode(
            node_id=self._next_node_id,
            parent=parent,
            fen=canonical_fen(fen_after, self.chess960),
            move_uci=uci,
            san=san,
            ply=parent.ply + 1,
            lane=lane,
            branch_id=self.active_branch.branch_id if extend else None,
            created_seq=self.next_seq(),
        )
        self._next_node_id += 1
        parent.children.append(node)

        if extend:
            assert self.active_branch is not None
            branch = self.active_branch
            node.branch_id = branch.branch_id
            branch.tip = node
            status = RecordStatus.EXTENDED
        else:
            branch = VariationBranch(
                branch_id=self._next_branch_id,
                name=san,
                custom_name=False,
                fork_node=parent,
                first_node=node,
                tip=node,
                lane=lane,
                color_index=lane,
                created_seq=self.next_seq(),
            )
            self._next_branch_id += 1
            self.branches.append(branch)
            node.branch_id = branch.branch_id
            status = RecordStatus.CREATED

        if evicted_name is not None:
            status = RecordStatus.EVICTED
        self._touch(node)
        self.active_branch = branch
        return RecordResult(status, node, branch, evicted_name)

    def _allocate_lane(self) -> int:
        used = {branch.lane for branch in self.branches}
        lane = 0
        while lane in used:
            lane += 1
        return lane

    def _eviction_candidate(self, parent: VariationNode) -> VariationNode | None:
        if not parent.children:
            return None

        protected: set[int] = set()
        if self.active_branch is not None:
            # Never truncate the branch the user is currently extending.
            for child in parent.children:
                if child.branch_id == self.active_branch.branch_id:
                    protected.add(child.node_id)

        current: VariationNode | None = self.active_node
        while current is not None and current.parent is not None:
            if current.parent is parent:
                protected.add(current.node_id)
                break
            current = current.parent

        if not protected:
            ranked = sorted(
                parent.children,
                key=lambda child: (
                    self.branch_for_node(child).last_active_seq
                    if self.branch_for_node(child) is not None
                    else child.last_visit_seq
                ),
                reverse=True,
            )
            protected.add(ranked[0].node_id)

        candidates = [child for child in parent.children if child.node_id not in protected]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda child: (
                self.branch_for_node(child).last_active_seq
                if self.branch_for_node(child) is not None
                else child.last_visit_seq
            ),
        )

    def _remove_subtree(self, node: VariationNode) -> set[int]:
        removed_ids: set[int] = set()
        stack = [node]
        while stack:
            current = stack.pop()
            removed_ids.add(current.node_id)
            stack.extend(current.children)

        if node.parent is not None:
            node.parent.children = [
                child for child in node.parent.children if child.node_id != node.node_id
            ]

        removed_branch_ids = {
            branch.branch_id
            for branch in self.branches
            if branch.first_node.node_id in removed_ids
            or branch.fork_node.node_id in removed_ids
        }
        self.branches = [
            branch for branch in self.branches if branch.branch_id not in removed_branch_ids
        ]
        # A branch whose tip was inside the removed subtree is truncated, not
        # deleted: its earlier moves still exist above the eviction point.
        for branch in self.branches:
            if branch.tip.node_id in removed_ids:
                branch.tip = node.parent or self.root

        if self.active_node.node_id in removed_ids:
            self.active_node = node.parent or self.root
            self.last_active_node = self.active_node
            self.active_branch = self.branch_for_node(self.active_node)
        elif self.active_branch is not None and self.active_branch.branch_id in removed_branch_ids:
            self.active_branch = self.branch_for_node(self.active_node)
        return removed_branch_ids

    def delete_branch(self, branch_id: int) -> bool:
        branch = self.branch_for_id(branch_id)
        if branch is None:
            return False
        self._remove_subtree(branch.first_node)
        return True

    def rename_branch(self, branch_id: int, name: str) -> bool:
        branch = self.branch_for_id(branch_id)
        if branch is None:
            return False
        cleaned = " ".join(name.split())[:24]
        if cleaned:
            branch.name = cleaned
            branch.custom_name = True
        else:
            branch.name = branch.first_node.san
            branch.custom_name = False
        return True

    def cache_eval(
        self,
        node: VariationNode,
        white_cp: int | None,
        white_mate: int | None,
        depth: int | None = None,
    ) -> None:
        node.eval_cp = white_cp
        node.eval_mate = white_mate
        node.eval_depth = depth

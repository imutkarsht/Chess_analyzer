"""Variation tree: branching, dedupe, LRU eviction, and recursive deletion."""

import chess

from src.backend.analysis.variation_tree import RecordStatus, VariationTree


def _play(tree, fen, uci):
    board = chess.Board(fen)
    move = chess.Move.from_uci(uci)
    san = board.san(move)
    board.push(move)
    return tree.record_move(uci, san, board.fen())


def test_tree_extends_forks_dedupes_and_cycles():
    tree = VariationTree(chess.STARTING_FEN)

    first = _play(tree, chess.STARTING_FEN, "e2e4")
    assert first.status is RecordStatus.CREATED
    assert first.branch.name == "e4"
    assert first.branch.lane == 0

    second = _play(tree, first.node.fen, "e7e5")
    assert second.status is RecordStatus.EXTENDED
    assert second.branch is first.branch
    assert second.branch.tip is second.node

    tree.select_node(first.node)
    sicilian = _play(tree, first.node.fen, "c7c5")
    assert sicilian.status is RecordStatus.CREATED
    assert sicilian.branch.lane == 1
    assert sicilian.branch.fork_node is first.node

    # Re-selecting an existing edge only checks it out.
    tree.select_node(first.node)
    duplicate = _play(tree, first.node.fen, "c7c5")
    assert duplicate.status is RecordStatus.SELECTED
    assert tree.branch_count() == 2
    assert tree.path_to(duplicate.node)[-1].san == "c5"
    assert [node.san for node in tree.path_to(duplicate.node)] == ["", "e4", "c5"]

    # Alt+Up/Down cycles the alternatives at the nearest fork, tip to tip.
    tree.select_node(sicilian.node)
    assert tree.cycle_sibling(-1) is first.branch
    assert tree.active_node is first.branch.tip

    assert tree.rename_branch(sicilian.branch.branch_id, "  Sicilian  ")
    assert sicilian.branch.name == "Sicilian"
    assert tree.rename_branch(sicilian.branch.branch_id, "   ")
    assert sicilian.branch.name == "c5"


def test_lru_eviction_is_silent_and_recursive():
    tree = VariationTree(chess.STARTING_FEN)

    e4 = _play(tree, chess.STARTING_FEN, "e2e4")
    tree.select_node(tree.root)
    d4 = _play(tree, chess.STARTING_FEN, "d2d4")
    tree.select_node(tree.root)
    c4 = _play(tree, chess.STARTING_FEN, "c2c4")

    # Give the d4 branch a nested continuation so replacing it is destructive.
    tree.select_node(d4.node)
    d5 = _play(tree, d4.node.fen, "d7d5")
    tree.select_node(e4.node)
    tree.select_node(c4.node)
    tree.select_node(tree.root)

    replaced = tree.record_move(
        "g1f3",
        "Nf3",
        "rnbqkbnr/pppppppp/8/8/8/5N2/PPPPPPPP/RNBQKB1R b KQkq - 1 1",
    )
    assert replaced.status is RecordStatus.EVICTED
    assert replaced.evicted_name == "d4"
    assert d4.branch not in tree.branches
    assert tree.find_node(d5.node.node_id) is None
    assert [branch.name for branch in tree.branches] == ["e4", "c4", "Nf3"]

    assert tree.delete_branch(e4.branch.branch_id) is True
    assert tree.branch_count() == 2
    assert all(node.san != "e4" for node in tree.all_nodes())

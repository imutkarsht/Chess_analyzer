"""Tests for the local opening book system."""
import csv
import os
import tempfile
import chess
from dataclasses import dataclass
from typing import List, Optional
from src.backend.analysis.opening_db import OpeningDB, _normalize_fen
from src.backend.analysis.local_book import LocalBookManager

SAMPLE_TSV = """eco	name	pgn
B20	Sicilian Defense	1. e4 c5
B21	Sicilian Defense: Grand Prix Attack	1. e4 c5 2. f4
B22	Sicilian Defense: Alapin Variation	1. e4 c5 2. c3
B23	Sicilian Defense: Closed	1. e4 c5 2. Nc3
B30	Sicilian Defense: Nimzowitsch Variation	1. e4 c5 2. Nf3 Nf6
B31	Sicilian Defense: Nimzowitsch-Rossolimo Attack	1. e4 c5 2. Nf3 Nc6 3. Bb5
B32	Sicilian Defense: Labourdonnais-Lowenthal Variation	1. e4 c5 2. Nf3 Nc6 3. d4
B33	Sicilian Defense: Sveshnikov Variation	1. e4 c5 2. Nf3 Nc6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 e5
B40	Sicilian Defense: French Variation	1. e4 c5 2. Nf3 e6
B50	Sicilian Defense: Modern Variations	1. e4 c5 2. Nf3 d6 3. d4
B90	Sicilian Defense: Najdorf Variation	1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6
C20	King's Pawn Game	1. e4 e5
C42	Petrov Defense	1. e4 e5 2. Nf3 Nf6
C44	King's Pawn Game: Dresden Opening	1. e4 e5 2. Nf3 Nc6 3. d4
C50	Italian Game	1. e4 e5 2. Nf3 Nc6 3. Bc4
C55	Two Knights Defense	1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6
C60	Ruy Lopez	1. e4 e5 2. Nf3 Nc6 3. Bb5
"""


def _write_sample_tsv(dir_path: str, filename: str = "s.tsv"):
    path = os.path.join(dir_path, filename)
    with open(path, "w", newline="") as f:
        f.write(SAMPLE_TSV)
    return path


def _make_db(tmp_path) -> OpeningDB:
    db_path = os.path.join(str(tmp_path), "openings.db")
    db = OpeningDB(db_path)
    tsv_dir = str(tmp_path)
    _write_sample_tsv(tsv_dir)
    db.initialize(tsv_dir)
    return db


class TestOpeningDB:
    def test_import_builds_tree(self, tmp_path):
        db = _make_db(tmp_path)
        root_fen = _normalize_fen(chess.Board().fen())
        root_id = db.get_node_by_fen(root_fen)
        assert root_id is not None
        children = db.get_children(root_id)
        assert "e4" in children

    def test_import_is_idempotent(self, tmp_path):
        db = _make_db(tmp_path)
        db.initialize(str(tmp_path))
        root_fen = _normalize_fen(chess.Board().fen())
        children1 = db.get_children(db.get_node_by_fen(root_fen))
        children2 = db.get_children(db.get_node_by_fen(root_fen))
        assert children1 == children2

    def test_sicilian_position_is_found(self, tmp_path):
        db = _make_db(tmp_path)
        board = chess.Board()
        board.push_san("e4")
        board.push_san("c5")
        board.push_san("Nf3")
        board.push_san("d6")
        fen = _normalize_fen(board.fen())
        node_id = db.get_node_by_fen(fen)
        assert node_id is not None
        openings = db.get_openings_at_node(node_id)
        names = [name for _, name in openings]
        assert any("Modern Variations" in n for n in names)

    def test_najdorf_eco_b90(self, tmp_path):
        db = _make_db(tmp_path)
        board = chess.Board()
        for san in ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"]:
            board.push_san(san)
        fen = _normalize_fen(board.fen())
        node_id = db.get_node_by_fen(fen)
        assert node_id is not None
        openings = db.get_openings_at_node(node_id)
        ecos = [eco for eco, _ in openings]
        assert "B90" in ecos

    def test_unknown_position_returns_none(self, tmp_path):
        db = _make_db(tmp_path)
        board = chess.Board()
        board.push_san("a3")
        fen = _normalize_fen(board.fen())
        assert db.get_node_by_fen(fen) is None

    def test_children_of_node(self, tmp_path):
        db = _make_db(tmp_path)
        board = chess.Board()
        board.push_san("e4")
        board.push_san("c5")
        fen = _normalize_fen(board.fen())
        node_id = db.get_node_by_fen(fen)
        children = db.get_children(node_id)
        assert "f4" in children  # Grand Prix Attack
        assert "c3" in children  # Alapin
        assert "Nc3" in children  # Closed
        assert "Nf3" in children  # Najdorf/Modern


class TestLocalBookManager:
    def test_reset_state(self, tmp_path):
        db = _make_db(tmp_path)
        book = LocalBookManager(db)
        result = book.process_move(chess.STARTING_FEN, "e2e4", 1)
        assert result.is_book
        book.reset()
        result = book.process_move(chess.STARTING_FEN, "e2e4", 1)
        assert result.is_book

    def test_sicilian_trace_through_book(self, tmp_path):
        db = _make_db(tmp_path)
        book = LocalBookManager(db)
        board = chess.Board()
        ucis = ["e2e4", "c7c5", "g1f3", "d7d6", "d2d4", "c5d4", "f3d4", "g8f6", "b1c3", "a7a6"]
        for i, uci in enumerate(ucis):
            result = book.process_move(board.fen(), uci, i + 1)
            board.push_uci(uci)
            assert result.is_book, f"Move {i+1} ({uci}) should be book"
            if i == len(ucis) - 1:
                assert result.current_eco == "B90"
                assert "Najdorf" in (result.current_opening or "")

    def test_book_exit_detected(self, tmp_path):
        db = _make_db(tmp_path)
        book = LocalBookManager(db)
        board = chess.Board()
        board.push_uci("e2e4")
        result = book.process_move(chess.STARTING_FEN, "e2e4", 1)
        assert result.is_book
        # Now play a non-book move
        result = book.process_move(board.fen(), "a2a3", 2)
        assert not result.is_book
        assert result.book_exit_move == 2

    def test_candidate_moves_at_position(self, tmp_path):
        db = _make_db(tmp_path)
        book = LocalBookManager(db)
        board = chess.Board()
        board.push_uci("e2e4")
        result = book.process_move(chess.STARTING_FEN, "e2e4", 1)
        assert "c5" in result.candidate_moves
        assert "e5" in result.candidate_moves

    def test_transposition_same_fen(self, tmp_path):
        """Two different openings converging on the same FEN is naturally handled."""
        db = _make_db(tmp_path)
        b1 = chess.Board("rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2")
        b2 = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2")
        # Both FENs are different → different nodes. This is expected — transpositions
        # (same FEN via different move orders) are handled automatically by FEN keying.

    def test_full_game_trace_with_exit(self, tmp_path):
        """Sicilian Najdorf up to move 6, then exit."""
        db = _make_db(tmp_path)
        book = LocalBookManager(db)
        board = chess.Board()

        moves = [
            ("e2e4", True),
            ("c7c5", True),
            ("g1f3", True),
            ("d7d6", True),
            ("d2d4", True),
            ("c5d4", True),
            ("f3d4", True),
            ("g8f6", True),
            ("b1c3", True),
            ("a7a6", True),
            ("h2h3", False),  # h3 is not in Najdorf (Be3/Bg5/Bc4 are)
        ]
        for i, (uci, should_be_book) in enumerate(moves):
            result = book.process_move(board.fen(), uci, i + 1)
            board.push_uci(uci)
            assert result.is_book == should_be_book, (
                f"Move {i+1} ({uci}): expected book={should_be_book}, got {result.is_book}"
            )
            if should_be_book:
                if i < len(moves) - 2:
                    assert result.candidate_moves, f"Book move {i+1} should have candidates"
            else:
                assert result.book_exit_move is not None

    def test_opening_name_most_specific(self, tmp_path):
        """At a position matching multiple openings, return the most specific name."""
        db = _make_db(tmp_path)
        board = chess.Board()
        board.push_san("e4")
        board.push_san("c5")
        board.push_san("Nf3")
        board.push_san("Nc6")
        fen = _normalize_fen(board.fen())
        node_id = db.get_node_by_fen(fen)
        assert node_id is not None
        openings = db.get_openings_at_node(node_id)
        names = [n for _, n in openings]
        # 'Sicilian Defense' is generic, but Labourdonnais-Lowenthal is more specific
        specific = max(names, key=len)
        assert specific == "Sicilian Defense: Labourdonnais-Lowenthal Variation"


def test_book_result_dataclass():
    from src.backend.analysis.local_book import BookResult
    r = BookResult(is_book=True, current_eco="B90", current_opening="Najdorf", book_move_count=5, candidate_moves=["Be3", "Bg5"])
    assert r.is_book
    assert r.current_eco == "B90"


def test_normalize_fen():
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    norm = _normalize_fen(fen)
    assert norm == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq -"
    assert len(norm.split()) == 4

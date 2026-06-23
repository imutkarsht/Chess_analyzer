"""Local opening database built from bundled Lichess ECO TSV files."""
import sqlite3
import csv
import glob
import os
import chess
from typing import List, Optional, Tuple


def _normalize_fen(fen: str) -> str:
    """Strip halfmove clock and fullmove number — keep position-only key."""
    return " ".join(fen.split()[:4])


class OpeningDB:
    """SQLite-backed opening tree keyed by normalized FEN."""

    SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS opening_book_metadata (
        version TEXT PRIMARY KEY,
        imported_at DATETIME
    );

    CREATE TABLE IF NOT EXISTS opening_nodes (
        id INTEGER PRIMARY KEY,
        fen TEXT NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS opening_edges (
        parent_id INTEGER NOT NULL REFERENCES opening_nodes(id),
        child_id INTEGER NOT NULL REFERENCES opening_nodes(id),
        move_san TEXT NOT NULL,
        PRIMARY KEY (parent_id, move_san),
        UNIQUE (parent_id, child_id)
    );

    CREATE TABLE IF NOT EXISTS node_openings (
        node_id INTEGER NOT NULL REFERENCES opening_nodes(id),
        eco TEXT NOT NULL,
        opening_name TEXT NOT NULL,
        PRIMARY KEY (node_id, eco)
    );
    """

    INDEXES_SQL = [
        "CREATE INDEX IF NOT EXISTS idx_edges_child ON opening_edges(child_id)",
        "CREATE INDEX IF NOT EXISTS idx_node_openings_name ON node_openings(opening_name)",
        "CREATE INDEX IF NOT EXISTS idx_nodes_fen ON opening_nodes(fen)",
    ]

    CURRENT_VERSION = "lichess-eco-1.0"

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self):
        """Open or create the database and ensure schema exists."""
        if self._conn is not None:
            return
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self.SCHEMA_SQL)
        for idx in self.INDEXES_SQL:
            self._conn.execute(idx)
        self._conn.commit()
        # Ensure WAL is checkpointed after schema checks/updates
        self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def is_populated(self) -> bool:
        """Return True if metadata table has a version row."""
        row = self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM opening_book_metadata"
        ).fetchone()
        return row["cnt"] > 0

    def initialize(self, tsv_dir: str):
        """Populate the database from TSV files if not already populated."""
        self.connect()
        if self.is_populated():
            return
        self._import_tsvs(tsv_dir)
        self._conn.execute(
            "INSERT INTO opening_book_metadata (version, imported_at) VALUES (?, datetime('now'))",
            (self.CURRENT_VERSION,),
        )
        self._conn.commit()

    # ---- TSV Import ----

    def _import_tsvs(self, tsv_dir: str):
        """Parse every TSV file and build the opening tree."""
        paths = sorted(glob.glob(os.path.join(tsv_dir, "*.tsv")))
        if not paths:
            raise FileNotFoundError(f"No TSV files found in {tsv_dir}")

        board = chess.Board()

        for path in paths:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter="\t")
                for row in reader:
                    if len(row) < 3:
                        continue
                    if row[0] == "eco":
                        continue
                    eco, name, pgn_str = row[0], row[1], row[2]
                    self._insert_variation(board, eco, name, pgn_str)

    def _insert_variation(self, board: chess.Board, eco: str, name: str, pgn_str: str):
        """Insert one opening variation into the tree."""
        board.reset()
        root_fen = _normalize_fen(board.fen())
        prev_id = self._get_or_create_node(root_fen)

        # Attach root opening for the starting position (covers all ECOs at root)
        self._upsert_node_opening(prev_id, eco, name)

        moves = self._parse_pgn_moves(pgn_str)
        for san in moves:
            try:
                board.push_san(san)
            except Exception:
                break
            cur_fen = _normalize_fen(board.fen())
            cur_id = self._get_or_create_node(cur_fen)
            self._upsert_edge(prev_id, cur_id, san)
            self._upsert_node_opening(cur_id, eco, name)
            prev_id = cur_id

    @staticmethod
    def _parse_pgn_moves(pgn_str: str) -> List[str]:
        """Extract SAN tokens from a PGN move string like '1. e4 c5 2. Nf3'."""
        tokens = pgn_str.split()
        moves = []
        for t in tokens:
            if t.endswith("."):
                continue
            moves.append(t)
        return moves

    # ---- Node / Edge CRUD ----

    def _get_or_create_node(self, fen: str) -> int:
        """Return node id for *fen*, inserting if missing."""
        row = self._conn.execute(
            "SELECT id FROM opening_nodes WHERE fen = ?", (fen,)
        ).fetchone()
        if row is not None:
            return row["id"]
        cur = self._conn.execute("INSERT INTO opening_nodes (fen) VALUES (?)", (fen,))
        return cur.lastrowid

    def _upsert_edge(self, parent_id: int, child_id: int, move_san: str):
        self._conn.execute(
            "INSERT OR IGNORE INTO opening_edges (parent_id, child_id, move_san) VALUES (?, ?, ?)",
            (parent_id, child_id, move_san),
        )

    def _upsert_node_opening(self, node_id: int, eco: str, name: str):
        self._conn.execute(
            "INSERT OR IGNORE INTO node_openings (node_id, eco, opening_name) VALUES (?, ?, ?)",
            (node_id, eco, name),
        )

    # ---- Lookups ----

    def get_node_by_fen(self, fen: str) -> Optional[int]:
        """Return node id for a normalized FEN, or None."""
        row = self._conn.execute(
            "SELECT id FROM opening_nodes WHERE fen = ?", (fen,)
        ).fetchone()
        return row["id"] if row is not None else None

    def get_openings_at_node(self, node_id: int) -> List[Tuple[str, str]]:
        """Return list of (eco, opening_name) for a given node."""
        rows = self._conn.execute(
            "SELECT eco, opening_name FROM node_openings WHERE node_id = ?", (node_id,)
        ).fetchall()
        return [(r["eco"], r["opening_name"]) for r in rows]

    def get_children(self, node_id: int) -> List[str]:
        """Return list of SAN moves available from this node."""
        rows = self._conn.execute(
            "SELECT move_san FROM opening_edges WHERE parent_id = ? ORDER BY move_san",
            (node_id,),
        ).fetchall()
        return [r["move_san"] for r in rows]

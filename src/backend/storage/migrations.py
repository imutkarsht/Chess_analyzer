"""
Database initialization, schema migrations, and indexing.
"""

import io
import json
import os
import sqlite3
from collections import Counter

import chess.pgn

from src.backend.storage.db_connection import get_db_connection
from src.backend.storage.models import MoveAnalysis
from src.backend.storage.schema_constants import CURRENT_SCHEMA_VERSION
from src.backend.storage.termination_detector import TerminationDetector
from src.utils.logger import logger


def _enrich_summary_with_tactics(
    summary_dict: dict,
    moves_data: list[dict],
    result: str,
    speed_category: str = "Blitz",
) -> tuple[dict, dict, dict]:
    from src.backend.analysis.tactics import analyze_game_tactics

    tactics_w = analyze_game_tactics(moves_data, "white", result, speed_category=speed_category)
    tactics_b = analyze_game_tactics(moves_data, "black", result, speed_category=speed_category)

    if "white" not in summary_dict or not isinstance(summary_dict["white"], dict):
        summary_dict["white"] = {}
    if "black" not in summary_dict or not isinstance(summary_dict["black"], dict):
        summary_dict["black"] = {}

    summary_dict["white"]["tactics"] = tactics_w
    summary_dict["black"]["tactics"] = tactics_b
    return summary_dict, tactics_w, tactics_b


def _create_pre_migration_backup(conn: sqlite3.Connection, db_path: str) -> None:
    if db_path != ":memory:" and os.path.exists(db_path) and os.path.getsize(db_path) > 0:
        backup_path = f"{db_path}.bak"
        try:
            with sqlite3.connect(backup_path) as bck:
                conn.backup(bck)
            logger.info("Created pre-migration database snapshot at %s", backup_path)
        except Exception as backup_err:
            logger.warning("Could not create pre-migration backup: %s", backup_err)


def _ensure_tables_and_columns(cursor: sqlite3.Cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id TEXT PRIMARY KEY,
            white TEXT,
            black TEXT,
            result TEXT,
            date TEXT,
            event TEXT,
            pgn TEXT,
            summary_json TEXT,
            timestamp REAL
        )
    """)

    new_columns = [
        ("white_elo", "TEXT"),
        ("black_elo", "TEXT"),
        ("time_control", "TEXT"),
        ("eco", "TEXT"),
        ("termination", "TEXT"),
        ("opening", "TEXT"),
        ("starting_fen", "TEXT"),
        ("source", "TEXT"),
        ("chess960", "INTEGER"),
        ("moves_json", "TEXT"),
        ("speed_category", "TEXT"),
        ("book_exit_ply", "INTEGER"),
        ("white_opening_acc", "REAL"),
        ("black_opening_acc", "REAL"),
        ("white_middlegame_acc", "REAL"),
        ("black_middlegame_acc", "REAL"),
        ("white_endgame_acc", "REAL"),
        ("black_endgame_acc", "REAL"),
        ("white_pieces_hung", "INTEGER DEFAULT 0"),
        ("black_pieces_hung", "INTEGER DEFAULT 0"),
        ("white_brilliant_count", "INTEGER DEFAULT 0"),
        ("black_brilliant_count", "INTEGER DEFAULT 0"),
        ("white_great_count", "INTEGER DEFAULT 0"),
        ("black_great_count", "INTEGER DEFAULT 0"),
        ("termination_mode", "TEXT"),
    ]

    cursor.execute("PRAGMA table_info(games)")
    existing_cols = {row[1] for row in cursor.fetchall()}

    for col_name, col_type in new_columns:
        if col_name not in existing_cols:
            try:
                logger.info("Migrating DB: Adding column %s", col_name)
                cursor.execute(f"ALTER TABLE games ADD COLUMN {col_name} {col_type}")
            except Exception as e:
                logger.error("Failed to add column %s: %s", col_name, e)


def _backfill_termination_mode(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        "SELECT id, result, termination, pgn, starting_fen, chess960 "
        "FROM games WHERE termination_mode IS NULL OR termination_mode = ''"
    )
    rows_to_migrate = cursor.fetchall()
    if not rows_to_migrate:
        return

    for gid, res, term, pgn_str, s_fen, is_960 in rows_to_migrate:
        try:
            game = chess.pgn.read_game(io.StringIO(pgn_str)) if pgn_str else None
            headers = dict(game.headers) if game else {"Result": res, "Termination": term or ""}
            moves = []
            if game:
                for ply_idx, node in enumerate(game.mainline()):
                    moves.append(
                        MoveAnalysis(
                            move_number=ply_idx // 2 + 1,
                            ply=ply_idx + 1,
                            san=node.san(),
                            uci=node.move.uci(),
                            fen_before="",
                        )
                    )
            mode, desc = TerminationDetector.detect_termination(
                headers=headers,
                moves=moves,
                starting_fen=s_fen,
                chess960=bool(is_960),
            )
            clean_term = (
                desc if (not term or term.strip().lower() in ("", "normal", "unknown")) else term
            )
            cursor.execute(
                "UPDATE games SET termination_mode = ?, termination = ? WHERE id = ?",
                (mode, clean_term, gid),
            )
        except Exception as e:
            logger.error("Failed to backfill termination for game %s: %s", gid, e)


def _create_performance_indexes(cursor: sqlite3.Cursor) -> None:
    indexes = [
        (
            "idx_games_white_lower",
            "CREATE INDEX IF NOT EXISTS idx_games_white_lower ON games(LOWER(white))",
        ),
        (
            "idx_games_black_lower",
            "CREATE INDEX IF NOT EXISTS idx_games_black_lower ON games(LOWER(black))",
        ),
        (
            "idx_games_timestamp",
            "CREATE INDEX IF NOT EXISTS idx_games_timestamp ON games(timestamp DESC)",
        ),
        (
            "idx_games_speed",
            "CREATE INDEX IF NOT EXISTS idx_games_speed ON games(speed_category)",
        ),
        (
            "idx_games_date",
            "CREATE INDEX IF NOT EXISTS idx_games_date ON games(date)",
        ),
        (
            "idx_games_opening",
            "CREATE INDEX IF NOT EXISTS idx_games_opening ON games(opening)",
        ),
        (
            "idx_games_source",
            "CREATE INDEX IF NOT EXISTS idx_games_source ON games(source)",
        ),
    ]
    for idx_name, idx_sql in indexes:
        try:
            cursor.execute(idx_sql)
        except Exception as e:
            logger.warning("Could not create index %s: %s", idx_name, e)


def _backfill_legacy_tactics(cursor: sqlite3.Cursor) -> None:
    try:
        cursor.execute(
            "SELECT id, moves_json, result, speed_category, summary_json "
            "FROM games "
            "WHERE moves_json IS NOT NULL AND moves_json != '' "
            "  AND (summary_json IS NULL OR summary_json = '' OR summary_json NOT LIKE '%hung_pieces_details%')"
        )
        rows = cursor.fetchall()
        if not rows:
            return

        logger.info("Migrating DB: Backfilling legacy tactics for %d games...", len(rows))

        for gid, m_json, res, speed, s_json in rows:
            try:
                moves_data = json.loads(m_json)
                s_cat = speed or "Blitz"
                raw_summary = json.loads(s_json) if s_json else {}
                s_dict, tactics_w, tactics_b = _enrich_summary_with_tactics(
                    raw_summary, moves_data, res, speed_category=s_cat
                )

                w_hanging = tactics_w.get("hanging_metrics", {})
                b_hanging = tactics_b.get("hanging_metrics", {})
                w_phase = tactics_w.get("phase_accuracies", {})
                b_phase = tactics_b.get("phase_accuracies", {})
                w_counts = Counter(
                    b.get("classification") for b in tactics_w.get("brilliancies", [])
                )
                b_counts = Counter(
                    b.get("classification") for b in tactics_b.get("brilliancies", [])
                )
                b_exit = tactics_w.get("book_exit_ply")

                cursor.execute(
                    """
                    UPDATE games SET
                        summary_json = ?,
                        speed_category = COALESCE(speed_category, ?),
                        book_exit_ply = ?,
                        white_opening_acc = ?,
                        black_opening_acc = ?,
                        white_middlegame_acc = ?,
                        black_middlegame_acc = ?,
                        white_endgame_acc = ?,
                        black_endgame_acc = ?,
                        white_pieces_hung = ?,
                        black_pieces_hung = ?,
                        white_brilliant_count = ?,
                        black_brilliant_count = ?,
                        white_great_count = ?,
                        black_great_count = ?
                    WHERE id = ?
                    """,
                    (
                        json.dumps(s_dict),
                        s_cat,
                        b_exit,
                        w_phase.get("opening"),
                        b_phase.get("opening"),
                        w_phase.get("middlegame"),
                        b_phase.get("middlegame"),
                        w_phase.get("endgame"),
                        b_phase.get("endgame"),
                        w_hanging.get("total_hung", 0),
                        b_hanging.get("total_hung", 0),
                        w_counts.get("Brilliant", 0),
                        b_counts.get("Brilliant", 0),
                        w_counts.get("Great", 0),
                        b_counts.get("Great", 0),
                        gid,
                    ),
                )
            except Exception as exc:
                logger.warning("Failed backfilling tactics for game %s: %s", gid, exc)

        logger.info("DB Migration: Successfully backfilled tactics for %d legacy games.", len(rows))
    except Exception as e:
        logger.warning("Could not execute legacy tactics backfill: %s", e)


def _init_cache_tables(cursor: sqlite3.Cursor) -> None:
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_game_cache (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                white TEXT NOT NULL,
                black TEXT NOT NULL,
                result TEXT NOT NULL,
                date TEXT NOT NULL,
                pgn TEXT NOT NULL,
                white_elo TEXT,
                black_elo TEXT,
                time_class TEXT,
                move_count INTEGER,
                opening TEXT,
                cached_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS explorer_cache (
                fen TEXT PRIMARY KEY,
                response_json TEXT NOT NULL,
                cached_at REAL NOT NULL
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_api_cache_date ON api_game_cache(source, date)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_api_cache_white ON api_game_cache(LOWER(white))"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_api_cache_black ON api_game_cache(LOWER(black))"
        )
    except Exception as e:
        logger.error("Failed to initialize API/Explorer cache tables: %s", e)


def init_db(db_path: str) -> None:
    """
    Initializes database tables, executes schema migrations if needed,
    creates performance indexes, and performs integrity checks.
    """
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            # Ensure basic table exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id TEXT PRIMARY KEY,
                    white TEXT,
                    black TEXT,
                    result TEXT,
                    date TEXT,
                    event TEXT,
                    pgn TEXT,
                    summary_json TEXT,
                    timestamp REAL
                )
            """)

            # Check schema version
            cursor.execute("PRAGMA user_version")
            user_ver_row = cursor.fetchone()
            current_version = user_ver_row[0] if user_ver_row else 0

            if current_version < CURRENT_SCHEMA_VERSION:
                _create_pre_migration_backup(conn, db_path)
                _ensure_tables_and_columns(cursor)
                _backfill_termination_mode(cursor)
                _create_performance_indexes(cursor)
                cursor.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")

            _backfill_legacy_tactics(cursor)

            # Check database integrity on launch
            try:
                cursor.execute("PRAGMA quick_check(1)")
                check_res = cursor.fetchone()
                if check_res and check_res[0] != "ok":
                    logger.warning("Database quick_check warning: %s", check_res[0])
            except Exception as e:
                logger.debug("Could not execute PRAGMA quick_check: %s", e)

            _init_cache_tables(cursor)
            conn.commit()
    except Exception as e:
        logger.error("Failed to initialize game history DB: %s", e)

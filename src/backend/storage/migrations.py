"""
Database initialization, schema migrations, and indexing.
"""

import hashlib
import io
import json
import os
import sqlite3
from collections import Counter

import chess.pgn

from src.backend.storage.db_connection import get_db_connection
from src.backend.storage.models import MoveAnalysis
from src.backend.storage.pgn_parser import normalize_lichess_site_for_id
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
        ("ai_summary", "TEXT"),
        ("move_count", "INTEGER"),
        ("last_fen", "TEXT"),
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


def _backfill_list_metadata(cursor: sqlite3.Cursor) -> None:
    """Populate ``move_count``/``last_fen`` for rows saved before they existed.

    List rows are rendered from light columns only, so any value that would
    otherwise require parsing ``moves_json`` must be materialised once here.
    """
    cursor.execute(
        "SELECT id, moves_json, summary_json FROM games "
        "WHERE move_count IS NULL OR last_fen IS NULL"
    )
    rows = cursor.fetchall()
    if not rows:
        return

    import json

    updates: list[tuple[int | None, str | None, str]] = []
    for game_id, moves_json, summary_json in rows:
        move_count: int | None = None
        last_fen: str | None = None

        moves_data: list = []
        if moves_json:
            try:
                parsed = json.loads(moves_json)
                if isinstance(parsed, list):
                    moves_data = parsed
            except (json.JSONDecodeError, TypeError, ValueError):
                moves_data = []

        if moves_data:
            move_count = (len(moves_data) + 1) // 2
        elif summary_json:
            try:
                total_plies = int(json.loads(summary_json).get("total_moves") or 0)
            except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
                total_plies = 0
            if total_plies > 0:
                move_count = (total_plies + 1) // 2

        if moves_data:
            last_fen = _fen_after_last_move(moves_data[-1])

        if move_count is not None or last_fen is not None:
            updates.append((move_count, last_fen, game_id))

    if updates:
        cursor.executemany(
            "UPDATE games SET move_count = COALESCE(?, move_count), "
            "last_fen = COALESCE(?, last_fen) WHERE id = ?",
            updates,
        )
        logger.info("Migrating DB: backfilled list metadata for %d games", len(updates))


def _fen_after_last_move(move: dict) -> str | None:
    """Return the FEN after ``move`` using its pre-move FEN and UCI move."""
    import chess

    fen_before = move.get("fen_before")
    uci = move.get("uci")
    if not fen_before or not uci:
        return None
    try:
        board = chess.Board(fen_before)
        board.push(chess.Move.from_uci(uci))
        return board.fen()
    except (ValueError, AssertionError):
        return None


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


def _game_richness(
    summary_json: str | None,
    ai_summary: str | None,
    timestamp: float | None,
) -> tuple[int, int, int, float]:
    """Rank duplicate rows so the analysed copy always survives a merge."""
    try:
        summary = json.loads(summary_json or "{}")
    except (TypeError, ValueError):
        summary = {}

    status = str(summary.get("analysis_status") or "")
    status_rank = {
        "completed": 4,
        "paused": 3,
        "in_progress": 2,
        "not_started": 1,
    }.get(status, 0)
    try:
        analyzed_moves = int(summary.get("analyzed_moves") or 0)
    except (TypeError, ValueError):
        analyzed_moves = 0
    try:
        saved_at = float(timestamp or 0.0)
    except (TypeError, ValueError):
        saved_at = 0.0

    return status_rank, analyzed_moves, int(bool(ai_summary)), saved_at


def _deduplicate_lichess_games(cursor: sqlite3.Cursor) -> None:
    """
    Merge history rows that differ only in the Lichess Site URL spelling.

    Older rows were hashed with ``lichess.org/game/<id>`` while a later Load
    Game change produced ``lichess.org/<id>``, creating a second primary key
    for the same game. Re-keying to the normalized hash is idempotent.
    """
    try:
        cursor.execute(
            "SELECT id, pgn, summary_json, ai_summary, timestamp "
            "FROM games WHERE pgn LIKE '%lichess.org/%'"
        )
        rows = cursor.fetchall()
    except Exception as e:
        logger.warning("Could not scan Lichess games for duplicate cleanup: %s", e)
        return

    groups: dict[str, list[tuple]] = {}
    for row in rows:
        gid, pgn = row[0], row[1] or ""
        raw_id = hashlib.md5(pgn.encode("utf-8"), usedforsecurity=False).hexdigest()
        canonical_id = hashlib.md5(
            normalize_lichess_site_for_id(pgn).encode("utf-8"),
            usedforsecurity=False,
        ).hexdigest()

        # Leave imported games with a user-supplied/custom ID untouched.
        if gid not in (raw_id, canonical_id):
            continue
        groups.setdefault(canonical_id, []).append(row)

    merged = 0
    for canonical_id, group in groups.items():
        if len(group) == 1 and group[0][0] == canonical_id:
            continue

        keeper = max(group, key=lambda r: _game_richness(r[2], r[3], r[4]))
        keeper_id = keeper[0]

        if not keeper[3]:
            inherited_summary = next((r[3] for r in group if r[3]), None)
            if inherited_summary:
                cursor.execute(
                    "UPDATE games SET ai_summary = ? WHERE id = ?",
                    (inherited_summary, keeper_id),
                )

        for row in group:
            if row[0] != keeper_id:
                cursor.execute("DELETE FROM games WHERE id = ?", (row[0],))

        if keeper_id != canonical_id:
            cursor.execute(
                "UPDATE games SET id = ? WHERE id = ?",
                (canonical_id, keeper_id),
            )

        if len(group) > 1:
            merged += len(group) - 1
            logger.info(
                "DB Migration: merged %d duplicate row(s) for Lichess game %s",
                len(group) - 1,
                canonical_id,
            )
        else:
            logger.debug("DB Migration: re-keyed Lichess game %s", canonical_id)

    if merged:
        logger.info("DB Migration: removed %d duplicate Lichess game row(s).", merged)


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
        (
            "idx_games_move_count",
            "CREATE INDEX IF NOT EXISTS idx_games_move_count ON games(move_count)",
        ),
    ]
    for idx_name, idx_sql in indexes:
        try:
            cursor.execute(idx_sql)
        except Exception as e:
            logger.warning("Could not create index %s: %s", idx_name, e)


def _backfill_analysis_status(cursor: sqlite3.Cursor) -> None:
    """Persist analysis status into ``summary_json`` for rows saved before it.

    List rows no longer load ``moves_json``, so status must come from the stored
    summary. Runs on every startup until no row is missing it, which also heals
    databases that were already migrated past an earlier schema version.
    """
    cursor.execute(
        "SELECT id, moves_json, summary_json FROM games "
        "WHERE summary_json IS NULL OR summary_json NOT LIKE '%analysis_status%'"
    )
    rows = cursor.fetchall()
    if not rows:
        return

    import json

    updates: list[tuple[str, str]] = []
    for game_id, moves_json, summary_json in rows:
        try:
            summary = json.loads(summary_json) if summary_json else {}
        except (json.JSONDecodeError, TypeError, ValueError):
            summary = {}
        if not isinstance(summary, dict):
            summary = {}
        if summary.get("analysis_status"):
            continue

        moves_data: list = []
        if moves_json:
            try:
                parsed = json.loads(moves_json)
                if isinstance(parsed, list):
                    moves_data = parsed
            except (json.JSONDecodeError, TypeError, ValueError):
                moves_data = []

        total = len(moves_data)
        analyzed = sum(1 for move in moves_data if move.get("classification"))

        if total == 0 or analyzed == 0:
            status = "not_started"
        elif analyzed < total:
            status = "paused"
        else:
            # Mirrors GameAnalysis.status: a fully analysed game is complete
            # even when the stored summary predates accuracy tracking.
            status = "completed"

        summary["analysis_status"] = status
        summary["analyzed_moves"] = analyzed
        summary.setdefault("total_moves", total)
        updates.append((json.dumps(summary), game_id))

    if updates:
        cursor.executemany("UPDATE games SET summary_json = ? WHERE id = ?", updates)
        logger.info("Migrating DB: backfilled analysis status for %d games", len(updates))


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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_profile_cache (
                platform TEXT NOT NULL,
                username_key TEXT NOT NULL,
                username TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                avatar_url TEXT,
                avatar_blob BLOB,
                avatar_mime TEXT,
                fetched_at REAL NOT NULL,
                PRIMARY KEY (platform, username_key)
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
                _backfill_list_metadata(cursor)
                _deduplicate_lichess_games(cursor)
                _create_performance_indexes(cursor)
                cursor.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")

            _backfill_legacy_tactics(cursor)
            _backfill_analysis_status(cursor)

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

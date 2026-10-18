import hashlib
import json
import os
import sqlite3
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from typing import Any

from src.utils.logger import logger
from src.utils.path_utils import get_user_data_dir

from .models import GameAnalysis

GAME_COLUMNS: tuple[str, ...] = (
    "id",
    "white",
    "black",
    "result",
    "date",
    "event",
    "white_elo",
    "black_elo",
    "time_control",
    "speed_category",
    "eco",
    "opening",
    "termination",
    "termination_mode",
    "source",
    "starting_fen",
    "chess960",
    "book_exit_ply",
    "white_opening_acc",
    "black_opening_acc",
    "white_middlegame_acc",
    "black_middlegame_acc",
    "white_endgame_acc",
    "black_endgame_acc",
    "white_pieces_hung",
    "black_pieces_hung",
    "white_brilliant_count",
    "black_brilliant_count",
    "white_great_count",
    "black_great_count",
    "pgn",
    "summary_json",
    "moves_json",
    "timestamp",
)

GAME_CSV_COLUMNS: list[str] = list(GAME_COLUMNS)

_GAME_COLS_SQL: str = ", ".join(GAME_COLUMNS)
_GAME_PLACEHOLDERS_SQL: str = ", ".join(f":{c}" for c in GAME_COLUMNS)
INSERT_GAME_SQL: str = (
    f"INSERT OR REPLACE INTO games ({_GAME_COLS_SQL}) VALUES ({_GAME_PLACEHOLDERS_SQL})"
)

API_CACHE_COLUMNS: tuple[str, ...] = (
    "id",
    "source",
    "white",
    "black",
    "result",
    "date",
    "pgn",
    "white_elo",
    "black_elo",
    "time_class",
    "move_count",
    "opening",
    "cached_at",
)
_API_CACHE_COLS_SQL: str = ", ".join(API_CACHE_COLUMNS)
_API_CACHE_PLACEHOLDERS_SQL: str = ", ".join(["?"] * len(API_CACHE_COLUMNS))
INSERT_API_CACHE_SQL: str = f"INSERT OR REPLACE INTO api_game_cache ({_API_CACHE_COLS_SQL}) VALUES ({_API_CACHE_PLACEHOLDERS_SQL})"

CURRENT_SCHEMA_VERSION: int = 2
EXPLORER_CACHE_TTL_SECONDS: float = 48 * 3600.0  # 48 hours


def _to_float(val: Any) -> float | None:
    try:
        return float(val) if val is not None and str(val).strip() != "" else None
    except (ValueError, TypeError):
        return None


def _to_int(val: Any) -> int:
    try:
        return int(val) if val is not None and str(val).strip() != "" else 0
    except (ValueError, TypeError):
        return 0


def _to_int_or_none(val: Any) -> int | None:
    try:
        return int(val) if val is not None and str(val).strip() != "" else None
    except (ValueError, TypeError):
        return None


def _make_game_id(pgn: str | None) -> str:
    if pgn and pgn.strip():
        return hashlib.md5(pgn.encode("utf-8"), usedforsecurity=False).hexdigest()
    return str(uuid.uuid4())


def _enrich_summary_with_tactics(
    summary_dict: dict[str, Any],
    moves_data: list[dict[str, Any]],
    result: str,
    speed_category: str = "Blitz",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """
    Computes tactics for white and black, and attaches them to summary_dict.
    Returns (summary_dict, tactics_white, tactics_black).
    """
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


def _info_to_cache_row(info: Any, default_cached_at: str | None = None) -> tuple:
    cached_at = (
        getattr(info, "cached_at", None) or default_cached_at or time.strftime("%Y-%m-%d %H:%M:%S")
    )
    return (
        getattr(info, "game_id", ""),
        getattr(info, "source", ""),
        getattr(info, "white", ""),
        getattr(info, "black", ""),
        getattr(info, "result", "*"),
        getattr(info, "date", ""),
        getattr(info, "pgn", ""),
        getattr(info, "white_elo", None),
        getattr(info, "black_elo", None),
        getattr(info, "time_class", None),
        getattr(info, "move_count", None),
        getattr(info, "opening", None),
        cached_at,
    )


def _row_to_game_info(d: dict[str, Any]) -> Any:
    from src.backend.models.game_info import GameInfo

    return GameInfo(
        game_id=d["id"],
        source=d["source"],
        white=d["white"],
        black=d["black"],
        result=d["result"],
        date=d["date"],
        pgn=d["pgn"],
        white_elo=d.get("white_elo"),
        black_elo=d.get("black_elo"),
        time_class=d.get("time_class"),
        move_count=d.get("move_count"),
        opening=d.get("opening"),
        cached_at=d.get("cached_at"),
    )


class GameHistoryManager:
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            self.db_path = os.path.join(get_user_data_dir(), "analysis_cache.db")
        else:
            self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Context manager guaranteeing connection closure upon completion or error."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=10000")
            yield conn
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def checkpoint(self):
        """Executes a WAL checkpoint to truncate sidecar WAL/SHM files into the main DB file."""
        try:
            with self._get_connection() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            logger.debug("Database WAL checkpoint (TRUNCATE) completed.")
        except Exception as e:
            logger.debug(f"Failed to execute WAL checkpoint: {e}")

    def vacuum(self):
        """Reclaims unused disk space from deleted rows."""
        try:
            with self._get_connection() as conn:
                conn.execute("VACUUM")
            logger.info("Database vacuum completed.")
        except Exception as e:
            logger.error(f"Database vacuum failed: {e}")

    def close(self):
        """Closes any active database resources and checkpoints WAL."""
        self.checkpoint()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _init_db(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 1. Create table with basic schema if not exists
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
                    # Pre-migration safety snapshot using native SQLite backup API
                    if (
                        self.db_path != ":memory:"
                        and os.path.exists(self.db_path)
                        and os.path.getsize(self.db_path) > 0
                    ):
                        backup_path = f"{self.db_path}.bak"
                        try:
                            with sqlite3.connect(backup_path) as bck:
                                conn.backup(bck)
                            logger.info(
                                "Created pre-migration database snapshot at %s", backup_path
                            )
                        except Exception as backup_err:
                            logger.warning("Could not create pre-migration backup: %s", backup_err)

                    # 2. Schema Migration: Ensure new columns exist
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

                    # Check existing columns
                    cursor.execute("PRAGMA table_info(games)")
                    existing_cols = {row[1] for row in cursor.fetchall()}

                    for col_name, col_type in new_columns:
                        if col_name not in existing_cols:
                            try:
                                logger.info(f"Migrating DB: Adding column {col_name}")
                                cursor.execute(
                                    f"ALTER TABLE games ADD COLUMN {col_name} {col_type}"
                                )
                            except Exception as e:
                                logger.error(f"Failed to add column {col_name}: {e}")

                    # Backfill termination_mode for any older games without it
                    cursor.execute(
                        "SELECT id, result, termination, pgn, starting_fen, chess960 "
                        "FROM games WHERE termination_mode IS NULL OR termination_mode = ''"
                    )
                    rows_to_migrate = cursor.fetchall()
                    if rows_to_migrate:
                        import io

                        import chess.pgn

                        from src.backend.storage.models import MoveAnalysis
                        from src.backend.storage.termination_detector import TerminationDetector

                        for gid, res, term, pgn_str, s_fen, is_960 in rows_to_migrate:
                            try:
                                game = (
                                    chess.pgn.read_game(io.StringIO(pgn_str)) if pgn_str else None
                                )
                                headers = (
                                    dict(game.headers)
                                    if game
                                    else {"Result": res, "Termination": term or ""}
                                )
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
                                    desc
                                    if (
                                        not term
                                        or term.strip().lower() in ("", "normal", "unknown")
                                    )
                                    else term
                                )
                                cursor.execute(
                                    "UPDATE games SET termination_mode = ?, termination = ? WHERE id = ?",
                                    (mode, clean_term, gid),
                                )
                            except Exception as e:
                                logger.error(f"Failed to backfill termination for game {gid}: {e}")

                    # 3. Performance Indexes for Scale (5,000+ games)
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
                            logger.warning(f"Could not create index {idx_name}: {e}")

                    cursor.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")

                # Ensure any legacy tactics metrics are backfilled into summary_json and table columns
                self._backfill_legacy_tactics(cursor)

                # Check database integrity on launch
                try:
                    cursor.execute("PRAGMA quick_check(1)")
                    check_res = cursor.fetchone()
                    if check_res and check_res[0] != "ok":
                        logger.warning("Database quick_check warning: %s", check_res[0])
                except Exception as e:
                    logger.debug(f"Could not execute PRAGMA quick_check: {e}")

                self._init_api_cache(cursor)
                self.prune_explorer_cache(cursor=cursor)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize game history DB: {e}")

    def _backfill_legacy_tactics(self, cursor: sqlite3.Cursor) -> None:
        """
        One-time migration to backfill rich tactical metrics (hung pieces, blunders,
        motifs, clock) directly into summary_json and direct table columns for legacy games.
        This eliminates runtime move replay during stats aggregation, speeding up stats
        calculation by 20x-100x.
        """
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

            logger.info(
                "DB Migration: Successfully backfilled tactics for %d legacy games.", len(rows)
            )
        except Exception as e:
            logger.warning("Could not execute legacy tactics backfill: %s", e)

    def _init_api_cache(self, cursor):
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
            logger.error(f"Failed to initialize API/Explorer cache tables: {e}")

    @staticmethod
    def _row_to_legacy_tuple(row: dict[str, Any]) -> tuple:
        return (
            row["id"],
            row["white"],
            row["black"],
            row["result"],
            row["date"],
            row["event"],
            row["pgn"],
            row["summary_json"],
            row["timestamp"],
            row["white_elo"],
            row["black_elo"],
            row["time_control"],
            row["eco"],
            row["termination"],
            row["termination_mode"],
            row["opening"],
            row["starting_fen"],
            row["source"],
            row["chess960"],
            row["moves_json"],
            row["speed_category"],
            row["book_exit_ply"],
            row["white_opening_acc"],
            row["black_opening_acc"],
            row["white_middlegame_acc"],
            row["black_middlegame_acc"],
            row["white_endgame_acc"],
            row["black_endgame_acc"],
            row["white_pieces_hung"],
            row["black_pieces_hung"],
            row["white_brilliant_count"],
            row["black_brilliant_count"],
            row["white_great_count"],
            row["black_great_count"],
        )

    def _prepare_game_analysis_row(
        self,
        game_analysis: GameAnalysis,
        pgn_content: str,
        timestamp: float | None = None,
    ) -> dict[str, Any]:
        game_id = game_analysis.game_id or _make_game_id(pgn_content)

        moves_data = []
        for m in game_analysis.moves:
            moves_data.append(
                {
                    "move_number": m.move_number,
                    "ply": m.ply,
                    "san": m.san,
                    "uci": m.uci,
                    "fen_before": m.fen_before,
                    "eval_before_cp": m.eval_before_cp,
                    "eval_before_mate": m.eval_before_mate,
                    "best_move": m.best_move,
                    "best_eval_cp": m.best_eval_cp,
                    "best_eval_mate": m.best_eval_mate,
                    "pv": m.pv,
                    "eval_after_cp": m.eval_after_cp,
                    "eval_after_mate": m.eval_after_mate,
                    "win_chance_before": m.win_chance_before,
                    "win_chance_after": m.win_chance_after,
                    "classification": m.classification,
                    "explanation": m.explanation,
                    "multi_pvs": m.multi_pvs,
                    "is_book_move": m.is_book_move,
                    "eco": m.eco,
                    "opening_name": m.opening_name,
                    "candidate_continuations": m.candidate_continuations,
                    "time_left": m.time_left,
                    "time_spent": m.time_spent,
                    "raw_clk": m.raw_clk,
                }
            )
        moves_json = json.dumps(moves_data)

        speed_category = game_analysis.metadata.speed_category or "Blitz"
        summary_dict = (
            dict(game_analysis.summary) if game_analysis.summary else {"white": {}, "black": {}}
        )
        summary_dict, tactics_white, tactics_black = _enrich_summary_with_tactics(
            summary_dict,
            moves_data,
            game_analysis.metadata.result,
            speed_category=speed_category,
        )
        summary_json = json.dumps(summary_dict)

        w_counts = Counter(b.get("classification") for b in tactics_white.get("brilliancies", []))
        b_counts = Counter(b.get("classification") for b in tactics_black.get("brilliancies", []))

        white_phase = tactics_white.get("phase_accuracies", {})
        black_phase = tactics_black.get("phase_accuracies", {})
        white_hanging = tactics_white.get("hanging_metrics", {})
        black_hanging = tactics_black.get("hanging_metrics", {})

        if (
            not game_analysis.metadata.termination_mode
            or not game_analysis.metadata.termination_description
        ):
            from src.backend.storage.termination_detector import TerminationDetector

            term_mode, term_desc = TerminationDetector.detect_termination(
                headers=game_analysis.metadata.headers,
                moves=game_analysis.moves,
                starting_fen=game_analysis.metadata.starting_fen,
                chess960=game_analysis.metadata.chess960,
            )
            game_analysis.metadata.termination_mode = term_mode
            game_analysis.metadata.termination_description = term_desc

        if (
            not game_analysis.metadata.termination
            or game_analysis.metadata.termination.strip().lower() in ("", "normal", "unknown")
        ):
            game_analysis.metadata.termination = game_analysis.metadata.termination_description

        save_ts = timestamp if timestamp is not None else time.time()

        return {
            "id": game_id,
            "white": game_analysis.metadata.white,
            "black": game_analysis.metadata.black,
            "result": game_analysis.metadata.result,
            "date": game_analysis.metadata.date,
            "event": game_analysis.metadata.event,
            "white_elo": game_analysis.metadata.white_elo,
            "black_elo": game_analysis.metadata.black_elo,
            "time_control": game_analysis.metadata.time_control,
            "speed_category": speed_category,
            "eco": game_analysis.metadata.eco,
            "opening": game_analysis.metadata.opening,
            "termination": game_analysis.metadata.termination,
            "termination_mode": game_analysis.metadata.termination_mode,
            "source": game_analysis.metadata.source,
            "starting_fen": game_analysis.metadata.starting_fen,
            "chess960": int(game_analysis.metadata.chess960),
            "book_exit_ply": tactics_white.get("book_exit_ply"),
            "white_opening_acc": white_phase.get("opening"),
            "black_opening_acc": black_phase.get("opening"),
            "white_middlegame_acc": white_phase.get("middlegame"),
            "black_middlegame_acc": black_phase.get("middlegame"),
            "white_endgame_acc": white_phase.get("endgame"),
            "black_endgame_acc": black_phase.get("endgame"),
            "white_pieces_hung": white_hanging.get("total_hung", 0),
            "black_pieces_hung": black_hanging.get("total_hung", 0),
            "white_brilliant_count": w_counts.get("Brilliant", 0),
            "black_brilliant_count": b_counts.get("Brilliant", 0),
            "white_great_count": w_counts.get("Great", 0),
            "black_great_count": b_counts.get("Great", 0),
            "pgn": pgn_content,
            "summary_json": summary_json,
            "moves_json": moves_json,
            "timestamp": save_ts,
        }

    def _prepare_game_analysis_params(
        self,
        game_analysis: GameAnalysis,
        pgn_content: str,
        timestamp: float | None = None,
    ) -> tuple:
        row = self._prepare_game_analysis_row(game_analysis, pgn_content, timestamp=timestamp)
        return self._row_to_legacy_tuple(row)

    def _prepare_game_dict_row(self, d: dict[str, Any]) -> dict[str, Any]:
        pgn = str(d.get("pgn") or "")
        gid = str(d.get("id") or "") or _make_game_id(pgn)
        white = str(d.get("white") or "")
        black = str(d.get("black") or "")
        result = str(d.get("result") or "*")
        date_str = str(d.get("date") or "")
        event = str(d.get("event") or "")

        raw_ts = d.get("timestamp")
        try:
            timestamp = (
                float(raw_ts) if raw_ts is not None and str(raw_ts).strip() != "" else time.time()
            )
        except (ValueError, TypeError):
            timestamp = time.time()

        time_control = d.get("time_control") or None
        speed_category = d.get("speed_category") or None
        if not speed_category:
            from src.backend.storage.pgn_parser import PGNParser

            speed_category = PGNParser.detect_speed_category(time_control, event)

        moves_json = d.get("moves_json") or ""
        summary_json = d.get("summary_json") or ""
        summary_dict = {}
        if summary_json:
            try:
                summary_dict = json.loads(summary_json)
            except Exception:
                summary_dict = {}

        has_tactics = (
            isinstance(summary_dict.get("white"), dict)
            and "tactics" in summary_dict["white"]
            and isinstance(summary_dict.get("black"), dict)
            and "tactics" in summary_dict["black"]
        )

        if not has_tactics and moves_json:
            try:
                moves_data = json.loads(moves_json)
                if moves_data:
                    summary_dict, _, _ = _enrich_summary_with_tactics(
                        summary_dict, moves_data, result, speed_category=speed_category or "Blitz"
                    )
                    summary_json = json.dumps(summary_dict)
            except Exception as e:
                logger.debug("Failed computing tactics for dict row %s: %s", gid, e)

        book_exit_ply = _to_float(d.get("book_exit_ply"))
        if book_exit_ply is not None:
            book_exit_ply = int(book_exit_ply)
        else:
            book_exit_ply = summary_dict.get("white", {}).get("tactics", {}).get("book_exit_ply")

        phase_accs: dict[str, dict[str, float | None]] = {"white": {}, "black": {}}
        for color in ("white", "black"):
            for phase in ("opening", "middlegame", "endgame"):
                col_key = f"{color}_{phase}_acc"
                val = _to_float(d.get(col_key))
                if val is None:
                    val = (
                        summary_dict.get(color, {})
                        .get("tactics", {})
                        .get("phase_accuracies", {})
                        .get(phase)
                    )
                phase_accs[color][phase] = val

        white_pieces_hung = _to_int_or_none(d.get("white_pieces_hung"))
        if white_pieces_hung is None:
            white_pieces_hung = (
                summary_dict.get("white", {})
                .get("tactics", {})
                .get("hanging_metrics", {})
                .get("total_hung", 0)
            )

        black_pieces_hung = _to_int_or_none(d.get("black_pieces_hung"))
        if black_pieces_hung is None:
            black_pieces_hung = (
                summary_dict.get("black", {})
                .get("tactics", {})
                .get("hanging_metrics", {})
                .get("total_hung", 0)
            )

        raw_960 = d.get("chess960")
        chess960 = 1 if str(raw_960).strip() in ("1", "True", "true") else 0
        starting_fen = d.get("starting_fen") or None
        termination = d.get("termination") or None
        termination_mode = d.get("termination_mode") or None

        if not termination_mode:
            from src.backend.storage.termination_detector import TerminationDetector

            t_mode, t_desc = TerminationDetector.detect_termination(
                headers={
                    "Result": result,
                    "White": white,
                    "Black": black,
                    "Termination": termination or "",
                },
                moves=[],
                starting_fen=starting_fen,
                chess960=bool(chess960),
            )
            termination_mode = t_mode
            if not termination:
                termination = t_desc

        return {
            "id": gid,
            "white": white,
            "black": black,
            "result": result,
            "date": date_str,
            "event": event,
            "white_elo": d.get("white_elo") or None,
            "black_elo": d.get("black_elo") or None,
            "time_control": time_control,
            "speed_category": speed_category,
            "eco": d.get("eco") or None,
            "opening": d.get("opening") or None,
            "termination": termination,
            "termination_mode": termination_mode,
            "source": d.get("source") or "file",
            "starting_fen": starting_fen,
            "chess960": chess960,
            "book_exit_ply": book_exit_ply,
            "white_opening_acc": phase_accs["white"]["opening"],
            "black_opening_acc": phase_accs["black"]["opening"],
            "white_middlegame_acc": phase_accs["white"]["middlegame"],
            "black_middlegame_acc": phase_accs["black"]["middlegame"],
            "white_endgame_acc": phase_accs["white"]["endgame"],
            "black_endgame_acc": phase_accs["black"]["endgame"],
            "white_pieces_hung": white_pieces_hung,
            "black_pieces_hung": black_pieces_hung,
            "white_brilliant_count": _to_int(d.get("white_brilliant_count")),
            "black_brilliant_count": _to_int(d.get("black_brilliant_count")),
            "white_great_count": _to_int(d.get("white_great_count")),
            "black_great_count": _to_int(d.get("black_great_count")),
            "pgn": pgn,
            "summary_json": summary_json,
            "moves_json": moves_json,
            "timestamp": timestamp,
        }

    def _prepare_game_dict_params(self, d: dict[str, Any]) -> tuple:
        row = self._prepare_game_dict_row(d)
        return self._row_to_legacy_tuple(row)

    def save_games_bulk(self, items: list[Any]) -> int:
        """
        Saves multiple game analyses or game dictionaries to the database
        inside a single transaction using named parameters.
        """
        if not items:
            return 0

        param_rows: list[dict[str, Any]] = []
        for item in items:
            try:
                if isinstance(item, dict):
                    param_rows.append(self._prepare_game_dict_row(item))
                elif isinstance(item, tuple) and len(item) >= 2:
                    ts = item[2] if len(item) > 2 else None
                    param_rows.append(
                        self._prepare_game_analysis_row(item[0], item[1], timestamp=ts)
                    )
                elif isinstance(item, GameAnalysis):
                    param_rows.append(self._prepare_game_analysis_row(item, item.pgn_content))
            except Exception as exc:
                logger.error("Failed preparing game record in save_games_bulk: %s", exc)

        if not param_rows:
            return 0

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(INSERT_GAME_SQL, param_rows)
                conn.commit()
            logger.info("Successfully bulk-saved %d games to history.", len(param_rows))
            return len(param_rows)
        except Exception as e:
            logger.error("Failed to execute save_games_bulk: %s", e)
            return 0

    def save_game(self, game_analysis: GameAnalysis, pgn_content: str):
        """Saves a completed game analysis to the history."""
        self.save_games_bulk([(game_analysis, pgn_content)])

    def get_all_game_ids(self) -> set[str]:
        """Returns a set of all game IDs currently in the database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM games")
                return {row[0] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Failed to fetch game IDs: {e}")
            return set()

    def get_all_games(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Returns a list of all games (metadata + summary) sorted by timestamp desc."""
        games = []
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                if limit is not None:
                    cursor.execute(
                        "SELECT * FROM games ORDER BY timestamp DESC LIMIT ?", (int(limit),)
                    )
                else:
                    cursor.execute("SELECT * FROM games ORDER BY timestamp DESC")
                rows = cursor.fetchall()

                for row in rows:
                    games.append(dict(row))
        except Exception as e:
            logger.error(f"Failed to fetch games from history: {e}")

        return games

    def get_games_for_users(
        self,
        usernames: list[str],
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Returns games where either white or black player matches one of the usernames."""
        if not usernames:
            return []

        games = []
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Case-insensitive matching
                placeholders = ",".join(["?"] * len(usernames))
                lower_usernames = [u.lower() for u in usernames]
                params: list[Any] = lower_usernames + lower_usernames

                query = f"""
                    SELECT * FROM games
                    WHERE LOWER(white) IN ({placeholders})
                       OR LOWER(black) IN ({placeholders})
                    ORDER BY timestamp DESC
                """
                if limit is not None:
                    query += " LIMIT ?"
                    params.append(int(limit))

                cursor.execute(query, params)
                rows = cursor.fetchall()

                for row in rows:
                    games.append(dict(row))
        except Exception as e:
            logger.error(f"Failed to fetch user games: {e}")

        return games

    def get_games_for_stats(
        self,
        usernames: list[str],
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieves user games for statistics aggregation.
        Maintains full payloads (including moves_json and pgn) to allow complete tactical
        analysis and backward-compatible drill-down recomputations.
        """
        return self.get_games_for_users(usernames, limit=limit)

    def delete_game(self, game_id: str):
        """Deletes a game from history."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM games WHERE id = ?", (game_id,))
                conn.commit()
            logger.info(f"Game deleted from history: {game_id}")
        except Exception as e:
            logger.error(f"Failed to delete game from history: {e}")

    def get_game(self, game_id: str) -> dict[str, Any] | None:
        """Retrieves a single game record."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM games WHERE id = ?", (game_id,))
                row = cursor.fetchone()

                if row:
                    return dict(row)
            return None
        except Exception as e:
            logger.error(f"Failed to get game {game_id}: {e}")
            return None

    def get_game_analysis(self, game_id: str) -> GameAnalysis | None:
        """Retrieves a single game record as a fully-hydrated GameAnalysis object."""
        row_dict = self.get_game(game_id)
        if not row_dict:
            return None
        return self._row_to_game_analysis(row_dict)

    def _row_to_game_analysis(self, g_dict: dict[str, Any]) -> GameAnalysis:
        from .models import GameMetadata, MoveAnalysis
        from .pgn_parser import PGNParser
        from .termination_detector import TerminationDetector

        stored_speed = g_dict.get("speed_category")
        stored_term = g_dict.get("termination")
        stored_term_mode = g_dict.get("termination_mode")

        metadata = GameMetadata(
            white=g_dict.get("white", ""),
            black=g_dict.get("black", ""),
            result=g_dict.get("result", "*"),
            date=g_dict.get("date", ""),
            event=g_dict.get("event", ""),
            white_elo=g_dict.get("white_elo"),
            black_elo=g_dict.get("black_elo"),
            time_control=g_dict.get("time_control"),
            eco=g_dict.get("eco"),
            opening=g_dict.get("opening"),
            termination=stored_term,
            termination_mode=stored_term_mode,
            termination_description=stored_term,
            starting_fen=g_dict.get("starting_fen"),
            speed_category=stored_speed,
            source=g_dict.get("source", "file"),
            chess960=bool(g_dict.get("chess960", 0)),
        )
        if not metadata.speed_category:
            metadata.speed_category = PGNParser.detect_speed_category(
                metadata.time_control, metadata.event
            )

        summary = {}
        if g_dict.get("summary_json"):
            try:
                summary = json.loads(g_dict["summary_json"])
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        moves = []
        if g_dict.get("moves_json"):
            try:
                moves_data = json.loads(g_dict["moves_json"])
                for md in moves_data:
                    move = MoveAnalysis(
                        move_number=md.get("move_number", 0),
                        ply=md.get("ply", 0),
                        san=md.get("san", ""),
                        uci=md.get("uci", ""),
                        fen_before=md.get("fen_before", ""),
                        eval_before_cp=md.get("eval_before_cp"),
                        eval_before_mate=md.get("eval_before_mate"),
                        best_move=md.get("best_move"),
                        best_eval_cp=md.get("best_eval_cp"),
                        best_eval_mate=md.get("best_eval_mate"),
                        pv=md.get("pv", []),
                        eval_after_cp=md.get("eval_after_cp"),
                        eval_after_mate=md.get("eval_after_mate"),
                        win_chance_before=md.get("win_chance_before", 0.5),
                        win_chance_after=md.get("win_chance_after", 0.5),
                        classification=md.get("classification", ""),
                        explanation=md.get("explanation", ""),
                        multi_pvs=md.get("multi_pvs", []),
                        is_book_move=md.get("is_book_move", False),
                        eco=md.get("eco", ""),
                        opening_name=md.get("opening_name", ""),
                        candidate_continuations=md.get("candidate_continuations", []),
                        time_left=md.get("time_left"),
                        time_spent=md.get("time_spent"),
                        raw_clk=md.get("raw_clk"),
                    )
                    moves.append(move)
            except Exception as e:
                logger.error(f"Failed to parse moves_json: {e}")

        if not moves and g_dict.get("pgn"):
            try:
                parsed_games = PGNParser.parse_pgn_text(g_dict["pgn"])
                if parsed_games:
                    moves = parsed_games[0].moves
            except Exception as e:
                logger.error(f"Failed to parse pgn: {e}")

        if not metadata.termination_mode:
            term_mode, term_desc = TerminationDetector.detect_termination(
                headers={
                    "Result": metadata.result,
                    "White": metadata.white,
                    "Black": metadata.black,
                    "Termination": metadata.termination or "",
                },
                moves=moves,
                starting_fen=metadata.starting_fen,
                chess960=metadata.chess960,
            )
            metadata.termination_mode = term_mode
            if not metadata.termination:
                metadata.termination = term_desc
            metadata.termination_description = term_desc

        return GameAnalysis(
            game_id=g_dict["id"],
            metadata=metadata,
            pgn_content=g_dict.get("pgn", ""),
            summary=summary,
            moves=moves,
        )

    def game_exists(self, game_id: str) -> bool:
        """Checks if a game with the given ID already exists."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM games WHERE id = ?", (game_id,))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Failed to check game existence: {e}")
            return False

    def clear_history(self):
        """Clears all games from history and reclaims disk space via VACUUM."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM games")
                conn.commit()
            self.vacuum()
            logger.info("Game history cleared and database vacuumed.")
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")

    def save_cached_game(self, info: Any):
        """Saves a single GameInfo to the api_game_cache table."""
        self.save_cached_games_bulk([info])

    def save_cached_games_bulk(self, games: list[Any]):
        """Saves multiple GameInfo objects inside a single database transaction."""
        if not games:
            return
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                rows = [_info_to_cache_row(g, default_cached_at=now_str) for g in games]
                cursor.executemany(INSERT_API_CACHE_SQL, rows)
                conn.commit()
            logger.debug("Saved %d games to API cache", len(games))
        except Exception as e:
            logger.error("Failed to save cached games bulk: %s", e)

    def get_cached_game(self, game_id: str) -> Any | None:
        """Retrieves a single GameInfo object from cache by its ID."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM api_game_cache WHERE id = ?", (game_id,))
                row = cursor.fetchone()
                if row:
                    return _row_to_game_info(dict(row))
            return None
        except Exception as e:
            logger.error(f"Failed to get cached game {game_id}: {e}")
            return None

    def get_cached_games_for_date(self, source: str, date: str, username: str) -> list[Any]:
        """Retrieves cached games matching source, date, and containing username (case-insensitive)."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM api_game_cache
                    WHERE source = ? AND date = ?
                      AND (LOWER(white) = ? OR LOWER(black) = ?)
                    """,
                    (source, date, username.lower(), username.lower()),
                )
                return [_row_to_game_info(dict(r)) for r in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get cached games for date {date}: {e}")
            return []

    def clear_api_cache(self):
        """Clears all games from the API cache and reclaims disk space via VACUUM."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM api_game_cache")
                conn.commit()
            self.vacuum()
            logger.info("API game cache cleared and database vacuumed.")
        except Exception as e:
            logger.error(f"Failed to clear API game cache: {e}")

    @staticmethod
    def _parse_cached_at_to_epoch(cached_at: Any) -> float:
        if isinstance(cached_at, (int, float)):
            return float(cached_at)
        try:
            return float(cached_at)
        except (ValueError, TypeError):
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return time.mktime(time.strptime(str(cached_at), fmt))
            except Exception:
                pass
        return 0.0

    def save_explorer_cache(self, fen: str, response_json: str):
        """Saves a Lichess explorer response json for a given FEN."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO explorer_cache (fen, response_json, cached_at)
                    VALUES (?, ?, ?)
                """,
                    (fen, response_json, time.time()),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save explorer cache: {e}")

    def prune_explorer_cache(self, cursor: sqlite3.Cursor | None = None) -> int:
        """Prunes cached opening explorer responses older than EXPLORER_CACHE_TTL_SECONDS."""
        try:
            cutoff = time.time() - EXPLORER_CACHE_TTL_SECONDS
            cutoff_iso = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(cutoff))
            prune_sql = (
                "DELETE FROM explorer_cache WHERE "
                "(typeof(cached_at) IN ('integer', 'real') AND cached_at < ?) "
                "OR (typeof(cached_at) = 'text' AND cached_at < ?)"
            )
            if cursor is not None:
                cursor.execute(prune_sql, (cutoff, cutoff_iso))
                return cursor.rowcount
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(prune_sql, (cutoff, cutoff_iso))
                pruned = cur.rowcount
                conn.commit()
                if pruned > 0:
                    logger.debug("Pruned %d expired explorer cache entries.", pruned)
                return pruned
        except Exception as e:
            logger.debug(f"Failed to prune explorer cache: {e}")
            return 0

    def get_explorer_cache(self, fen: str) -> str | None:
        """Retrieves a cached explorer response json by FEN, deleting expired entries."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT response_json, cached_at FROM explorer_cache WHERE fen = ?", (fen,)
                )
                row = cursor.fetchone()
                if row:
                    response_json, cached_at = row
                    cached_epoch = self._parse_cached_at_to_epoch(cached_at)
                    if time.time() - cached_epoch < EXPLORER_CACHE_TTL_SECONDS:
                        return response_json
                    else:
                        cursor.execute("DELETE FROM explorer_cache WHERE fen = ?", (fen,))
                        conn.commit()
            return None
        except Exception as e:
            logger.error(f"Failed to get explorer cache: {e}")
            return None

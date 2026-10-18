import hashlib
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import Any

from src.utils.logger import logger
from src.utils.path_utils import get_user_data_dir

from .models import GameAnalysis

GAME_CSV_COLUMNS: list[str] = [
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
]

CURRENT_SCHEMA_VERSION: int = 2


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
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
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

                # Enable WAL mode and normal synchronous for fast concurrent reads
                try:
                    cursor.execute("PRAGMA journal_mode=WAL")
                    cursor.execute("PRAGMA synchronous=NORMAL")
                except Exception as e:
                    logger.debug(f"Could not enable WAL pragma: {e}")

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
            from src.backend.analysis.tactics import analyze_game_tactics

            for gid, m_json, res, speed, s_json in rows:
                try:
                    moves_data = json.loads(m_json)
                    s_cat = speed or "Blitz"
                    tactics_w = analyze_game_tactics(moves_data, "white", res, speed_category=s_cat)
                    tactics_b = analyze_game_tactics(moves_data, "black", res, speed_category=s_cat)

                    s_dict = json.loads(s_json) if s_json else {"white": {}, "black": {}}
                    if "white" not in s_dict or not isinstance(s_dict["white"], dict):
                        s_dict["white"] = {}
                    if "black" not in s_dict or not isinstance(s_dict["black"], dict):
                        s_dict["black"] = {}

                    s_dict["white"]["tactics"] = tactics_w
                    s_dict["black"]["tactics"] = tactics_b

                    w_hanging = tactics_w.get("hanging_metrics", {})
                    b_hanging = tactics_b.get("hanging_metrics", {})
                    w_phase = tactics_w.get("phase_accuracies", {})
                    b_phase = tactics_b.get("phase_accuracies", {})
                    w_brilliants = len(
                        [
                            b
                            for b in tactics_w.get("brilliancies", [])
                            if b.get("classification") == "Brilliant"
                        ]
                    )
                    b_brilliants = len(
                        [
                            b
                            for b in tactics_b.get("brilliancies", [])
                            if b.get("classification") == "Brilliant"
                        ]
                    )
                    w_greats = len(
                        [
                            b
                            for b in tactics_w.get("brilliancies", [])
                            if b.get("classification") == "Great"
                        ]
                    )
                    b_greats = len(
                        [
                            b
                            for b in tactics_b.get("brilliancies", [])
                            if b.get("classification") == "Great"
                        ]
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
                            w_brilliants,
                            b_brilliants,
                            w_greats,
                            b_greats,
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
                    cached_at TEXT NOT NULL
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

    def _prepare_game_analysis_params(
        self,
        game_analysis: GameAnalysis,
        pgn_content: str,
        timestamp: float | None = None,
    ) -> tuple:
        game_id = game_analysis.game_id
        if not game_id:
            if pgn_content:
                game_id = hashlib.md5(pgn_content.encode("utf-8")).hexdigest()
            else:
                game_id = str(uuid.uuid4())

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

        from src.backend.analysis.tactics import analyze_game_tactics

        speed_category = game_analysis.metadata.speed_category or "Blitz"
        tactics_white = analyze_game_tactics(
            moves_data,
            "white",
            game_analysis.metadata.result,
            speed_category=speed_category,
        )
        tactics_black = analyze_game_tactics(
            moves_data,
            "black",
            game_analysis.metadata.result,
            speed_category=speed_category,
        )

        summary_dict = (
            dict(game_analysis.summary) if game_analysis.summary else {"white": {}, "black": {}}
        )
        if "white" not in summary_dict:
            summary_dict["white"] = {}
        if "black" not in summary_dict:
            summary_dict["black"] = {}

        summary_dict["white"]["tactics"] = tactics_white
        summary_dict["black"]["tactics"] = tactics_black
        summary_json = json.dumps(summary_dict)

        book_exit_ply = tactics_white.get("book_exit_ply")
        white_phase = tactics_white.get("phase_accuracies", {})
        black_phase = tactics_black.get("phase_accuracies", {})
        white_hanging = tactics_white.get("hanging_metrics", {})
        black_hanging = tactics_black.get("hanging_metrics", {})
        white_brilliants = len(
            [
                b
                for b in tactics_white.get("brilliancies", [])
                if b.get("classification") == "Brilliant"
            ]
        )
        white_greats = len(
            [b for b in tactics_white.get("brilliancies", []) if b.get("classification") == "Great"]
        )
        black_brilliants = len(
            [
                b
                for b in tactics_black.get("brilliancies", [])
                if b.get("classification") == "Brilliant"
            ]
        )
        black_greats = len(
            [b for b in tactics_black.get("brilliancies", []) if b.get("classification") == "Great"]
        )

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

        return (
            game_id,
            game_analysis.metadata.white,
            game_analysis.metadata.black,
            game_analysis.metadata.result,
            game_analysis.metadata.date,
            game_analysis.metadata.event,
            pgn_content,
            summary_json,
            save_ts,
            game_analysis.metadata.white_elo,
            game_analysis.metadata.black_elo,
            game_analysis.metadata.time_control,
            game_analysis.metadata.eco,
            game_analysis.metadata.termination,
            game_analysis.metadata.termination_mode,
            game_analysis.metadata.opening,
            game_analysis.metadata.starting_fen,
            game_analysis.metadata.source,
            int(game_analysis.metadata.chess960),
            moves_json,
            speed_category,
            book_exit_ply,
            white_phase.get("opening"),
            black_phase.get("opening"),
            white_phase.get("middlegame"),
            black_phase.get("middlegame"),
            white_phase.get("endgame"),
            black_phase.get("endgame"),
            white_hanging.get("total_hung", 0),
            black_hanging.get("total_hung", 0),
            white_brilliants,
            black_brilliants,
            white_greats,
            black_greats,
        )

    def _prepare_game_dict_params(self, d: dict[str, Any]) -> tuple:
        pgn = str(d.get("pgn") or "")
        gid = str(d.get("id") or "")
        if not gid:
            if pgn:
                gid = hashlib.md5(pgn.encode("utf-8")).hexdigest()
            else:
                gid = str(uuid.uuid4())

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

        white_elo = d.get("white_elo") or None
        black_elo = d.get("black_elo") or None
        time_control = d.get("time_control") or None
        eco = d.get("eco") or None
        termination = d.get("termination") or None
        termination_mode = d.get("termination_mode") or None
        opening = d.get("opening") or None
        starting_fen = d.get("starting_fen") or None
        source = d.get("source") or "file"

        raw_960 = d.get("chess960")
        chess960 = 1 if str(raw_960).strip() in ("1", "True", "true") else 0

        moves_json = d.get("moves_json") or ""
        summary_json = d.get("summary_json") or ""
        speed_category = d.get("speed_category") or None

        if not speed_category:
            from src.backend.storage.pgn_parser import PGNParser

            speed_category = PGNParser._detect_speed_category(time_control, event)

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
                    from src.backend.analysis.tactics import analyze_game_tactics

                    s_cat = speed_category or "Blitz"
                    tw = analyze_game_tactics(moves_data, "white", result, speed_category=s_cat)
                    tb = analyze_game_tactics(moves_data, "black", result, speed_category=s_cat)
                    if "white" not in summary_dict or not isinstance(summary_dict["white"], dict):
                        summary_dict["white"] = {}
                    if "black" not in summary_dict or not isinstance(summary_dict["black"], dict):
                        summary_dict["black"] = {}
                    summary_dict["white"]["tactics"] = tw
                    summary_dict["black"]["tactics"] = tb
                    summary_json = json.dumps(summary_dict)
            except Exception as e:
                logger.debug("Failed computing tactics for dict row %s: %s", gid, e)

        def _to_float(v):
            try:
                return float(v) if v is not None and str(v).strip() != "" else None
            except (ValueError, TypeError):
                return None

        def _to_int(v):
            try:
                return int(v) if v is not None and str(v).strip() != "" else 0
            except (ValueError, TypeError):
                return 0

        book_exit_ply = _to_float(d.get("book_exit_ply"))
        if book_exit_ply is not None:
            book_exit_ply = int(book_exit_ply)
        else:
            book_exit_ply = summary_dict.get("white", {}).get("tactics", {}).get("book_exit_ply")

        white_opening_acc = _to_float(d.get("white_opening_acc"))
        if white_opening_acc is None:
            white_opening_acc = (
                summary_dict.get("white", {})
                .get("tactics", {})
                .get("phase_accuracies", {})
                .get("opening")
            )

        black_opening_acc = _to_float(d.get("black_opening_acc"))
        if black_opening_acc is None:
            black_opening_acc = (
                summary_dict.get("black", {})
                .get("tactics", {})
                .get("phase_accuracies", {})
                .get("opening")
            )

        white_middlegame_acc = _to_float(d.get("white_middlegame_acc"))
        if white_middlegame_acc is None:
            white_middlegame_acc = (
                summary_dict.get("white", {})
                .get("tactics", {})
                .get("phase_accuracies", {})
                .get("middlegame")
            )

        black_middlegame_acc = _to_float(d.get("black_middlegame_acc"))
        if black_middlegame_acc is None:
            black_middlegame_acc = (
                summary_dict.get("black", {})
                .get("tactics", {})
                .get("phase_accuracies", {})
                .get("middlegame")
            )

        white_endgame_acc = _to_float(d.get("white_endgame_acc"))
        if white_endgame_acc is None:
            white_endgame_acc = (
                summary_dict.get("white", {})
                .get("tactics", {})
                .get("phase_accuracies", {})
                .get("endgame")
            )

        black_endgame_acc = _to_float(d.get("black_endgame_acc"))
        if black_endgame_acc is None:
            black_endgame_acc = (
                summary_dict.get("black", {})
                .get("tactics", {})
                .get("phase_accuracies", {})
                .get("endgame")
            )

        white_pieces_hung = _to_int(d.get("white_pieces_hung"))
        if not white_pieces_hung:
            white_pieces_hung = (
                summary_dict.get("white", {})
                .get("tactics", {})
                .get("hanging_metrics", {})
                .get("total_hung", 0)
            )

        black_pieces_hung = _to_int(d.get("black_pieces_hung"))
        if not black_pieces_hung:
            black_pieces_hung = (
                summary_dict.get("black", {})
                .get("tactics", {})
                .get("hanging_metrics", {})
                .get("total_hung", 0)
            )

        white_brilliant_count = _to_int(d.get("white_brilliant_count"))
        black_brilliant_count = _to_int(d.get("black_brilliant_count"))
        white_great_count = _to_int(d.get("white_great_count"))
        black_great_count = _to_int(d.get("black_great_count"))

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

        return (
            gid,
            white,
            black,
            result,
            date_str,
            event,
            pgn,
            summary_json,
            timestamp,
            white_elo,
            black_elo,
            time_control,
            eco,
            termination,
            termination_mode,
            opening,
            starting_fen,
            source,
            chess960,
            moves_json,
            speed_category,
            book_exit_ply,
            white_opening_acc,
            black_opening_acc,
            white_middlegame_acc,
            black_middlegame_acc,
            white_endgame_acc,
            black_endgame_acc,
            white_pieces_hung,
            black_pieces_hung,
            white_brilliant_count,
            black_brilliant_count,
            white_great_count,
            black_great_count,
        )

    def save_games_bulk(self, items: list[Any]) -> int:
        """
        Saves multiple game analyses or game dictionaries to the database
        inside a single transaction.
        """
        if not items:
            return 0

        param_rows = []
        for item in items:
            try:
                if isinstance(item, dict):
                    param_rows.append(self._prepare_game_dict_params(item))
                elif isinstance(item, tuple) and len(item) >= 2:
                    ts = item[2] if len(item) > 2 else None
                    param_rows.append(
                        self._prepare_game_analysis_params(item[0], item[1], timestamp=ts)
                    )
                elif isinstance(item, GameAnalysis):
                    param_rows.append(self._prepare_game_analysis_params(item, item.pgn_content))
            except Exception as exc:
                logger.error("Failed preparing game record in save_games_bulk: %s", exc)

        if not param_rows:
            return 0

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(
                    """
                    INSERT OR REPLACE INTO games (
                        id, white, black, result, date, event, pgn, summary_json, timestamp,
                        white_elo, black_elo, time_control, eco, termination, termination_mode, opening, starting_fen, source,
                        chess960, moves_json, speed_category, book_exit_ply,
                        white_opening_acc, black_opening_acc,
                        white_middlegame_acc, black_middlegame_acc,
                        white_endgame_acc, black_endgame_acc,
                        white_pieces_hung, black_pieces_hung,
                        white_brilliant_count, black_brilliant_count,
                        white_great_count, black_great_count
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    param_rows,
                )
                conn.commit()
            logger.info("Successfully bulk-saved %d games to history.", len(param_rows))
            return len(param_rows)
        except Exception as e:
            logger.error(f"Failed to execute save_games_bulk: {e}")
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

                limit_clause = f" LIMIT {int(limit)}" if limit is not None else ""
                cursor.execute(f"SELECT * FROM games ORDER BY timestamp DESC{limit_clause}")
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
                limit_clause = f" LIMIT {int(limit)}" if limit is not None else ""
                query = f"""
                    SELECT * FROM games
                    WHERE LOWER(white) IN ({placeholders})
                       OR LOWER(black) IN ({placeholders})
                    ORDER BY timestamp DESC{limit_clause}
                """

                # Duplicate params for both IN clauses
                lower_usernames = [u.lower() for u in usernames]
                params = lower_usernames + lower_usernames

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
            termination=g_dict.get("termination"),
            source=g_dict.get("source", "file"),
            chess960=bool(g_dict.get("chess960", 0)),
        )
        metadata.speed_category = PGNParser._detect_speed_category(
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
                try:
                    cursor.execute("VACUUM")
                except Exception as ve:
                    logger.debug(f"VACUUM after clear_history skipped: {ve}")
            logger.info("Game history cleared and database vacuumed.")
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")

    def save_cached_game(self, info):
        """Saves a single GameInfo to the api_game_cache table."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cached_at = info.cached_at or time.strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO api_game_cache (
                        id, source, white, black, result, date, pgn,
                        white_elo, black_elo, time_class, move_count, opening, cached_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        info.game_id,
                        info.source,
                        info.white,
                        info.black,
                        info.result,
                        info.date,
                        info.pgn,
                        info.white_elo,
                        info.black_elo,
                        info.time_class,
                        info.move_count,
                        info.opening,
                        cached_at,
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save cached game {info.game_id}: {e}")

    def save_cached_games_bulk(self, games):
        """Saves multiple GameInfo objects inside a single database transaction."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cached_at = time.strftime("%Y-%m-%d %H:%M:%S")
                for info in games:
                    c_at = info.cached_at or cached_at
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO api_game_cache (
                            id, source, white, black, result, date, pgn,
                            white_elo, black_elo, time_class, move_count, opening, cached_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            info.game_id,
                            info.source,
                            info.white,
                            info.black,
                            info.result,
                            info.date,
                            info.pgn,
                            info.white_elo,
                            info.black_elo,
                            info.time_class,
                            info.move_count,
                            info.opening,
                            c_at,
                        ),
                    )
                conn.commit()
            logger.debug(f"Saved {len(games)} games to API cache")
        except Exception as e:
            logger.error(f"Failed to save cached games bulk: {e}")

    def get_cached_game(self, game_id: str):
        """Retrieves a single GameInfo object from cache by its ID."""
        try:
            from src.backend.models.game_info import GameInfo

            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM api_game_cache WHERE id = ?", (game_id,))
                row = cursor.fetchone()
                if row:
                    d = dict(row)
                    return GameInfo(
                        game_id=d["id"],
                        source=d["source"],
                        white=d["white"],
                        black=d["black"],
                        result=d["result"],
                        date=d["date"],
                        pgn=d["pgn"],
                        white_elo=d["white_elo"],
                        black_elo=d["black_elo"],
                        time_class=d["time_class"],
                        move_count=d["move_count"],
                        opening=d["opening"],
                        cached_at=d["cached_at"],
                    )
            return None
        except Exception as e:
            logger.error(f"Failed to get cached game {game_id}: {e}")
            return None

    def get_cached_games_for_date(self, source: str, date: str, username: str) -> list:
        """Retrieves cached games matching source, date, and containing username (case-insensitive)."""
        try:
            from src.backend.models.game_info import GameInfo

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
                rows = cursor.fetchall()
                games = []
                for row in rows:
                    d = dict(row)
                    games.append(
                        GameInfo(
                            game_id=d["id"],
                            source=d["source"],
                            white=d["white"],
                            black=d["black"],
                            result=d["result"],
                            date=d["date"],
                            pgn=d["pgn"],
                            white_elo=d["white_elo"],
                            black_elo=d["black_elo"],
                            time_class=d["time_class"],
                            move_count=d["move_count"],
                            opening=d["opening"],
                            cached_at=d["cached_at"],
                        )
                    )
                return games
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
                try:
                    cursor.execute("VACUUM")
                except Exception as ve:
                    logger.debug(f"VACUUM after clear_api_cache skipped: {ve}")
            logger.info("API game cache cleared and database vacuumed.")
        except Exception as e:
            logger.error(f"Failed to clear API game cache: {e}")

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
                    (fen, response_json, time.strftime("%Y-%m-%d %H:%M:%S")),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save explorer cache: {e}")

    def prune_explorer_cache(self, cursor: sqlite3.Cursor | None = None) -> int:
        """Prunes cached opening explorer responses older than 48 hours."""
        try:
            if cursor is not None:
                cursor.execute(
                    "DELETE FROM explorer_cache WHERE cached_at < datetime('now', '-2 days')"
                )
                return cursor.rowcount
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "DELETE FROM explorer_cache WHERE cached_at < datetime('now', '-2 days')"
                )
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
                    try:
                        cached_time = time.strptime(cached_at, "%Y-%m-%d %H:%M:%S")
                        cached_epoch = time.mktime(cached_time)
                        if time.time() - cached_epoch < 172800:
                            return response_json
                        else:
                            cursor.execute("DELETE FROM explorer_cache WHERE fen = ?", (fen,))
                            conn.commit()
                    except Exception:
                        return response_json
            return None
        except Exception as e:
            logger.error(f"Failed to get explorer cache: {e}")
            return None

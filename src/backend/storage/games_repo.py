"""
Repository for chess game analysis persistence, querying, and hydration.
"""

import hashlib
import json
import sqlite3
import time
import uuid
from collections import Counter
from typing import Any

from src.backend.storage.db_connection import get_db_connection
from src.backend.storage.models import GameAnalysis
from src.backend.storage.schema_constants import (
    _LIGHT_GAME_COLS_SQL,
    INSERT_GAME_SQL,
)
from src.utils.logger import logger


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


class GamesRepo:
    """Manages persistence, retrieval, and hydration of analyzed games."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self):
        return get_db_connection(self.db_path)

    @staticmethod
    def _row_to_legacy_tuple(row: dict[str, Any]) -> tuple:
        """
        Backwards-compatible tuple conversion in exact original schema order.
        """
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

        moves_data = [m.to_dict() for m in game_analysis.moves]
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

        white_hanging = tactics_white.get("hanging_metrics", {})
        black_hanging = tactics_black.get("hanging_metrics", {})
        white_phase = tactics_white.get("phase_accuracies", {})
        black_phase = tactics_black.get("phase_accuracies", {})

        w_counts = Counter(b.get("classification") for b in tactics_white.get("brilliancies", []))
        b_counts = Counter(b.get("classification") for b in tactics_black.get("brilliancies", []))

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

        phase_accs: dict[str, dict[str, float | None]] = {
            "white": {"opening": None, "middlegame": None, "endgame": None},
            "black": {"opening": None, "middlegame": None, "endgame": None},
        }
        for color in ("white", "black"):
            c_dict = summary_dict.get(color, {}) if isinstance(summary_dict, dict) else {}
            c_tactics = c_dict.get("tactics", {}) if isinstance(c_dict, dict) else {}
            phase_map = c_tactics.get("phase_accuracies", {}) if isinstance(c_tactics, dict) else {}
            for phase in ("opening", "middlegame", "endgame"):
                val = d.get(f"{color}_{phase}_acc")
                if val is not None:
                    phase_accs[color][phase] = _to_float(val)
                elif isinstance(phase_map, dict):
                    phase_accs[color][phase] = _to_float(phase_map.get(phase))

        white_pieces_hung = _to_int_or_none(d.get("white_pieces_hung"))
        black_pieces_hung = _to_int_or_none(d.get("black_pieces_hung"))
        if white_pieces_hung is None:
            w_hang = (
                summary_dict.get("white", {}).get("tactics", {}).get("hanging_metrics", {})
                if isinstance(summary_dict, dict)
                else {}
            )
            white_pieces_hung = w_hang.get("total_hung", 0) if isinstance(w_hang, dict) else 0
        if black_pieces_hung is None:
            b_hang = (
                summary_dict.get("black", {}).get("tactics", {}).get("hanging_metrics", {})
                if isinstance(summary_dict, dict)
                else {}
            )
            black_pieces_hung = b_hang.get("total_hung", 0) if isinstance(b_hang, dict) else 0

        book_exit_ply = _to_int(d.get("book_exit_ply"))
        if not book_exit_ply and isinstance(summary_dict, dict):
            book_exit_ply = (
                summary_dict.get("white", {}).get("tactics", {}).get("book_exit_ply")
                or summary_dict.get("black", {}).get("tactics", {}).get("book_exit_ply")
                or 0
            )

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
            "termination": d.get("termination") or None,
            "termination_mode": d.get("termination_mode") or None,
            "source": d.get("source") or "file",
            "starting_fen": d.get("starting_fen") or None,
            "chess960": _to_int(d.get("chess960")),
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
                    param_rows.append(self._prepare_game_analysis_row(item, item.pgn_content or ""))
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

    def save_game(self, game_analysis: GameAnalysis, pgn_content: str) -> None:
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
            logger.error("Failed to fetch game IDs: %s", e)
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
            logger.error("Failed to fetch games from history: %s", e)

        return games

    def get_game_summaries(self, limit: int | None = None) -> list[dict[str, Any]]:
        """
        Lightweight projection returning game metadata, summary_json, and metrics
        WITHOUT heavy moves_json or pgn payloads.
        Optimized for history tables and high-scale list rendering.
        """
        games = []
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                query = f"SELECT {_LIGHT_GAME_COLS_SQL} FROM games ORDER BY timestamp DESC"
                if limit is not None:
                    query += " LIMIT ?"
                    cursor.execute(query, (int(limit),))
                else:
                    cursor.execute(query)
                rows = cursor.fetchall()

                for row in rows:
                    games.append(dict(row))
        except Exception as e:
            logger.error("Failed to fetch game summaries: %s", e)

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
            logger.error("Failed to fetch user games: %s", e)

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

    def delete_game(self, game_id: str) -> None:
        """Deletes a game from history."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM games WHERE id = ?", (game_id,))
                conn.commit()
            logger.info("Game deleted from history: %s", game_id)
        except Exception as e:
            logger.error("Failed to delete game from history: %s", e)

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
            logger.error("Failed to get game %s: %s", game_id, e)
            return None

    def get_game_analysis(self, game_id: str) -> GameAnalysis | None:
        """Retrieves a single game record as a fully-hydrated GameAnalysis object."""
        row_dict = self.get_game(game_id)
        if not row_dict:
            return None
        return self.row_to_game_analysis(row_dict)

    def row_to_game_analysis(self, g_dict: dict[str, Any]) -> GameAnalysis:
        from src.backend.storage.models import GameMetadata, MoveAnalysis
        from src.backend.storage.pgn_parser import PGNParser
        from src.backend.storage.termination_detector import TerminationDetector

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
                moves = [MoveAnalysis.from_dict(md) for md in moves_data if isinstance(md, dict)]
            except Exception as e:
                logger.error("Failed to parse moves_json: %s", e)

        if not moves and g_dict.get("pgn"):
            try:
                parsed_games = PGNParser.parse_pgn_text(g_dict["pgn"])
                if parsed_games:
                    moves = parsed_games[0].moves
            except Exception as e:
                logger.error("Failed to parse pgn: %s", e)

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

    _row_to_game_analysis = row_to_game_analysis

    def game_exists(self, game_id: str) -> bool:
        """Checks if a game with the given ID already exists."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM games WHERE id = ?", (game_id,))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error("Failed to check game existence: %s", e)
            return False

    def clear_history(self) -> None:
        """Clears all games from history and reclaims disk space via VACUUM."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM games")
                conn.commit()
                cursor.execute("VACUUM")
            logger.info("Game history cleared and database vacuumed.")
        except Exception as e:
            logger.error("Failed to clear history: %s", e)

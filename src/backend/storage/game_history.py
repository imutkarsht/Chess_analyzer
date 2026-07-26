import sqlite3
import json
import uuid
import time
from typing import List, Optional, Dict, Any
from .models import GameAnalysis, GameMetadata, MoveAnalysis
from src.utils.logger import logger

class GameHistoryManager:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            import os
            from src.utils.path_utils import get_user_data_dir
            self.db_path = os.path.join(get_user_data_dir(), "analysis_cache.db")
        else:
            self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
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
            
            # 2. Schema Migration: Ensure new columns exist
            # List of (column_name, column_type)
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
                ("moves_json", "TEXT")
            ]
            
            # Check existing columns
            cursor.execute("PRAGMA table_info(games)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            
            for col_name, col_type in new_columns:
                if col_name not in existing_cols:
                    try:
                        logger.info(f"Migrating DB: Adding column {col_name}")
                        cursor.execute(f"ALTER TABLE games ADD COLUMN {col_name} {col_type}")
                    except Exception as e:
                        logger.error(f"Failed to add column {col_name}: {e}")
            
            self._init_api_cache(cursor)
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize game history DB: {e}")

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
        except Exception as e:
            logger.error(f"Failed to initialize API/Explorer cache tables: {e}")

    def save_game(self, game_analysis: GameAnalysis, pgn_content: str):
        """Saves a completed game analysis to the history."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            game_id = game_analysis.game_id or str(uuid.uuid4())
            
            summary_json = json.dumps(game_analysis.summary)
            
            moves_data = []
            for m in game_analysis.moves:
                moves_data.append({
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
                })
            moves_json = json.dumps(moves_data)
            
            cursor.execute("""
                INSERT OR REPLACE INTO games (
                    id, white, black, result, date, event, pgn, summary_json, timestamp,
                    white_elo, black_elo, time_control, eco, termination, opening, starting_fen, source,
                    chess960, moves_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game_id,
                game_analysis.metadata.white,
                game_analysis.metadata.black,
                game_analysis.metadata.result,
                game_analysis.metadata.date,
                game_analysis.metadata.event,
                pgn_content,
                summary_json,
                time.time(),
                game_analysis.metadata.white_elo,
                game_analysis.metadata.black_elo,
                game_analysis.metadata.time_control,
                game_analysis.metadata.eco,
                game_analysis.metadata.termination,
                game_analysis.metadata.opening,
                game_analysis.metadata.starting_fen,
                game_analysis.metadata.source,
                int(game_analysis.metadata.chess960),
                moves_json
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Game saved to history: {game_id}")
        except Exception as e:
            logger.error(f"Failed to save game to history: {e}")

    def get_all_games(self) -> List[Dict[str, Any]]:
        """Returns a list of all games (metadata + summary) sorted by timestamp desc."""
        games = []
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM games ORDER BY timestamp DESC LIMIT 200")
            rows = cursor.fetchall()
            
            for row in rows:
                games.append(dict(row))
                
            conn.close()
        except Exception as e:
            logger.error(f"Failed to fetch games from history: {e}")
            
        return games
            
    def get_games_for_users(self, usernames: List[str]) -> List[Dict[str, Any]]:
        """Returns games where either white or black player matches one of the usernames."""
        if not usernames:
            return []
            
        games = []
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Case-insensitive matching
            placeholders = ','.join(['?'] * len(usernames))
            query = f"""
                SELECT * FROM games 
                WHERE LOWER(white) IN ({placeholders}) 
                   OR LOWER(black) IN ({placeholders})
                ORDER BY timestamp DESC LIMIT 200
            """
            
            # Duplicate params for both IN clauses
            lower_usernames = [u.lower() for u in usernames]
            params = lower_usernames + lower_usernames
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            for row in rows:
                games.append(dict(row))
                
            conn.close()
        except Exception as e:
            logger.error(f"Failed to fetch user games: {e}")
            
        return games

    def delete_game(self, game_id: str):
        """Deletes a game from history."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM games WHERE id = ?", (game_id,))
            conn.commit()
            conn.close()
            logger.info(f"Game deleted from history: {game_id}")
        except Exception as e:
            logger.error(f"Failed to delete game from history: {e}")

    def get_game(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single game record."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM games WHERE id = ?", (game_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return None
        except Exception as e:
            logger.error(f"Failed to get game {game_id}: {e}")
            return None

    def game_exists(self, game_id: str) -> bool:
        """Checks if a game with the given ID already exists."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM games WHERE id = ?", (game_id,))
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except Exception as e:
            logger.error(f"Failed to check game existence: {e}")
            return False

    def clear_history(self):
        """Clears all games from history."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM games")
            conn.commit()
            conn.close()
            logger.info("Game history cleared.")
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")

    def save_cached_game(self, info):
        """Saves a single GameInfo to the api_game_cache table."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cached_at = info.cached_at or time.strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT OR REPLACE INTO api_game_cache (
                    id, source, white, black, result, date, pgn,
                    white_elo, black_elo, time_class, move_count, opening, cached_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
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
                cached_at
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save cached game {info.game_id}: {e}")

    def save_cached_games_bulk(self, games):
        """Saves multiple GameInfo objects inside a single database transaction."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cached_at = time.strftime("%Y-%m-%d %H:%M:%S")
            for info in games:
                c_at = info.cached_at or cached_at
                cursor.execute("""
                    INSERT OR REPLACE INTO api_game_cache (
                        id, source, white, black, result, date, pgn,
                        white_elo, black_elo, time_class, move_count, opening, cached_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
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
                    c_at
                ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save cached games bulk: {e}")

    def get_cached_game(self, game_id: str):
        """Retrieves a single GameInfo object from cache by its ID."""
        try:
            from src.backend.models.game_info import GameInfo
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM api_game_cache WHERE id = ?", (game_id,))
            row = cursor.fetchone()
            conn.close()
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
                    cached_at=d["cached_at"]
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get cached game {game_id}: {e}")
            return None

    def get_cached_games_for_date(self, source: str, date: str, username: str) -> list:
        """Retrieves cached games matching source, date, and containing username (case-insensitive)."""
        try:
            from src.backend.models.game_info import GameInfo
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM api_game_cache
                WHERE source = ? AND date = ?
                  AND (LOWER(white) = ? OR LOWER(black) = ?)
            """, (source, date, username.lower(), username.lower()))
            rows = cursor.fetchall()
            conn.close()
            games = []
            for row in rows:
                d = dict(row)
                games.append(GameInfo(
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
                    cached_at=d["cached_at"]
                ))
            return games
        except Exception as e:
            logger.error(f"Failed to get cached games for date {date}: {e}")
            return []

    def clear_api_cache(self):
        """Clears all games from the API cache."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM api_game_cache")
            conn.commit()
            conn.close()
            logger.info("API game cache cleared.")
        except Exception as e:
            logger.error(f"Failed to clear API game cache: {e}")

    def save_explorer_cache(self, fen: str, response_json: str):
        """Saves a Lichess explorer response json for a given FEN."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO explorer_cache (fen, response_json, cached_at)
                VALUES (?, ?, ?)
            """, (fen, response_json, time.strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save explorer cache: {e}")

    def get_explorer_cache(self, fen: str) -> Optional[str]:
        """Retrieves a cached explorer response json by FEN."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT response_json, cached_at FROM explorer_cache WHERE fen = ?", (fen,))
            row = cursor.fetchone()
            conn.close()
            if row:
                response_json, cached_at = row
                try:
                    cached_time = time.strptime(cached_at, "%Y-%m-%d %H:%M:%S")
                    cached_epoch = time.mktime(cached_time)
                    if time.time() - cached_epoch < 172800:
                        return response_json
                except Exception:
                    return response_json
            return None
        except Exception as e:
            logger.error(f"Failed to get explorer cache: {e}")
            return None

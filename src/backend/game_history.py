import sqlite3
import json
import uuid
import time
from typing import List, Optional, Dict, Any
from dataclasses import asdict
from .models import GameAnalysis, GameMetadata, MoveAnalysis
from ..utils.logger import logger

class GameHistoryManager:
    def __init__(self, db_path: str = "analysis_cache.db"):
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
                ("starting_fen", "TEXT")
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
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize game history DB: {e}")

    def save_game(self, game_analysis: GameAnalysis, pgn_content: str):
        """Saves a completed game analysis to the history."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Generate ID if not present (though GameAnalysis usually has one)
            game_id = game_analysis.game_id or str(uuid.uuid4())
            
            # Serialize summary
            summary_json = json.dumps(game_analysis.summary)
            
            cursor.execute("""
                INSERT OR REPLACE INTO games (
                    id, white, black, result, date, event, pgn, summary_json, timestamp,
                    white_elo, black_elo, time_control, eco, termination, opening, starting_fen
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                game_analysis.metadata.starting_fen
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
            
            cursor.execute("SELECT * FROM games ORDER BY timestamp DESC")
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
                ORDER BY timestamp DESC
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

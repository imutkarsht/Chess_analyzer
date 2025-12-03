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
                INSERT OR REPLACE INTO games (id, white, black, result, date, event, pgn, summary_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game_id,
                game_analysis.metadata.white,
                game_analysis.metadata.black,
                game_analysis.metadata.result,
                game_analysis.metadata.date,
                game_analysis.metadata.event,
                pgn_content,
                summary_json,
                time.time()
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

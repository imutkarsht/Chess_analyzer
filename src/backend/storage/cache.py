import sqlite3
import json
import hashlib
from typing import Optional, Dict, Any
from src.constants import DEFAULT_MULTI_PV

class AnalysisCache:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            import os
            from src.utils.path_utils import get_user_data_dir
            self.db_path = os.path.join(get_user_data_dir(), "analysis_cache.db")
        else:
            self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    def __del__(self):
        if hasattr(self, 'conn') and self.conn:
            try:
                self.conn.close()
            except:
                pass

    def _init_db(self):
        cursor = self.conn.cursor()
        # Create table with depth column for depth-aware caching
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis (
                id TEXT PRIMARY KEY,
                fen TEXT,
                engine_params TEXT,
                depth INTEGER DEFAULT 0,
                result TEXT
            )
        """)
        # Add depth column if it doesn't exist (migration for existing DBs)
        try:
            cursor.execute("ALTER TABLE analysis ADD COLUMN depth INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        self.conn.commit()

    def _generate_key(self, fen: str, multi_pv: int) -> str:
        """Generate cache key based on FEN and multi_pv only (not depth)."""
        key_str = f"{fen}|multipv:{multi_pv}"
        return hashlib.sha256(key_str.encode('utf-8')).hexdigest()

    def get_analysis(self, fen: str, engine_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get cached analysis if it exists at sufficient depth.
        Returns cached result only if cached_depth >= requested_depth.
        """
        requested_depth = engine_params.get("depth", 0) or 0
        multi_pv = engine_params.get("multi_pv", DEFAULT_MULTI_PV)
        key = self._generate_key(fen, multi_pv)
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT result, depth FROM analysis WHERE id = ?", (key,))
        row = cursor.fetchone()
        
        if row:
            cached_result, cached_depth = row[0], row[1] or 0
            # Only return cached result if it was analyzed at equal or higher depth
            if cached_depth >= requested_depth:
                return json.loads(cached_result)
        return None

    def save_analysis(self, fen: str, engine_params: Dict[str, Any], result: Dict[str, Any]):
        """
        Save analysis to cache. Overwrites if new depth is higher than cached depth.
        """
        new_depth = engine_params.get("depth", 0) or 0
        multi_pv = engine_params.get("multi_pv", DEFAULT_MULTI_PV)
        key = self._generate_key(fen, multi_pv)
        
        cursor = self.conn.cursor()
        
        # Check existing depth
        cursor.execute("SELECT depth FROM analysis WHERE id = ?", (key,))
        row = cursor.fetchone()
        
        should_save = True
        if row:
            cached_depth = row[0] or 0
            # Only overwrite if new analysis is at higher depth
            if new_depth <= cached_depth:
                should_save = False
        
        if should_save:
            cursor.execute("""
                INSERT OR REPLACE INTO analysis (id, fen, engine_params, depth, result)
                VALUES (?, ?, ?, ?, ?)
            """, (key, fen, json.dumps(engine_params, sort_keys=True), new_depth, json.dumps(result)))
            self.conn.commit()

    def clear_cache(self):
        """Clears all cached analysis."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM analysis")
            self.conn.commit()
        except Exception as e:
            print(f"Failed to clear cache: {e}")

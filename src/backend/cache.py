import sqlite3
import json
import hashlib
from typing import Optional, Dict, Any

class AnalysisCache:
    def __init__(self, db_path: str = "analysis_cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis (
                id TEXT PRIMARY KEY,
                fen TEXT,
                engine_params TEXT,
                result TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _generate_key(self, fen: str, engine_params: Dict[str, Any]) -> str:
        # Sort params to ensure consistent key
        params_str = json.dumps(engine_params, sort_keys=True)
        key_str = f"{fen}|{params_str}"
        return hashlib.sha256(key_str.encode('utf-8')).hexdigest()

    def get_analysis(self, fen: str, engine_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        key = self._generate_key(fen, engine_params)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT result FROM analysis WHERE id = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return None

    def save_analysis(self, fen: str, engine_params: Dict[str, Any], result: Dict[str, Any]):
        key = self._generate_key(fen, engine_params)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO analysis (id, fen, engine_params, result)
            VALUES (?, ?, ?, ?)
        """, (key, fen, json.dumps(engine_params, sort_keys=True), json.dumps(result)))
        conn.commit()
        conn.close()

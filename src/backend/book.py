import os
import chess
import requests
from typing import Optional
from ..utils.logger import logger
from ..utils.config import ConfigManager

class BookManager:
    def __init__(self):
        self.cache = {}
        self.session = requests.Session()
        self.base_url = "https://explorer.lichess.ovh/masters"
        self.config_manager = ConfigManager()

    def _get_headers(self) -> dict:
        token = self.config_manager.get("lichess_token") or os.getenv("LICHESS_TOKEN")
        headers = {
            "User-Agent": "ChessAnalyzerPro/2.0.1 (contact: github.com/imutkarsht/Chess_analyzer)"
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def get_opening_name(self, fen_before: str, move_uci: str) -> Optional[str]:
        """
        Checks if the move leads to a known book position and returns the opening name.
        """
        # We need the FEN AFTER the move to identify the opening
        board = chess.Board(fen_before)
        try:
            board.push_uci(move_uci)
            fen_after = board.fen()
        except:
            return None
            
        # Check cache first
        fen_key = " ".join(fen_after.split(" ")[:4]) # Position only
        if fen_key in self.cache:
            return self.cache[fen_key]

        try:
            # Fetch from Lichess
            # We query the position. The API returns the opening name for this position.
            params = {
                "fen": fen_after,
                "moves": 1 # We just need the opening name, not moves
            }
            response = self.session.get(self.base_url, params=params, headers=self._get_headers(), timeout=2)
            
            if response.status_code == 200:
                data = response.json()
                opening = data.get("opening")
                if opening:
                    name = opening.get("name")
                    if name:
                        self.cache[fen_key] = name
                        return name
        except Exception as e:
            logger.error(f"Failed to fetch opening from Lichess: {e}")
            
        return None

    def is_book_move(self, fen_before: str, move_uci: str) -> bool:
        # For now, we consider it a book move if we can find an opening name for the resulting position
        # Or if it's in the Lichess masters database (which implies it's a book move)
        # To be more precise, we should check if the move exists in the database for the BEFORE position.
        
        try:
            params = {
                "fen": fen_before,
                "moves": 10
            }
            response = self.session.get(self.base_url, params=params, headers=self._get_headers(), timeout=2)
            if response.status_code == 200:
                data = response.json()
                moves = data.get("moves", [])
                for move in moves:
                    if move.get("uci") == move_uci:
                        return True
        except:
            pass
            
        return False

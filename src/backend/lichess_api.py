import requests
from dotenv import load_dotenv
import os
import sys
import json
from typing import List, Dict
from ..utils.config import ConfigManager

class LichessAPI:
    BASE_URL = "https://lichess.org/api/games/user"

    def __init__(self):
        self.config_manager = ConfigManager()
        
        try:
            if getattr(sys, 'frozen', False):
                # If running as executable, load from bundled env.sample
                base_path = sys._MEIPASS
                load_dotenv(dotenv_path=os.path.join(base_path, '.env.sample'))
            else:
                # If running from source, load from local .env
                load_dotenv()
        except Exception:
            pass
        
    def get_headers(self):
        token = self.config_manager.get("lichess_token") or os.getenv("LICHESS_TOKEN")
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/x-ndjson", 
            "Content-Type": "application/json"
        }

    def get_user_games(self, username: str, max_games: int = 5) -> List[Dict]:
        """
        Fetches last N games from Lichess and returns JSON (NDJSON parsed)
        """
        try:
            url = f"{LichessAPI.BASE_URL}/{username}"
            params = {
                "max": max_games,
                "moves": "true",
                "opening": "true",
                "pgnInJson": "true",  
            }

            response = requests.get(url, headers=self.get_headers(), params=params)
            response.raise_for_status()

            games = []
            for raw_line in response.iter_lines():
                if raw_line.strip():
                    line = raw_line.decode("utf-8").strip()
                    try:
                        game_data = json.loads(line)
                        
                        # Normalize to match Chess.com format expected by UI
                        normalized_game = {
                            "white": {
                                "username": game_data.get("players", {}).get("white", {}).get("user", {}).get("name", "?"),
                                "rating": game_data.get("players", {}).get("white", {}).get("rating", "?"),
                                "result": "win" if game_data.get("winner") == "white" else "checkmated" if game_data.get("status") == "mate" else "agreed" # Simplified result mapping
                            },
                            "black": {
                                "username": game_data.get("players", {}).get("black", {}).get("user", {}).get("name", "?"),
                                "rating": game_data.get("players", {}).get("black", {}).get("rating", "?"),
                                "result": "win" if game_data.get("winner") == "black" else "checkmated" if game_data.get("status") == "mate" else "agreed"
                            },
                            "time_class": game_data.get("speed", "standard"),
                            "end_time": int(game_data.get("createdAt", 0) / 1000), # Convert ms to seconds
                            "pgn": game_data.get("pgn", ""),
                            "url": f"https://lichess.org/{game_data.get('id')}"
                        }
                        
                        games.append(normalized_game)
                    except json.JSONDecodeError:
                        continue
            return games

        except Exception as e:
            print("Error fetching games:", e)
            return []



import requests
import datetime
from typing import List, Dict, Optional
from ..utils.logger import logger
from .base_api import BaseChessAPI


class ChessComAPI(BaseChessAPI):
    BASE_URL = "https://api.chess.com/pub"
    HEADERS = {
        "User-Agent": "ChessAnalyzer/1.0 (contact: your_email@example.com)" 
    }

    @staticmethod
    def get_last_games(username: str, limit: int = 5) -> List[Dict]:
        """
        Fetches the last 'limit' games for the given username.
        Returns a list of dictionaries containing game data (pgn, white, black, result, etc).
        """
        try:
            archives_url = f"{ChessComAPI.BASE_URL}/player/{username}/games/archives"
            response = BaseChessAPI._make_request(archives_url, ChessComAPI.HEADERS)
            if not response:
                return []
            
            archives = BaseChessAPI._safe_json(response)
            if not archives:
                return []
            archives = archives.get("archives", [])
            
            if not archives:
                return []
            
            all_games = []
            for archive_url in reversed(archives):
                resp = BaseChessAPI._make_request(archive_url, ChessComAPI.HEADERS)
                if resp:
                    games_data = BaseChessAPI._safe_json(resp)
                    if games_data:
                        games_list = games_data.get("games", [])
                        games_list.sort(key=lambda x: x.get("end_time", 0), reverse=True)
                        all_games.extend(games_list)
                        
                        if len(all_games) >= limit:
                            break
            
            return all_games[:limit]
            
        except Exception as e:
            BaseChessAPI._log_api_error("Chess.com", "get_last_games", e)
            return []

    @staticmethod
    def get_game_by_id(game_id: str, url: str = None) -> Optional[Dict]:
        """
        Fetches a specific game by its ID.
        Prioritizes the callback API for live games as it's most reliable for recent games.
        Falls back to scraping or archive search if needed.
        """
        # 1. Try callback API first (fastest and most reliable for live games)
        game = ChessComAPI._get_game_via_callback(game_id)
        if game:
            return game

        if not url:
            return None

        try:
            # 2. If callback failed, try scraping metadata from URL to find archive
            response = requests.get(url, headers=ChessComAPI.HEADERS)
            response.raise_for_status()
            html = response.text
            
            # Extract username
            import re
            # Try finding "username":"name" pattern in JSON blobs in HTML
            user_match = re.search(r'"username":"([^"]+)"', html)
            username = None
            if user_match:
                username = user_match.group(1)
            
            if not username:
                # Try meta description
                desc_match = re.search(r'<meta name="description" content="([^"]+)"', html)
                if desc_match:
                    content = desc_match.group(1)
                    parts = content.split(' vs ')
                    if len(parts) > 0:
                        username = parts[0].split(' (')[0].strip()
            
            if username:
                return ChessComAPI._find_game_in_archives(username, game_id)
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching game {game_id}: {e}", exc_info=True)
            return None

    @staticmethod
    def _find_game_in_archives(username: str, game_id: str) -> Optional[Dict]:
        try:
            # Get list of archives
            archives_url = f"{ChessComAPI.BASE_URL}/player/{username}/games/archives"
            response = requests.get(archives_url, headers=ChessComAPI.HEADERS)
            if response.status_code != 200:
                return None
            
            archives = response.json().get("archives", [])
            if not archives:
                return None
                
            # Search backwards (latest first)
            for archive_url in reversed(archives):
                resp = requests.get(archive_url, headers=ChessComAPI.HEADERS)
                if resp.status_code == 200:
                    games = resp.json().get("games", [])
                    for game in games:
                        if game.get("url", "").endswith(game_id):
                            return game
                            
            return None
        except Exception as e:
            logger.error(f"Error searching archives: {e}")
            return None

    @staticmethod
    def _get_game_via_callback(game_id: str) -> Optional[Dict]:
        try:
            url = f"https://www.chess.com/callback/live/game/{game_id}"
            response = requests.get(url, headers=ChessComAPI.HEADERS)
            if response.status_code != 200:
                return None
            data = response.json()
            if "game" in data and "pgn" in data["game"]:
                return {"pgn": data["game"]["pgn"]}
            return None
        except:
            return None


    @staticmethod
    def extract_game_id(url: str) -> Optional[str]:
        """
        Extracts the game ID from a Chess.com URL.
        Supports:
        - https://www.chess.com/game/live/123456
        - https://www.chess.com/live/game/123456
        - https://www.chess.com/game/daily/123456
        """
        import re
        # Match /game/live/123456 or /live/game/123456
        match = re.search(r"(?:game/live|live/game|game/daily)/(\d+)", url)
        if match:
            return match.group(1)
        return None

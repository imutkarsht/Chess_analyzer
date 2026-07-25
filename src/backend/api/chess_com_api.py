import requests
import datetime
from typing import List, Dict, Optional
from src.utils.logger import logger
from src.constants import CHESSCOM_BASE_URL, CHESSCOM_HEADERS
from .base_api import BaseChessAPI


class ChessComAPI(BaseChessAPI):
    BASE_URL = CHESSCOM_BASE_URL
    HEADERS = CHESSCOM_HEADERS

    @staticmethod
    def get_last_games(username: str, limit: int = 20) -> List[Dict]:
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
    def get_user_games_by_date(username: str, date) -> List[Dict]:
        """
        Fetches games of a user for a specific date from Chess.com archives.
        """
        import datetime
        try:
            year = str(date.year)
            month = f"{date.month:02d}"
            url = f"{ChessComAPI.BASE_URL}/player/{username}/games/{year}/{month}"
            
            response = BaseChessAPI._make_request(url, ChessComAPI.HEADERS)
            if not response:
                return []
                
            data = BaseChessAPI._safe_json(response)
            if not data:
                return []
                
            games_list = data.get("games", [])
            matched_games = []
            
            start_dt = datetime.datetime.combine(date, datetime.time.min, tzinfo=datetime.timezone.utc)
            start_ts = int(start_dt.timestamp())
            end_dt = datetime.datetime.combine(date, datetime.time.max, tzinfo=datetime.timezone.utc)
            end_ts = int(end_dt.timestamp())
            
            for game in games_list:
                end_time = game.get("end_time")
                if end_time and start_ts <= end_time <= end_ts:
                    matched_games.append(game)
                    
            return matched_games
        except Exception as e:
            BaseChessAPI._log_api_error("Chess.com", "get_user_games_by_date", e)
            return []

    @staticmethod
    def get_game_by_id(game_id: str, url: str = None, username: str = None) -> Optional[Dict]:
        """
        Fetches a specific game by its ID using ONLY Chess.com Public API.
        Requires the player's username to search their archives.
        """
        if username:
            game = ChessComAPI._find_game_in_archives(username, game_id)
            if game:
                return game

        if not url:
            return None

        # Fallback scraping of HTML to find the username if it was somehow not passed
        try:
            response = requests.get(url, headers=ChessComAPI.HEADERS)
            response.raise_for_status()
            html = response.text
            
            import re
            user_match = re.search(r'"username":"([^"]+)"', html)
            extracted_username = None
            if user_match:
                extracted_username = user_match.group(1)
            
            if not extracted_username:
                desc_match = re.search(r'<meta name="description" content="([^"]+)"', html)
                if desc_match:
                    content = desc_match.group(1)
                    parts = content.split(' vs ')
                    if len(parts) > 0:
                        extracted_username = parts[0].split(' (')[0].strip()
            
            if extracted_username:
                return ChessComAPI._find_game_in_archives(extracted_username, game_id)
        except Exception as e:
            logger.error(f"Error scraping HTML fallback for game {game_id}: {e}")

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

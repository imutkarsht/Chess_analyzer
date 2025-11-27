import requests
import datetime
from typing import List, Dict, Optional

class ChessComAPI:
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
            # 1. Get archives to find the latest month with games
            archives_url = f"{ChessComAPI.BASE_URL}/player/{username}/games/archives"
            response = requests.get(archives_url, headers=ChessComAPI.HEADERS)
            response.raise_for_status()
            archives = response.json().get("archives", [])
            
            if not archives:
                return []
            
            # 2. Fetch games from the last archive (current or previous month)
            # We might need to go back multiple months if the last month has few games, 
            # but for simplicity let's start with the last one.
            all_games = []
            
            # Iterate backwards through archives until we have enough games
            for archive_url in reversed(archives):
                resp = requests.get(archive_url, headers=ChessComAPI.HEADERS)
                if resp.status_code == 200:
                    games_data = resp.json().get("games", [])
                    # Sort by end_time descending
                    games_data.sort(key=lambda x: x.get("end_time", 0), reverse=True)
                    all_games.extend(games_data)
                    
                    if len(all_games) >= limit:
                        break
            
            return all_games[:limit]
            
            return all_games[:limit]
            
        except Exception as e:
            print(f"Error fetching games from Chess.com: {e}")
            return []

    @staticmethod
    def get_game_by_id(game_id: str, url: str = None) -> Optional[Dict]:
        """
        Fetches a specific game by its ID using a hybrid approach:
        1. If URL is provided, scrape it for metadata (username, date).
        2. Use the official Pub API to fetch the archive for that month.
        3. Find the game in the archive.
        """
        if not url:
            # Try to construct a URL if only ID is given? 
            # Without username, we can't easily guess the URL for live games reliably without redirection.
            # But we can try the callback method as a fallback if URL is missing.
            return ChessComAPI._get_game_via_callback(game_id)

        try:
            # Step 1: Fetch HTML to get metadata
            response = requests.get(url, headers=ChessComAPI.HEADERS)
            response.raise_for_status()
            html = response.text
            
            # Step 2: Extract username and date
            # We look for the game date and one of the players.
            # Usually there is a link to the archive or metadata.
            # Let's look for the "Date" header in PGN or specific meta tags.
            # Actually, simpler: The URL itself might not have it, but the page content does.
            
            # Extract usernames from description meta tag
            # <meta name="description" content="White (Rating) vs Black (Rating). Result..." />
            import re
            desc_match = re.search(r'<meta name="description" content="([^"]+)"', html)
            username = None
            if desc_match:
                content = desc_match.group(1)
                # "User1 (1000) vs User2 (1200)"
                # Extract first username
                parts = content.split(' vs ')
                if len(parts) > 0:
                    # "User1 (1000)" -> "User1"
                    username = parts[0].split(' (')[0].strip()
            
            if not username:
                # Fallback: try to find "username" in JSON
                user_match = re.search(r'"username":"([^"]+)"', html)
                if user_match:
                    username = user_match.group(1)
            
            if username:
                # We have a username. We don't have the date, so we have to search archives.
                # Start from the latest archive and go back.
                return ChessComAPI._find_game_in_archives(username, game_id)
            
            # Fallback to callback if scraping fails
            print("Metadata scraping failed, falling back to callback API.")
            return ChessComAPI._get_game_via_callback(game_id)
            
        except Exception as e:
            print(f"Error fetching game {game_id}: {e}")
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
            print(f"Error searching archives: {e}")
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
    def _fetch_from_archive(username: str, year: str, month: str, game_id: str) -> Optional[Dict]:
        # Deprecated in favor of _find_game_in_archives but kept for compatibility if needed
        return ChessComAPI._find_game_in_archives(username, game_id)

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

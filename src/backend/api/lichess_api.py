import datetime
import json
import os
import sys
from urllib.parse import quote

import requests
from dotenv import load_dotenv

from src.constants import LICHESS_ACCOUNT_URL, LICHESS_BASE_URL, LICHESS_USER_URL
from src.utils.config import ConfigManager
from src.utils.logger import logger

from .base_api import ApiStatus, BaseChessAPI, ProfileResult
from .import_limits import clamp_games_limit, current_token


def _result_for_side(game_data: dict, side: str) -> str:
    """Map a Lichess result to the Chess.com-style value used by the UI.

    Lichess only sends a winner for decisive games, so the old fallback turned
    every resignation/timeout into an agreed draw. Keep the loss reason so
    history records and win/loss metrics stay accurate.
    """
    if game_data.get("winner") == side:
        return "win"

    status = game_data.get("status", "")
    if status == "resign":
        return "resigned"
    if status in ("outoftime", "timeout"):
        return "timeout"
    if status == "mate":
        return "checkmated"
    if status == "stalemate":
        return "stalemate"
    return "agreed"


class LichessAPI(BaseChessAPI):
    BASE_URL = LICHESS_BASE_URL

    def __init__(self):
        self.config_manager = ConfigManager()

        try:
            if getattr(sys, "frozen", False):
                # If running as executable, load from bundled env.sample
                base_path = sys._MEIPASS
                load_dotenv(dotenv_path=os.path.join(base_path, ".env.sample"))
            else:
                # If running from source, load from local .env
                load_dotenv()
        except Exception:
            pass

    def get_headers(self):
        token = current_token(self.config_manager)
        headers = BaseChessAPI.DEFAULT_HEADERS.copy()
        headers.update(
            {
                "Accept": "application/x-ndjson",
                "Content-Type": "application/json",
            }
        )
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def get_user_games(self, username: str, max_games: int = 20) -> list[dict]:
        """
        Fetches last N games from Lichess and returns JSON (NDJSON parsed)
        """
        # Enforce the token-dependent cap here as well as in the UI: a setting
        # saved while a token was present must not over-fetch after it is gone.
        max_games = clamp_games_limit(max_games, current_token(self.config_manager))
        logger.info("Fetching last %d games for user '%s' from Lichess", max_games, username)
        try:
            url = f"{LichessAPI.BASE_URL}/{username}"
            params = {
                "max": max_games,
                "moves": "true",
                "opening": "true",
                "pgnInJson": "true",
                "clocks": "true",
            }

            # Use BaseChessAPI helper
            response = BaseChessAPI._make_request(url, self.get_headers(), params)
            if not response:
                return []

            games = []
            for raw_line in response.iter_lines():
                if raw_line.strip():
                    line = raw_line.decode("utf-8").strip()
                    try:
                        game_data = json.loads(line)

                        # Normalize to match Chess.com format expected by UI
                        normalized_game = {
                            "white": {
                                "username": game_data.get("players", {})
                                .get("white", {})
                                .get("user", {})
                                .get("name", "?"),
                                "rating": game_data.get("players", {})
                                .get("white", {})
                                .get("rating", "?"),
                                "result": _result_for_side(game_data, "white"),
                            },
                            "black": {
                                "username": game_data.get("players", {})
                                .get("black", {})
                                .get("user", {})
                                .get("name", "?"),
                                "rating": game_data.get("players", {})
                                .get("black", {})
                                .get("rating", "?"),
                                "result": _result_for_side(game_data, "black"),
                            },
                            "time_class": game_data.get("speed", "standard"),
                            "end_time": int(
                                game_data.get("createdAt", 0) / 1000
                            ),  # Convert ms to seconds
                            "pgn": game_data.get("pgn", ""),
                            "url": f"https://lichess.org/{game_data.get('id')}",
                        }

                        games.append(normalized_game)
                    except json.JSONDecodeError:
                        continue
            logger.info(
                "Successfully fetched %d games for user '%s' from Lichess", len(games), username
            )
            return games

        except Exception as e:
            BaseChessAPI._log_api_error("Lichess", "get_user_games", e)
            return []

    def get_user_games_by_date(self, username: str, date) -> list[dict]:
        """
        Fetches games for a specific user and date.
        """
        try:
            start_dt = datetime.datetime.combine(date, datetime.time.min)
            since = int(start_dt.timestamp() * 1000)
            end_dt = datetime.datetime.combine(date, datetime.time.max)
            until = int(end_dt.timestamp() * 1000)

            url = f"{LichessAPI.BASE_URL}/{username}"
            params = {
                "since": since,
                "until": until,
                "moves": "true",
                "opening": "true",
                "pgnInJson": "true",
                "clocks": "true",
                "max": 100,
            }

            response = BaseChessAPI._make_request(url, self.get_headers(), params)
            if not response:
                return []

            games = []
            for raw_line in response.iter_lines():
                if raw_line.strip():
                    line = raw_line.decode("utf-8").strip()
                    try:
                        game_data = json.loads(line)
                        normalized_game = {
                            "white": {
                                "username": game_data.get("players", {})
                                .get("white", {})
                                .get("user", {})
                                .get("name", "?"),
                                "rating": game_data.get("players", {})
                                .get("white", {})
                                .get("rating", "?"),
                                "result": _result_for_side(game_data, "white"),
                            },
                            "black": {
                                "username": game_data.get("players", {})
                                .get("black", {})
                                .get("user", {})
                                .get("name", "?"),
                                "rating": game_data.get("players", {})
                                .get("black", {})
                                .get("rating", "?"),
                                "result": _result_for_side(game_data, "black"),
                            },
                            "time_class": game_data.get("speed", "standard"),
                            "end_time": int(game_data.get("createdAt", 0) / 1000),
                            "pgn": game_data.get("pgn", ""),
                            "url": f"https://lichess.org/{game_data.get('id')}",
                        }
                        games.append(normalized_game)
                    except json.JSONDecodeError:
                        continue
            return games

        except Exception as e:
            BaseChessAPI._log_api_error("Lichess", "get_user_games_by_date", e)
            return []

    def extract_game_id(self, url: str) -> str:
        """
        Extracts game ID from Lichess URL.
        Supported formats:
        - https://lichess.org/HuUq2G3x
        - https://lichess.org/HuUq2G3x/white
        """
        if "lichess.org" not in url.lower():
            return ""

        try:
            # Remove trailing slash
            if url.endswith("/"):
                url = url[:-1]

            # Split by /
            parts = url.split("/")
            possible_id = parts[-1]

            # Lichess IDs are 8 or 12 chars usually.
            # If "white" or "black" is at the end, go back one
            if possible_id.lower() in ["white", "black"] and len(parts) > 1:
                possible_id = parts[-2]

            # Basic validation: alphanumeric, length 8 or 12
            if len(possible_id) >= 8:
                return possible_id[:8]  # First 8 chars are the game ID

            return ""
        except Exception:
            return ""

    def get_game_by_id(self, game_id: str) -> dict:
        """
        Fetches PGN for a specific game ID
        """
        try:
            url = f"https://lichess.org/game/export/{game_id}"

            headers = self.get_headers()
            headers["Accept"] = (
                "application/json"  # Enforce JSON to get metadata + PGN easily if needed
            )

            params = {
                "moves": "true",
                "pgnInJson": "true",
                "clocks": "true",
                "evals": "true",
            }

            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()

            game_data = response.json()

            # Normalize to return dict with "pgn"
            return {
                "pgn": game_data.get("pgn", ""),
                "id": game_data.get("id"),
                "white": game_data.get("players", {})
                .get("white", {})
                .get("user", {})
                .get("name", "?"),
                "black": game_data.get("players", {})
                .get("black", {})
                .get("user", {})
                .get("name", "?"),
                "white_rating": game_data.get("players", {}).get("white", {}).get("rating"),
                "black_rating": game_data.get("players", {}).get("black", {}).get("rating"),
            }

        except Exception as e:
            logger.error(f"Error fetching game {game_id}: {e}")
            return {}

    def get_user_profile_result(self, username: str) -> ProfileResult:
        """Fetch a public Lichess profile together with its transport status.

        The public profile endpoint does not require authentication. We
        deliberately omit the user's API token here so an expired token cannot
        break the settings preview; token health is checked separately through
        :meth:`get_account`.
        """
        clean_user = username.strip()
        if not clean_user:
            return ProfileResult(None, "not_found")

        url = f"{LICHESS_USER_URL}/{quote(clean_user, safe='')}"
        headers = BaseChessAPI.DEFAULT_HEADERS.copy()
        headers["Accept"] = "application/json"

        data, status = BaseChessAPI._request_json(url, headers)
        if status != "ok" or not isinstance(data, dict):
            return ProfileResult(None, status if status != "ok" else "error")

        perfs = data.get("perfs", {})

        def parse_perf(key: str) -> dict:
            item = perfs.get(key, {})
            return {
                "rating": item.get("rating"),
                "peak": None,
                "games": item.get("games", 0),
            }

        bullet = parse_perf("bullet")
        blitz = parse_perf("blitz")
        rapid = parse_perf("rapid")
        classical = parse_perf("classical")
        puzzle = parse_perf("puzzle")

        counts = data.get("count", {})
        total_games = counts.get("all", 0)
        wins = counts.get("win", 0)
        losses = counts.get("loss", 0)
        draws = counts.get("draw", 0)
        win_rate = (wins / total_games * 100) if total_games > 0 else 0.0
        profile_info = data.get("profile", {})

        profile = {
            "platform": "lichess",
            "username": data.get("username", clean_user),
            "title": data.get("title"),
            "avatar": None,
            # Lichess stores the country under "flag" (a two-letter code).
            # Accept "country" too for older payloads/fixtures.
            "country": profile_info.get("flag") or profile_info.get("country"),
            "joined": data.get("createdAt"),
            "url": data.get("url"),
            "bullet": bullet,
            "blitz": blitz,
            "rapid": rapid,
            "classical": classical,
            "puzzle": puzzle,
            "total_games": total_games,
            "win_rate": win_rate,
            "record": {
                "win": wins,
                "loss": losses,
                "draw": draws,
            },
        }
        return ProfileResult(profile, "ok")

    def get_user_profile(self, username: str) -> dict | None:
        """Backward-compatible profile-only accessor."""
        return self.get_user_profile_result(username).profile

    def get_account(self, token: str | None = None) -> tuple[dict | None, ApiStatus]:
        """Validate a token against the authenticated account endpoint.

        ``token`` may be passed explicitly because the settings card validates
        the value the user just typed, before the binder has persisted it.
        """
        token = (token or current_token(self.config_manager)).strip()
        if not token:
            return None, "unauthorized"

        headers = BaseChessAPI.DEFAULT_HEADERS.copy()
        headers.update(
            {
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            }
        )
        return BaseChessAPI._request_json(LICHESS_ACCOUNT_URL, headers)


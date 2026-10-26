"""Single source of truth for public-game import limits.

Lichess allows a higher import cap for authenticated requests. The UI and the
fetch workers must agree on the cap, otherwise a limit saved while a token was
present survives after the token is removed and silently over-fetches.
"""

import os

MAX_GAMES_ANONYMOUS = 20
MAX_GAMES_WITH_TOKEN = 30


def max_games_limit(token: str | None) -> int:
    """Return the largest import the current Lichess token allows."""
    return MAX_GAMES_WITH_TOKEN if (token or "").strip() else MAX_GAMES_ANONYMOUS


def clamp_games_limit(value: object, token: str | None) -> int:
    """Coerce an arbitrary setting value into the allowed import range."""
    try:
        requested = int(float(value))
    except (TypeError, ValueError):
        requested = MAX_GAMES_ANONYMOUS
    return max(1, min(requested, max_games_limit(token)))


def current_token(config_manager) -> str:
    """Resolve the configured Lichess token, falling back to the environment."""
    try:
        token = config_manager.get("lichess_token", "") or ""
    except Exception:
        token = ""
    return (token or os.getenv("LICHESS_TOKEN", "") or "").strip()

"""Single source of truth for public-game import limits.

The public recent-game cap is the same for anonymous and authenticated
requests. A Lichess token still unlocks private archives and the online
opening explorer, but it no longer changes the cap. The UI and fetch workers
must agree on the cap so a saved value cannot silently over-fetch.
"""

import os

MAX_GAMES_ANONYMOUS = 50
MAX_GAMES_WITH_TOKEN = 50


def max_games_limit(token: str | None) -> int:
    """Return the public recent-game cap for the current request."""
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
        token = config_manager.lichess_token
    except Exception:
        token = ""
    return (token or os.getenv("LICHESS_TOKEN", "") or "").strip()

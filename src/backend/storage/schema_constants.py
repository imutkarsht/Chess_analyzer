"""
Schema constants and SQL query definitions for the storage layer.
"""

GAME_COLUMNS: tuple[str, ...] = (
    "id",
    "white",
    "black",
    "result",
    "date",
    "event",
    "white_elo",
    "black_elo",
    "time_control",
    "speed_category",
    "eco",
    "opening",
    "termination",
    "termination_mode",
    "source",
    "starting_fen",
    "chess960",
    "book_exit_ply",
    "white_opening_acc",
    "black_opening_acc",
    "white_middlegame_acc",
    "black_middlegame_acc",
    "white_endgame_acc",
    "black_endgame_acc",
    "white_pieces_hung",
    "black_pieces_hung",
    "white_brilliant_count",
    "black_brilliant_count",
    "white_great_count",
    "black_great_count",
    "pgn",
    "summary_json",
    "moves_json",
    "timestamp",
)

GAME_CSV_COLUMNS: list[str] = list(GAME_COLUMNS)

_GAME_COLS_SQL: str = ", ".join(GAME_COLUMNS)
_GAME_PLACEHOLDERS_SQL: str = ", ".join(f":{c}" for c in GAME_COLUMNS)
INSERT_GAME_SQL: str = (
    f"INSERT OR REPLACE INTO games ({_GAME_COLS_SQL}) VALUES ({_GAME_PLACEHOLDERS_SQL})"
)

# Light column projection excluding heavy blobs (pgn and moves_json) for fast list views
LIGHT_GAME_COLUMNS: tuple[str, ...] = tuple(
    c for c in GAME_COLUMNS if c not in ("pgn", "moves_json")
)
_LIGHT_GAME_COLS_SQL: str = ", ".join(LIGHT_GAME_COLUMNS)

API_CACHE_COLUMNS: tuple[str, ...] = (
    "id",
    "source",
    "white",
    "black",
    "result",
    "date",
    "pgn",
    "white_elo",
    "black_elo",
    "time_class",
    "move_count",
    "opening",
    "cached_at",
)
_API_CACHE_COLS_SQL: str = ", ".join(API_CACHE_COLUMNS)
_API_CACHE_PLACEHOLDERS_SQL: str = ", ".join(["?"] * len(API_CACHE_COLUMNS))
INSERT_API_CACHE_SQL: str = f"INSERT OR REPLACE INTO api_game_cache ({_API_CACHE_COLS_SQL}) VALUES ({_API_CACHE_PLACEHOLDERS_SQL})"

CURRENT_SCHEMA_VERSION: int = 2
EXPLORER_CACHE_TTL_SECONDS: float = 48 * 3600.0  # 48 hours

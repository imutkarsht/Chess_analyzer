# Skill: Storage & Persistence

## Purpose
Manages all local data: SQLite engine cache, game history, PGN parsing, and the JSON config file. This layer has no Qt dependency and is independently testable.

---

## Relevant Files
| File | Role |
|---|---|
| `src/backend/storage/models.py` | Core dataclasses |
| `src/backend/storage/pgn_parser.py` | PGN → GameAnalysis conversion |
| `src/backend/storage/cache.py` | `AnalysisCache` — engine result cache |
| `src/backend/storage/game_history.py` | `GameHistoryManager` — game CRUD |
| `src/utils/config.py` | `ConfigManager` — JSON settings |
| `src/utils/path_utils.py` | Platform-aware path resolution |

---

## Data Models (`models.py`)

### MoveAnalysis
Fields set during PGN parsing: `move_number`, `ply`, `san`, `uci`, `fen_before`, `time_left`, `time_spent`, `raw_clk`

Fields set during analysis: `eval_before_cp`, `eval_before_mate`, `best_move`, `pv`, `eval_after_cp`, `eval_after_mate`, `win_chance_before`, `win_chance_after`, `classification`, `explanation`, `multi_pvs`

### GameMetadata
Contains: player names, ELO, date, event, result, ECO, opening, termination, time control, source (`"file"`, `"chesscom"`, `"lichess"`), `chess960: bool`

### GameAnalysis
Top-level: `game_id` (MD5 of PGN), `metadata: GameMetadata`, `moves: List[MoveAnalysis]`, `summary: Dict`, `ai_summary: Optional[str]`, `pgn_content: Optional[str]`

---

## Important APIs

### PGNParser
```python
# Parse from file
games: List[GameAnalysis] = PGNParser.parse_pgn_file("path/to/game.pgn")

# Parse from string
games: List[GameAnalysis] = PGNParser.parse_pgn_text(pgn_string)

# Internal: produces one GameAnalysis per chess.pgn.Game
```
- Game ID = `MD5(str(game))` — deterministic, prevents duplicates on re-import
- Clock annotation `[%clk H:MM:SS.s]` parsed per move; range-validated (mm: 0–59, ss: 0–59)
- Chess960 detected from `board.chess960` (python-chess) or FEN castling field (fallback)
- Source set from Site header: `chess.com` → `"chesscom"`, `lichess.org` → `"lichess"`, else `"file"`

### AnalysisCache
```python
cache = AnalysisCache()  # Uses get_user_data_dir() / analysis_cache.db
cache.get_analysis(fen: str, engine_params: dict) -> Optional[list]
cache.save_analysis(fen: str, engine_params: dict, result: list)
cache.clear_cache()
```
- Cache key: `SHA256(fen + "|multipv:" + str(multi_pv))`
- Depth-aware: cached result returned only if `cached_depth >= requested_depth`
- Overwrites cache only when new depth > cached depth

### GameHistoryManager
```python
mgr = GameHistoryManager()
mgr.save_game(game_analysis: GameAnalysis, pgn_content: str)
mgr.get_all_games() -> List[Dict]            # sorted by timestamp desc
mgr.get_games_for_users(usernames: List[str]) -> List[Dict]  # case-insensitive
mgr.get_game(game_id: str) -> Optional[Dict]
mgr.delete_game(game_id: str)
mgr.game_exists(game_id: str) -> bool
mgr.clear_history()
```

### ConfigManager
```python
cfg = ConfigManager()
cfg.get(key, default=None)
cfg.set(key, value)               # Persists immediately to disk
cfg.reload_config()               # Re-reads disk and updates shared dict in-place
cfg.get_active_profile() -> dict  # Returns active LLM profile
cfg.get_profiles() -> list
cfg.set_profiles(profiles, active_name)
```

### path_utils
```python
get_resource_path(relative_path: str) -> str  # Handles PyInstaller _MEIPASS
get_user_data_dir() -> str                     # Platform-specific user data dir
get_app_path() -> str                          # App dir (dev: cwd, frozen: exe dir)
```

---

## SQLite Schema

### `analysis` table (engine cache)
```sql
CREATE TABLE analysis (
    id TEXT PRIMARY KEY,          -- SHA256 key
    fen TEXT,
    engine_params TEXT,           -- JSON
    depth INTEGER DEFAULT 0,
    result TEXT                   -- JSON list of analysis dicts
)
```

### `games` table (history)
```sql
CREATE TABLE games (
    id TEXT PRIMARY KEY,          -- MD5 of PGN content
    white TEXT, black TEXT,
    result TEXT, date TEXT, event TEXT,
    pgn TEXT, summary_json TEXT,
    timestamp REAL,               -- Unix time
    white_elo TEXT, black_elo TEXT,
    time_control TEXT, eco TEXT,
    termination TEXT, opening TEXT,
    starting_fen TEXT, source TEXT,
    chess960 INTEGER              -- 0/1
)
```
Schema migration uses `ALTER TABLE ... ADD COLUMN` with try/except — safe to run on existing DBs.

---

## Key Assumptions
- `AnalysisCache` and `GameHistoryManager` both default to the same DB file. They coexist peacefully via separate tables.
- `ConfigManager` is a shared singleton — all instances in a process share `_shared_config`. Do not expect isolation between instances.
- PGN game IDs are content-addressable (MD5 of raw PGN string). Editing PGN metadata produces a different ID.
- `engine_params` in the cache is stored as JSON but the cache key deliberately excludes `depth` — only `fen` and `multi_pv` determine the key.

---

## Common Pitfalls
- **Schema migration**: New columns are added via `ALTER TABLE ADD COLUMN` + try/except. If you add a column, add it to the `new_columns` list in `GameHistoryManager._init_db()`.
- **Missing clock data**: `time_left` / `time_spent` may be `None` if PGN has no `[%clk]` annotations. Always guard against `None` before computing time deltas.
- **ConfigManager None collision**: Keys explicitly set to `None` in the JSON config will shadow `.get(key, default)` — the stored `None` wins. This is intentional for `engine_threads`/`engine_hash` (they are excluded from `DEFAULT_CONFIG` so module-level fallbacks in `engine.py` apply).
- **Re-analysis overwrites summary**: `save_game()` uses `INSERT OR REPLACE` — re-analyzing the same game (same PGN content → same MD5) overwrites the previous summary JSON.

---

## Extension Guidelines
- To add a new field to game history: add column to `new_columns` in `GameHistoryManager._init_db()`, add field to `save_game()` INSERT, add to `GameMetadata` dataclass.
- To add a new config setting: add key + default to `ConfigManager.DEFAULT_CONFIG`. No migration needed — `data.setdefault(key, value)` fills it in automatically on next load.
- To change the cache key scheme: update `_generate_key()` in `AnalysisCache`. Existing cache entries with the old key become orphaned (dead rows, harmless but wasteful).

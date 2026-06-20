# Architectural Decisions — Chess Analyzer Pro

---

## 1. Single SQLite File for Both Cache and History

**Decision**: Use one database file (`analysis_cache.db`) for both the engine analysis cache (`analysis` table) and the game history (`games` table).

**Reason**: Simplifies user data management — one file to back up, one path to configure, and one `get_user_data_dir()` call. Both datasets are local-only and tightly coupled in usage (history games reference the same positions in cache).

**Alternatives Considered**: Two separate `.db` files (one per concern). Rejected to avoid dual path management.

**Tradeoffs**: `clear_cache()` only clears the `analysis` table; clearing history is separate. The file can grow large for power users. Schema migrations for both tables are managed independently.

---

## 2. ConfigManager Singleton Pattern (Class-Level Shared State)

**Decision**: `ConfigManager` uses `_shared_config` as a class variable so all instances share the same in-memory dict.

**Reason**: Config is read frequently across many classes (`Analyzer`, `EngineManager`, `GroqService`, `MainWindow`, all views). A true singleton avoids redundant JSON reads and ensures settings changes propagate without explicit passing.

**Alternatives Considered**: Dependency injection (pass config explicitly everywhere), or a module-level global. Singleton was chosen for minimal boilerplate while keeping `ConfigManager` instantiable for testing.

**Tradeoffs**: Mutable shared state makes testing harder (must `reload_config()` between tests). External config changes require explicit `reload_config()` call. Booleans stored as `None` in `window_state` would shadow `.get(key, default)` fallbacks — documented workaround in `config.py` comments.

---

## 3. Score Convention: Always Store White-Perspective

**Decision**: All `eval_before_cp`, `eval_after_cp`, `eval_before_mate`, `eval_after_mate` fields in `MoveAnalysis` are stored relative to White (positive = White winning).

**Reason**: Stockfish returns scores relative to the side-to-move. Normalizing to White-perspective at the point of ingestion (`_process_analysis_results()`) means all downstream code (classification, graph rendering, ACPL calculation) can use a consistent sign convention without re-flipping.

**Alternatives Considered**: Store relative-to-player and flip at render time. Rejected because it requires every consumer to know whose turn it is.

**Tradeoffs**: Conversion must happen exactly once and in the right place. An off-by-one on when the flip is applied causes silent analysis errors. The final position's score requires special handling since the board has been advanced.

---

## 4. LLM Service: Provider-Agnostic via OpenAI SDK

**Decision**: `GroqService` uses the `openai` Python SDK for all providers (Groq, OpenAI, LM Studio, MiniMax, Custom), differentiated only by `base_url` and `api_key`.

**Reason**: All target providers expose OpenAI-compatible `/v1/chat/completions`. One SDK eliminates provider-specific client maintenance. Named `GroqService` for backward compatibility with existing import sites despite serving all providers.

**Alternatives Considered**: Individual SDKs per provider (`groq`, `anthropic`, etc.). Rejected: adds dependencies, requires multi-provider abstraction layer.

**Tradeoffs**: Custom/local providers with non-standard endpoints may have quirks. Provider label is cosmetic — actual routing is entirely via `base_url`.

---

## 5. LLM Profile System (Multi-Profile Config)

**Decision**: LLM configuration uses a `llm_profiles` list (with `name`, `provider`, `api_key`, `model`, `base_url`) and an `llm_active_profile` key in config.json, replacing flat keys.

**Reason**: Users often want to switch between providers (e.g., Groq for speed, LM Studio for offline). Multiple saved profiles avoid re-entering credentials each time.

**Alternatives Considered**: Single-profile flat config (original design). Migrated via one-time migration in `load_config()` that converts old `groq_api_key`/`groq_model` keys.

**Tradeoffs**: Migration runs once and persists. Old keys (`groq_api_key`, `groq_model`) kept in `DEFAULT_CONFIG` only for migration path.

---

## 6. Analysis Accuracy Algorithm (Lichess-Derived)

**Decision**: Per-game accuracy uses the average of a **volatility-weighted mean** and **harmonic mean** of per-move accuracies, replicating the Lichess algorithm.

**Reason**: Simple arithmetic mean over-rewards consistent mediocre play. The Lichess approach weights critical positions (high volatility windows) more heavily and penalizes catastrophic moves (harmonic mean collapses on very low values).

**Source**: `https://github.com/lichess-org/lila/blob/master/modules/analyse/src/main/AccuracyPercent.scala`

**Alternatives Considered**: Chess.com-style accuracy (ACPL-to-accuracy mapping). Rejected: less transparent formula, harder to reproduce.

**Tradeoffs**: Minimum accuracy floor of 10% prevents harmonic mean from collapsing to near-zero from a single outlier. Book moves, checkmate moves, and mating moves are forcibly set to 100%.

---

## 7. Engine Resource Defaults (Anti-Overheating)

**Decision**: Default to `multi_pv=1`, `engine_threads=min(cpu_count, 4)`, `engine_hash=64MB`.

**Reason**: Issue #5 identified that `multi_pv=3` (previous default) roughly triples the search tree, pinning laptop CPU cores. The conservative defaults prevent thermal throttling on fanless machines (e.g., MacBook Air).

**Alternatives Considered**: Let users configure everything from first launch. Rejected: bad default UX for non-technical users.

**Tradeoffs**: Power users may find analysis slower. They can raise `Threads`, `Hash`, `multi_pv`, and `analysis_depth` in Settings. `engine_threads` and `engine_hash` are intentionally absent from `DEFAULT_CONFIG` so `options_from_config()` falls back to its own module-level defaults (a `None` stored value would bypass the fallback).

---

## 8. Game ID as MD5 Hash of PGN Content

**Decision**: `game_id = hashlib.md5(pgn_content.encode()).hexdigest()`

**Reason**: Deterministic — the same game loaded twice produces the same ID, triggering `INSERT OR REPLACE` instead of duplicating the history entry.

**Alternatives Considered**: UUID (random). Rejected: would create duplicate entries on re-analysis.

**Tradeoffs**: Minor hash collision risk (negligible for this use case). Cosmetic metadata edits to PGN produce a different ID and a new history entry.

---

## 9. PyInstaller Packaging with `_MEIPASS` Detection

**Decision**: `get_resource_path()` checks `sys._MEIPASS` to resolve asset paths for both dev and frozen (PyInstaller) contexts.

**Reason**: PyInstaller extracts bundled files to a temp directory at runtime (`_MEIPASS`). Without this detection, asset paths valid in dev are broken in the distributed executable.

**Alternatives Considered**: `importlib.resources` (Python 3.9+). Rejected: less compatible with PyInstaller's bundling model without additional configuration.

**Tradeoffs**: All asset accesses must go through `get_resource_path()` or `get_user_data_dir()` — never use bare relative paths.

---

## 10. Update Checker Rate-Limiting (Once Per Day)

**Decision**: `MainWindow.check_for_updates()` stores `last_update_check` date in config and skips if already checked today.

**Reason**: Avoid hammering the GitHub API on every app launch, and respect API rate limits.

**Tradeoffs**: Users will not see updates released intraday until the next day's first launch.

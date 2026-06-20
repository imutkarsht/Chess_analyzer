# Lessons Learned — Chess Analyzer Pro

---

**Problem**: `multi_pv=3` (or higher) caused laptop CPU to pin at 100% and thermal throttle during analysis, especially on MacBook Air.

**Root Cause**: Stockfish evaluates N principal variations independently for each position. `multi_pv=3` roughly triples the search work per position across an entire game (50–100 positions).

**Solution**: Default `multi_pv=1` in `ConfigManager.DEFAULT_CONFIG`. Users who need multi-PV lines for live analysis can enable them in Settings. See issue #5.

**Future Prevention**: Never raise `multi_pv` default above 1. Document in Settings UI that higher values significantly increase CPU usage. Keep `engine_threads` and `engine_hash` out of `DEFAULT_CONFIG` (use module-level fallbacks in `engine.py`) so a stored `None` doesn't shadow the conservative defaults.

---

**Problem**: Duplicate game entries saved to history when the same game was analyzed multiple times.

**Root Cause**: Original implementation used UUID for `game_id`, generating a new random ID each time.

**Solution**: Changed `game_id` to `hashlib.md5(pgn_content)`. Same PGN → same ID → `INSERT OR REPLACE` in SQLite overwrites the old entry.

**Future Prevention**: Always derive game IDs deterministically from content, not randomly.

---

**Problem**: Engine evaluation score sign convention caused incorrect move classification for Black's moves.

**Root Cause**: Stockfish returns scores **relative to the side to move** (positive = current side is winning). If stored as-is, Black's moves appear as white-perspective scores, inverting all comparisons.

**Solution**: In `_process_analysis_results()`, flip `cp` and `mate` when `not is_white_turn` before storing in `MoveAnalysis`. All downstream code then assumes White-perspective convention.

**Future Prevention**: The conversion must happen in exactly one place (`_process_analysis_results`). The final position's score requires special handling in `_get_next_eval()` since the board is advanced beyond the last move.

---

**Problem**: Win probability harmonic mean collapsed to near-zero when any single move had very low accuracy (e.g., a catastrophic blunder in an otherwise solid game).

**Root Cause**: Harmonic mean is dominated by its smallest element. A single `0.001` accuracy pulls the result toward zero.

**Solution**: Enforced a minimum floor of `10.0%` per move accuracy before computing the harmonic mean. Book moves, checkmate moves, and moves leading to forced mate are overridden to `100.0%`.

**Future Prevention**: Always cap minimum per-move accuracy before feeding into harmonic mean. Document the floor value and its rationale (same approach as Lichess source).

---

**Problem**: `ConfigManager` instances in tight loops (e.g., per-move analysis callbacks) causing repeated JSON reads.

**Root Cause**: Before singleton pattern was implemented, each `ConfigManager()` instantiation called `load_config()`, reading disk on every call.

**Solution**: Class-level `_shared_config` dict shared across all instances. Only the first instantiation (per path) reads from disk. `reload_config()` updates the shared dict in-place.

**Future Prevention**: Always instantiate `ConfigManager` once per class/module, not inside loops. Use `config_manager.get(key)` — never read JSON files directly.

---

**Problem**: Window appeared off-screen after a monitor configuration change (e.g., external monitor disconnected).

**Root Cause**: Saved window position (`window_state.x/y`) from a multi-monitor setup was outside the bounds of the new single-monitor setup.

**Solution**: In `_restore_window_state()`, check that the restored geometry intersects at least one available screen via `QGuiApplication.screens()` before calling `self.move()`.

**Future Prevention**: Always validate saved window positions against current screen geometry before restoring. Also guard against `True/False` booleans stored as geometry values (Python's `isinstance(True, int)` is `True`).

---

**Problem**: `[%clk]` timestamps in PGN files with out-of-range minute/second values (e.g., `[0:99:00]`) were silently parsed as valid, injecting garbage time data.

**Root Cause**: Regex correctly matched the format but did no range validation.

**Solution**: Added range guards in `_parse_clk()`: minutes must be 0–59, seconds integer part must be 0–59. Out-of-range returns `(None, None)` and is treated as "no clock data."

**Future Prevention**: Always validate parsed time fields before using deltas. A negative `time_spent` would indicate a parse error.

---

**Problem**: Qt stylesheet with `background + border-radius` on `QLabel` inside `QStatusBar` rendered as a plain rectangle without rounded corners.

**Root Cause**: Qt's CSS rendering for status bar labels ignores border-radius for background painting.

**Solution**: Use colored text only for the engine status pill (`color: #27ae60` for Ready, etc.) rather than a colored background pill.

**Future Prevention**: Avoid relying on `border-radius` for `QLabel` inside `QStatusBar`. Use `QPushButton` or custom `QWidget` paint if a pill shape is needed.

---

**Problem**: Lichess API returned PGN games in a streaming format that `chess.pgn.read_game()` could not parse when multiple games were concatenated without proper separation.

**Root Cause**: Lichess bulk export streams games with `\n\n` separators but some edge cases had missing blank lines between games.

**Solution**: `PGNParser.parse_pgn_text()` already handles this correctly by looping `chess.pgn.read_game()` on a `StringIO` object until `None` is returned. No special separator handling needed for well-formed PGN.

**Future Prevention**: Always use the `while game := chess.pgn.read_game(io_stream):` loop pattern for multi-game PGN. Do not pre-split by `\n\n`.

---

**Problem**: Chess960 castling moves were sent to Stockfish in standard notation (`e1g1`) instead of Chess960 notation (`e1h1` — king to rook square), causing `IllegalMoveError`.

**Root Cause**: `UCI_Chess960` option not set on the engine before analyzing Chess960 games.

**Solution**: `Analyzer._analyze_positions()` calls `engine_manager.set_chess960_mode(True)` when `game_analysis.metadata.chess960` is `True`. Also added FEN-based Chess960 detection in `PGNParser` (checking for non-KQkq castling characters).

**Future Prevention**: Always detect Chess960 from `board.chess960` (set by python-chess from Variant header) or FEN castling field. Set `UCI_Chess960` on the engine before analysis. Note: Stockfish 16+ auto-manages this — `set_chess960_mode()` is wrapped in try/except for forward compatibility.

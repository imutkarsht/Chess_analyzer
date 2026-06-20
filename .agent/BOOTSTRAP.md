# Bootstrap — Chess Analyzer Pro

> **Read this first.** This file gives you the fastest path to working effectively in this codebase. Spend 2 minutes here before opening any source file.

---

## What Is This Project?

A **local-first Python desktop app** for analyzing chess games. It wraps the Stockfish engine with a PyQt6 GUI, stores results in SQLite, and optionally calls an LLM for AI summaries.

```
python main.py          # Run the app
python -m pytest tests/ # Run the test suite
```

---

## Knowledge Base Map

| File | Read When |
|---|---|
| **BOOTSTRAP.md** ← you are here | Starting any task |
| [AGENTS.md](AGENTS.md) | Need architecture overview, conventions, critical constraints |
| [PROJECT_MAP.md](PROJECT_MAP.md) | Need to find a file, understand data flow, locate an entry point |
| [DECISIONS.md](DECISIONS.md) | Questioning a design choice or about to make an architectural change |
| [LESSONS.md](LESSONS.md) | Hitting a bug or unexpected behavior |
| [skills/analysis.md](skills/analysis.md) | Working on engine evaluation, move classification, accuracy |
| [skills/storage.md](skills/storage.md) | Working on SQLite, PGN parsing, config, data models |
| [skills/gui.md](skills/gui.md) | Working on any PyQt6 widget, theming, or threading |
| [skills/api.md](skills/api.md) | Working on LLM integration, Chess.com/Lichess import, auto-updater |

---

## 5 Things You Must Know Before Touching Code

1. **Score convention**: Engine scores are **White-perspective** in storage (positive = White winning). Stockfish returns relative-to-side-to-move — flipping happens in `_process_analysis_results()`. Don't flip anywhere else.

2. **ConfigManager is a singleton**: All `ConfigManager()` instances share one in-memory dict via `_shared_config`. Call `reload_config()` after external changes. Don't instantiate inside loops.

3. **Engine must be stopped after each analysis**: `Analyzer.analyze_game()` calls `engine_manager.stop_engine()` in a `finally` block. The engine must be restarted for each new analysis — this is intentional.

4. **No hardcoded colors in widgets**: All colors go through `src/gui/styles.py → Styles.COLOR_*`. Call `Styles.get_theme()` for the global stylesheet.

5. **Never use `print()` for logs**: Use `from src.utils.logger import logger` everywhere.

---

## Critical Default Values

| Setting | Default | Why |
|---|---|---|
| `multi_pv` | `1` | `multi_pv=3` caused laptop overheating (issue #5) |
| `engine_threads` | `min(cpu_count, 4)` | Laptop-safe; NOT in `DEFAULT_CONFIG` (intentional) |
| `engine_hash` | `64 MB` | Conservative; NOT in `DEFAULT_CONFIG` (intentional) |
| `analysis_depth` | `18` | In `DEFAULT_CONFIG` |

---

## Where Things Live at Runtime

| Data | Location |
|---|---|
| User config | `~/Library/Application Support/ChessAnalyzerPro/config.json` (macOS) |
| Engine cache + history | `…/ChessAnalyzerPro/analysis_cache.db` (same dir) |
| Assets (pieces, sounds) | `assets/` in repo root (resolved via `get_resource_path()`) |

---

## Most Common Task Starting Points

| Task | Start Here |
|---|---|
| Change how moves are classified | `src/backend/analysis/move_classifier.py:classify_move()` |
| Change accuracy calculation | `src/backend/analysis/math_utils.py` |
| Add/change a config setting | `src/utils/config.py:ConfigManager.DEFAULT_CONFIG` |
| Add a new LLM provider | `src/constants.py:PROVIDERS` dict (no other changes needed) |
| Add a new board theme | `src/gui/styles.py:Styles.BOARD_THEMES` dict |
| Change UI colors/theme | `src/gui/styles.py:Styles` class constants |
| Add a new history column | `src/backend/storage/game_history.py:_init_db()` `new_columns` list |
| Add a new page/view | `src/gui/main_window.py:setup_ui()` + `src/gui/components/sidebar.py` |

---

## Maintenance Reminder

At the end of every completed task, update:
- `AGENTS.md` — if architecture changed
- `PROJECT_MAP.md` — if files moved or new modules added
- `DECISIONS.md` — if a significant design choice was made
- `LESSONS.md` — if you hit a non-obvious bug
- Relevant `skills/*.md` — if subsystem behavior changed

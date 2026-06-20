# Chess Analyzer Pro — Agent Knowledge Base

## Project Purpose
Chess Analyzer Pro is a local-first Python desktop application for analyzing chess games. It integrates Stockfish for engine evaluation, PyQt6 for the GUI, SQLite for persistence, and optional LLM providers (Groq, OpenAI, LM Studio, MiniMax) for AI-generated game summaries.

Current version: **2.0.1** (`src/constants.py`)  
Website: https://chess-analyzer-ut.vercel.app/

---

## High-Level Architecture

```
main.py  →  MainWindow (PyQt6)
              ├── Sidebar (4 pages: Analyze, History, Metrics, Settings)
              ├── BoardWidget       — interactive chessboard
              ├── MoveListPanel     — move history + live engine lines
              ├── AnalysisPanel     — eval graph, AI summary, multi-PV lines
              ├── HistoryView       — saved games list
              ├── MetricsView       — aggregate stats & coach AI insights
              └── SettingsView      — engine path, LLM profiles, themes

Backend (no Qt dependency):
  Analyzer  →  EngineManager (Stockfish UCI)
            →  AnalysisCache (SQLite)
            →  BookManager (opening book)
            →  GameHistoryManager (SQLite)
            →  PGNParser
            →  GroqService (OpenAI-compatible LLM)
```

---

## Main Technologies
| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| GUI | PyQt6 ≥ 6.4 |
| Chess logic | python-chess ≥ 1.9 |
| Engine | Stockfish (UCI protocol) |
| Database | SQLite via `sqlite3` stdlib |
| LLM | `openai` SDK (compatible with all providers) |
| Charts | Matplotlib ≥ 3.7 |
| Icons | qtawesome ≥ 1.2 |
| HTTP | `requests` ≥ 2.31 (API imports) |
| Config | JSON (`config.json` in platform user data dir) |
| Packaging | PyInstaller (`build.spec`) |
| Testing | pytest + pytest-qt + pytest-mock |

---

## Coding Conventions
- **Python typing**: All public functions use type hints; `Optional[X]` for nullable.
- **Dataclasses**: Core data models (`MoveAnalysis`, `GameMetadata`, `GameAnalysis`) live in `src/backend/storage/models.py` as `@dataclass`.
- **QThread workers**: Long-running tasks (analysis, AI summary, downloads) run in `QThread` subclasses and communicate via `pyqtSignal`.
- **ConfigManager singleton**: `ConfigManager` uses class-level `_shared_config` — all instances share state. Call `reload_config()` after external changes.
- **Score convention**: Evaluation scores are stored **relative to White** (positive = White better). Engine returns scores relative to side-to-move; conversion happens in `_process_analysis_results()`.
- **Logging**: Use `from src.utils.logger import logger` everywhere. Never use `print()` for internal messages.
- **Styles**: All Qt stylesheets go through `src/gui/styles.py → Styles` class. Never hardcode colors in widget files; use `Styles.COLOR_*` constants.
- **No cd**: Path utilities (`get_resource_path`, `get_user_data_dir`, `get_app_path`) handle dev vs PyInstaller contexts.

---

## Important Commands
```bash
# Run application
python main.py

# Run tests
python -m pytest tests/

# Install dependencies (recommended: uv)
uv pip install -r requirements.txt

# Build executable
pyinstaller build.spec
```

---

## Directory Responsibilities

| Path | Responsibility |
|---|---|
| `main.py` | Entry point, splash screen, Qt app lifecycle |
| `src/constants.py` | App version, API URLs, LLM provider catalogue, platform updater rules |
| `src/backend/analysis/` | Stockfish engine wrapper, move analysis loop, classification, accuracy math |
| `src/backend/api/` | Chess.com and Lichess REST API clients |
| `src/backend/services/` | LLM AI service (game summaries, coach insights) |
| `src/backend/storage/` | SQLite cache, game history, PGN parser, data models |
| `src/backend/updater/` | GitHub release checker, platform-specific installer/hot-swap |
| `src/gui/analysis/` | Analysis panel widgets, move list, live engine lines widget |
| `src/gui/board/` | Chessboard widget, eval bar, piece themes |
| `src/gui/components/` | Shared reusable widgets (game list, stat cards, graph, sidebar, loading overlay) |
| `src/gui/dialogs/` | All dialog windows (load game, splash, update notification, shortcuts) |
| `src/gui/metrics/` | Matplotlib-based stat charts and background worker |
| `src/gui/views/` | Full page views (analysis, history, metrics, settings) |
| `src/gui/styles.py` | Centralised dark theme, color constants, Qt stylesheet generators |
| `src/utils/config.py` | ConfigManager: loads/saves `config.json`, migration logic |
| `src/utils/path_utils.py` | Cross-platform path resolution (dev vs frozen/PyInstaller) |
| `src/utils/logger.py` | Shared logger instance |
| `src/utils/resources.py` | ResourceManager: sound playback |
| `assets/` | Images, piece SVGs, sound files |
| `tests/` | pytest test suite |

---

## User Data Storage (platform-specific)
All runtime data is stored outside the project directory:
- **macOS**: `~/Library/Application Support/ChessAnalyzerPro/`
- **Windows**: `%APPDATA%\ChessAnalyzerPro\`
- **Linux**: `~/.local/share/chessanalyzerpro/`

Files stored:
- `config.json` — user preferences
- `analysis_cache.db` — SQLite: both `analysis` table (engine cache) and `games` table (history)

---

## Common Development Workflows

### Adding a new LLM provider
1. Add entry to `PROVIDERS` dict in `src/constants.py`.
2. `GroqService._connect()` auto-picks up the new provider — no changes needed there.
3. Add to `_PROVIDER_LABELS` in `src/utils/config.py` for migration display name.

### Adding a new setting
1. Add key + default to `ConfigManager.DEFAULT_CONFIG`.
2. Add UI in `src/gui/views/settings_view.py`.
3. Read via `config_manager.get("key", default)` wherever needed.

### Adding a new board theme
1. Add entry to `Styles.BOARD_THEMES` in `src/gui/styles.py`.

### Running analysis manually (without GUI)
```python
from src.backend.analysis.engine import EngineManager
from src.backend.analysis.analyzer import Analyzer
from src.backend.storage.pgn_parser import PGNParser

engine = EngineManager("/path/to/stockfish")
analyzer = Analyzer(engine)
games = PGNParser.parse_pgn_file("game.pgn")
analyzer.analyze_game(games[0])
```

---

## Critical Constraints
- **Engine stops after analysis**: `engine_manager.stop_engine()` is called in `Analyzer.analyze_game()` finally block. The engine must be restarted for each analysis.
- **Cache key is FEN + multi_pv** (not depth): Depth is stored separately and used as a "minimum depth" guard.
- **ConfigManager shares state**: Do not instantiate in tight loops. One instance per class is fine; they share `_shared_config`.
- **Chess960 support**: Set `UCI_Chess960` on engine and use `chess.Board(chess960=True)`. FEN-based detection is in `PGNParser`.
- **Overheating prevention**: Default `multi_pv=1`, `engine_threads=min(cpu_count, 4)`, `engine_hash=64MB`. Raising `multi_pv` to 3+ was identified as causing laptop overheating (issue #5).
- **Score normalization**: Engine returns scores relative to side-to-move. Always convert to White-perspective before storing in `MoveAnalysis.eval_before_cp`.
- **Game ID**: MD5 hash of the raw PGN string — prevents duplicate saves.

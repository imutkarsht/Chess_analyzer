# Project Map — Chess Analyzer Pro

## Repository Root
```
Chess_analyzer/
├── main.py                    # Entry point: Qt app, splash screen
├── requirements.txt           # Runtime + dev dependencies
├── build.spec                 # PyInstaller packaging spec
├── config.example.json        # Template for config.json
├── src/                       # All source code
├── tests/                     # pytest suite
├── assets/                    # Images, sounds, piece SVGs
└── installers/                # Platform installer scripts
```

---

## src/ — Source Tree

### `src/constants.py`
Global constants. Key items:
- `APP_VERSION` — bump here for releases
- `GITHUB_RELEASES_API` — URL for update checking
- `SRC_PGN_FILE/TEXT/CHESSCOM/LICHESS` — load source IDs (0–3)
- `PLATFORM_RULES` — per-OS installer suffix rules for updater
- `PROVIDERS` — dict of all LLM providers (Groq, OpenAI, LM Studio, MiniMax, Custom)

### `src/backend/`

#### `analysis/`
| File | Purpose |
|---|---|
| `analyzer.py` | `Analyzer` class — main analysis orchestrator |
| `engine.py` | `EngineManager` — Stockfish UCI wrapper, thread-safe start/stop |
| `move_classifier.py` | `classify_move()` — assigns Brilliant/Best/Blunder/etc. labels |
| `math_utils.py` | Win probability, move accuracy, volatility weights, harmonic mean |
| `book.py` | `BookManager` — opening book lookup |

#### `api/`
| File | Purpose |
|---|---|
| `base_api.py` | Abstract base for API clients |
| `chess_com_api.py` | `ChessComAPI` — fetch games by username or URL |
| `lichess_api.py` | `LichessAPI` — fetch games by username or URL (supports OAuth token) |

#### `services/`
| File | Purpose |
|---|---|
| `groq_service.py` | `GroqService` — provider-agnostic LLM client; `generate_summary()`, `generate_coach_insights()` |

#### `storage/`
| File | Purpose |
|---|---|
| `models.py` | `MoveAnalysis`, `GameMetadata`, `GameAnalysis` dataclasses |
| `pgn_parser.py` | `PGNParser` — file/text PGN → `GameAnalysis` objects; parses `[%clk]` clock annotations |
| `cache.py` | `AnalysisCache` — SQLite engine result cache (key: SHA256 of FEN+multi_pv) |
| `game_history.py` | `GameHistoryManager` — SQLite CRUD for analyzed games |

#### `updater/`
| File | Purpose |
|---|---|
| `update_checker.py` | `UpdateCheckerWorker` (QThread) — polls GitHub Releases API |
| `updater.py` | `DownloadWorker` (QThread), `install_and_quit()` — platform-specific installers |

### `src/gui/`

#### `main_window.py`
`MainWindow(QMainWindow)` — central hub (998 lines). Owns all views, wires signals between backend and frontend. Key methods:
- `setup_ui()` — creates 4-page QStackedWidget + sidebar
- `load_game()` — loads `GameAnalysis` into all views
- `start_analysis()` — kicks off `AnalysisWorker` thread
- `check_for_updates()` — rate-limited to once/day via config

#### `styles.py`
`Styles` class — static dark theme. All color constants prefixed `COLOR_`. Key classmethod APIs:
- `get_theme()` → global Qt stylesheet string
- `get_class_color(classification)` → hex color for move classification
- `set_accent_color(hex)` → runtime accent change
- `BOARD_THEMES` dict → board color presets

#### `board/`
| File | Purpose |
|---|---|
| `board_widget.py` | `BoardWidget` — renders chessboard with SVG pieces, drag/drop, last-move highlight |
| `eval_bar.py` | `EvalBar` — vertical evaluation bar |
| `piece_themes.py` | `PieceThemeManager` — maps theme names to SVG piece directories |

#### `analysis/`
| File | Purpose |
|---|---|
| `analysis_panel.py` | `AnalysisPanel` — right panel: eval graph, multi-PV lines, AI summary tab |
| `analysis_lines_widget.py` | `AnalysisLinesWidget` — multi-PV engine lines display |
| `analysis_worker.py` | `AnalysisWorker(QThread)` — runs `Analyzer.analyze_game()` off-thread |
| `move_list_panel.py` | `MoveListPanel` — scrollable move list with classification badges |
| `live_analysis.py` | Live engine lines worker (runs during move browsing) |
| `captured.py` | `CapturedPiecesWidget` — shows captured pieces above/below board |
| `controls.py` | `GameControlsWidget` — first/prev/next/last/flip buttons |
| `move_cell_widget.py` | Single move row widget with classification icon |
| `think_time_bar.py` | Per-move clock bar visualization |

#### `components/`
| File | Purpose |
|---|---|
| `sidebar.py` | `Sidebar` — left nav with 4 icon buttons, emits `page_changed` |
| `graph_widget.py` | `GraphWidget` — Matplotlib evaluation graph, emits `move_clicked` |
| `game_list_widget.py` | `GameListWidget` — game list for history view |
| `game_list_item_widget.py` | Single game card widget |
| `stat_card.py` | `StatCard` — metric display card |
| `loading_widget.py` | `LoadingOverlay` — full-window loading spinner |
| `skeleton_widget.py` | Skeleton loading placeholder |
| `masonry_layout.py` | Custom masonry/waterfall layout |
| `stats_layout.py` | Stats grid layout helper |

#### `dialogs/`
| File | Purpose |
|---|---|
| `load_game_dialog.py` | `LoadGameDialog` — tabbed dialog: PGN file/text/Chess.com/Lichess |
| `load_game/` | Submodule with per-tab loading widgets |
| `game_selection_dialog.py` | Multi-game picker (when PGN has multiple games) |
| `update_dialog.py` | `UpdateNotificationDialog` — download + install flow |
| `splash_screen.py` | `SplashScreen` — startup splash with progress |
| `shortcut_help_dialog.py` | Keyboard shortcuts reference |

#### `views/`
| File | Purpose |
|---|---|
| `analysis_view.py` | Re-exports `MoveListPanel`, `AnalysisPanel` (thin shim) |
| `history_view.py` | `HistoryView` — full history page with search, delete, export/import CSV |
| `metrics_view.py` | `MetricsWidget` — stats dashboard with coach AI insights |
| `settings_view.py` | `SettingsView` — engine, LLM profiles, themes, usernames |
| `metrics/` | `charts.py` (Matplotlib chart widgets), `workers.py` (QThread data loaders) |
| `settings/` | Settings sub-widgets |

### `src/utils/`
| File | Purpose |
|---|---|
| `config.py` | `ConfigManager` — JSON config with singleton pattern + migration |
| `path_utils.py` | `get_resource_path()`, `get_app_path()`, `get_user_data_dir()` |
| `logger.py` | Shared `logging.Logger` instance |
| `resources.py` | `ResourceManager` — sound playback |

---

## Data Flow

### Game Load Flow
```
User → LoadGameDialog → PGNParser.parse_pgn_text()
     → GameAnalysis (moves: List[MoveAnalysis])
     → MainWindow.load_game()
     → BoardWidget, MoveListPanel, AnalysisPanel (all receive same GameAnalysis)
```

### Analysis Flow
```
User clicks "Analyze"
  → AnalysisWorker(QThread).run()
    → Analyzer.analyze_game(game_analysis, callback)
      → _analyze_positions(): for each move:
          AnalysisCache.get_analysis(fen) OR EngineManager.analyze_position(board)
          → AnalysisCache.save_analysis()
          → _process_analysis_results() → populates MoveAnalysis fields
      → _analyze_final_position()
      → _classify_and_calculate_stats()
          → classify_move() → MoveAnalysis.classification
          → calculate_move_accuracy() → per-move accuracy %
          → _calculate_final_accuracy() → Lichess algorithm (volatility-weighted mean + harmonic mean)
      → GameHistoryManager.save_game()
  → AnalysisWorker signals → MainWindow updates all widgets
```

### LLM Summary Flow
```
User clicks "Generate AI Summary"
  → GroqService.generate_summary(pgn, analysis_summary) 
  → OpenAI SDK → provider endpoint
  → Response displayed in AnalysisPanel summary tab
```

### Config Load
```
App start → ConfigManager.__init__() → load_config()
  → Checks for migration (flat keys → llm_profiles list)
  → Shared via class-level _shared_config (singleton)
  → All instances share same dict in memory
```

---

## Key Entry Points
| Purpose | Location |
|---|---|
| Launch app | `python main.py` |
| Analysis logic | `src/backend/analysis/analyzer.py:Analyzer.analyze_game()` |
| Move classification | `src/backend/analysis/move_classifier.py:classify_move()` |
| Win probability | `src/backend/analysis/math_utils.py:get_win_probability()` |
| Config access | `src/utils/config.py:ConfigManager.get(key, default)` |
| User data path | `src/utils/path_utils.py:get_user_data_dir()` |
| Database | `src/backend/storage/game_history.py:GameHistoryManager` |

---

## Important Integrations
| Integration | Details |
|---|---|
| Stockfish | UCI protocol via `chess.engine.SimpleEngine.popen_uci()`. Path configurable. |
| Chess.com API | `https://api.chess.com/pub` — requires User-Agent header |
| Lichess API | `https://lichess.org/api/games/user` — OAuth token optional |
| GitHub Releases | `https://api.github.com/repos/imutkarsht/Chess_analyzer/releases/latest` |
| LLM Providers | All use OpenAI-compatible `/v1/chat/completions` endpoint |

# Chess Analyzer Pro - Onboarding Guide

Welcome to the **Chess Analyzer Pro** codebase. This guide gets you from clone to
your first meaningful change. It is a tutorial, not the full reference — the
canonical file-by-file map, runtime flows, patterns and invariants live in
[architecture.md](architecture.md).

---

## 1. Project Overview

**Chess Analyzer Pro** is a local-first desktop application built with **Python**
and **PyQt6**. It analyses chess games with **Stockfish** (UCI), classifies
moves, aggregates performance metrics, explores openings, and optionally adds
grounded AI coaching through any OpenAI-compatible endpoint.

### Key technologies

- **Language:** Python 3.10+
- **GUI:** PyQt6 (plus QtAwesome icons and Matplotlib charts)
- **Chess logic:** `python-chess`
- **Engine:** Stockfish over UCI
- **Persistence:** SQLite (`analysis_cache.db`, WAL mode) and JSON (`config.json`)
- **Credentials:** `keyring` (OS credential store)
- **AI:** `openai` SDK against Groq, LM Studio, MiniMax, or a custom endpoint
- **Networking:** `requests` with bundled `certifi` CAs
- **Tooling:** Ruff, pytest, pytest-qt, PyInstaller

---

## 2. Directory Structure

```text
Chess_analyzer/
├── main.py                     # Entry point: high-DPI, splash, MainWindow
├── assets/                     # Images, icons, sounds, piece SVGs
├── src/
│   ├── constants.py            # Version, URLs, provider presets, DEFAULT_BOARD_THEME
│   ├── config/
│   │   └── settings_schema.py  # Single source of settings defaults/validation
│   ├── backend/                # Pure Python, zero Qt imports
│   │   ├── analysis/           # Analyzer, engine, classification, books, variations
│   │   │   ├── metrics/        # Stats aggregation + coach dossier
│   │   │   └── tactics/        # Motifs, phases, SEE, hanging pieces, insight
│   │   ├── api/                # Chess.com & Lichess clients
│   │   ├── cache/              # API response cache facade
│   │   ├── engine/             # Stockfish downloader/validator
│   │   ├── models/             # Cross-layer models (GameInfo)
│   │   ├── services/           # LLM + feedback services
│   │   ├── storage/            # Repos, migrations, PGN, backup, caches
│   │   └── updater/            # Release checks and installers
│   ├── gui/                    # PyQt6 presentation layer
│   │   ├── main_window/        # MainWindow + focused mixins
│   │   ├── views/              # Pages (+ metrics/ and settings/ subpackages)
│   │   ├── analysis/           # Board analysis, move list, coach, variations
│   │   ├── board/              # The single configurable Board
│   │   ├── components/         # controls/ display/ feedback/ layout/ lists/
│   │   ├── dialogs/            # load_game/, wizard/, feedback, errors, updates
│   │   ├── engine_lines/       # Shared live session + engine-lines widget
│   │   ├── metrics/            # Drill-down and chart helpers
│   │   ├── theme/              # Palettes, tokens, motion, OS detection
│   │   ├── utils/              # Debounce, shortcuts, smooth scroll, factories
│   │   └── styles.py           # QSS generators driven by the live palette
│   └── utils/                  # logger, config, paths, resources, secrets
├── tests/                      # backend/, gui/, storage/ suites
├── docs/                       # architecture.md, this guide, user guide
├── planning/                   # 2.5.0 progress and feature plans
├── installers/                 # Platform packaging
├── build.spec                  # PyInstaller definition
├── requirements.txt
└── requirements-dev.txt
```

> Runtime files (`config.json`, `analysis_cache.db`, logs, backups) live in the
> OS user-data directory, never in the repo. See
> [How_to_use.md](How_to_use.md#3-configuration--data-files).

---

## 3. Architecture & Data Flow

The app is layered:

```text
main.py → src/gui (presentation) → src/backend (domain) → SQLite / Stockfish
```

1. **Model/domain (`src/backend/`)** — `Analyzer`, `EngineManager`,
   `MoveClassifier`, metrics/tactics, repositories, PGN parsing. No Qt.
2. **View (`src/gui/`)** — `MainWindow` composes pages; widgets render state and
   dispatch actions. Shared widgets come from `src.gui.components`.
3. **Controller/glue** — Qt signals connect UI events to workers, which call
   domain services and emit results back.

### Where to look first

| Area | Files |
| --- | --- |
| Window composition | `src/gui/main_window/window.py` + mixins |
| Analysis pipeline | `src/backend/analysis/analyzer.py`, `engine.py`, `gui/analysis/analysis_worker.py` |
| Move classification | `src/backend/analysis/move_classifier.py` |
| AI Coach | `src/backend/analysis/tactics/insight.py`, `services/groq_service.py`, `gui/analysis/coach_worker.py` |
| Variations | `src/backend/analysis/variation_tree.py`, `gui/analysis/variation_mode.py` |
| Settings | `src/config/settings_schema.py`, `gui/views/settings/` |
| History | `src/gui/views/history_view.py`, `backend/storage/games_repo.py` |
| Metrics | `src/backend/analysis/metrics/`, `gui/views/metrics/` |
| Shared components | `src/gui/components/` (import via the facade) |
| Styling/theming | `src/gui/theme/`, `src/gui/styles.py` |

For every module's purpose and the allowed dependency edges, see
[architecture.md](architecture.md#2-system-overview).

---

## 4. The patterns you must follow

### Components

Import shared widgets from the facade only:

```python
from src.gui.components import Button, ButtonVariant, Input, Select, Tabs
```

Never construct raw `QPushButton`, `QLineEdit`, or `QComboBox`, and never write
widget-local QSS. Use:

| Need | Component |
| --- | --- |
| Action | `Button` / `create_button` / `create_icon_button` |
| Text entry | `Input`, `TextArea` |
| Dropdown | `Select` |
| Tabs | `Tabs` |
| Date | `DatePicker` |
| Notification | `ToastManager` |
| Paging | `PaginationBar` |
| Empty state | `EmptyState` |
| Status pill | `StatusBadge` |
| Chips | `SegmentedControl` |
| Bars/legends | `MiniBar`, `SegmentedBar`, `LegendList` |

### Theming

- Colours come from `Styles.COLOR_*` and `gui/theme/palette.py`.
- Each control's look comes from a `Styles.get_*_qss()` generator.
- Per-widget styles must be rebuilt on theme/accent change. Capture palette
  values inside a `_refresh_*_styles()` method, not in `__init__`.

### Settings

Add settings to `src/config/settings_schema.py` (default, type, validation,
`apply="live"` if it should take effect immediately). Build the control in
`src/gui/views/settings/` with `SettingsForm`/`SettingsBinder`. Credentials go
through `SecretStore`, never plaintext JSON.

### Background work

Engine analysis, API calls, and LLM requests run in `QThread` subclasses and
communicate with signals. Never block the Qt event loop, and always cancel and
clean up workers on close.

---

## 5. How-To Guides (Making Changes)

### Scenario A: Change how “Blunders” are defined

**File:** `src/backend/analysis/move_classifier.py`

1. Locate the classification thresholds.
2. Adjust them and update the classifier tests.
3. Keep the White-perspective score contract intact.

### Scenario B: Add a column to the Move List

**Files:** `src/gui/analysis/move_list_panel.py`,
`src/gui/analysis/move_cell_widget.py`

1. Update the table columns/headers in `move_list_panel.py`.
2. Render the new value in the cell widget.
3. Add a GUI test.

### Scenario C: Change the app's colour theme

**Files:** `src/gui/theme/palette.py`, `src/gui/styles.py`

1. Edit the `LIGHT`/`DARK` palettes (or `BOARD_THEMES`).
2. QSS generators read the palette automatically.
3. Verify per-widget refresh methods still run on theme change.

### Scenario D: Add a setting end-to-end

1. Add a `SettingSpec` to `src/config/settings_schema.py`.
2. Add the control to the matching card in `src/gui/views/settings/`.
3. Wire the live-apply slot in `SettingsView`/`MainWindow` if needed.
4. Test persistence and the live branch.

### Scenario E: Add a game-loading source

1. Create a client in `src/backend/api/` extending `BaseChessAPI`.
2. Add a panel in `src/gui/dialogs/load_game/` and wire it into
   `LoadGameDialog`.
3. Run requests through `ApiWorker`, respect `import_limits.py`, and normalise to
   `GameInfo`/`GameAnalysis`.
4. Mock the HTTP client in tests.

### Scenario F: Add a shared component

1. Add it under the right `src/gui/components/<group>/` subpackage.
2. Export it from `src/gui/components/__init__.py`.
3. Generate its style from `Styles`; restyle on theme change.
4. Add a `pytest-qt` test.

---

## 6. Running the Application

### Prerequisites

1. Python 3.10+.
2. Stockfish (or use the in-app downloader).

### Setup

```bash
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows

pip install -r requirements-dev.txt
python main.py
```

On first run, the Setup Wizard configures the engine, theme, and optional
integrations.

---

## 7. Testing

```bash
# Full suite (should finish in under 20 seconds)
pytest tests/

# Headless Linux/CI
QT_QPA_PLATFORM=offscreen pytest tests/

# One file
pytest tests/backend/test_analyzer.py

# Branch coverage (85% floor, GUI excluded)
pytest tests/ --cov=src --cov-branch --cov-report=term-missing
```

When adding tests:

- Cover meaningful behaviour, calculations, state changes, and failure paths —
  not line counts.
- Do not lower `fail_under` or exclude modules to make the gate pass.
- Extend or parameterize existing tests; delete smoke-only duplicates.
- Never use `time.sleep()`, `QTest.qWait()`, or real timeouts. Run workers
  synchronously or inject fake clocks.
- Mock every HTTP and LLM call; tests must pass offline.
- Use `tmp_path`/`tmp_path_factory`; never touch real user data.
- Keep tests cross-platform (`pathlib.Path`, no POSIX-only assertions).

Full rules: [CONTRIBUTING.md](../CONTRIBUTING.md#8-test-quality-expectations).

---

## 8. Troubleshooting

- **“Engine not found”**: point Settings → Chess Engine at the Stockfish
  **executable**, not the folder.
- **“API key error”**: activate a valid LLM profile in Settings → AI Coach.
- **Logs**: `chess_analyzer.log` in the OS user-data directory
  (`~/Library/Application Support/ChessAnalyzerPro` on macOS,
  `%APPDATA%\ChessAnalyzerPro` on Windows,
  `~/.local/share/chessanalyzerpro` on Linux).

---

## 9. Building from Source

```bash
pip install pyinstaller
pyinstaller build.spec
```

The bundle is written to `dist/`. `build.spec` includes assets and hidden imports
for PyQt6 and python-chess. Platform installers live in `installers/`.

---

## 10. Next Steps

- Read [architecture.md](architecture.md) for the file map and extension recipes.
- Read [CONTRIBUTING.md](../CONTRIBUTING.md) before opening a PR (issue-first).
- Check [planning/2.5.0_progress.md](../planning/2.5.0_progress.md) for release
  scope.

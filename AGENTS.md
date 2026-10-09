# Chess Analyzer Pro — Agent Guidelines

## 1. Project Overview
Chess Analyzer Pro is a local-first desktop application for in-depth chess game analysis. Built for desktop chess players, coaches, and enthusiasts, it provides unlimited offline game analysis using Stockfish (UCI), SQLite persistence, full Chess960 (Fischer Random) support, and optional AI-powered game coaching via OpenAI-compatible LLM endpoints. See [README.md](README.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 2. Critical Invariants (Must Never Regress)
- **Offline-First Functionality**: Core analysis, Stockfish engine, PGN parsing, opening books, and history caching must work with 0 internet connection. Network calls are strictly optional (APIs, updater, LLM).
- **Keep Heavy Compute Off the UI Thread**: All Stockfish analysis, API fetches, and LLM requests must execute in `QThread` subclasses communicating solely via `pyqtSignal`. Never block the Qt event loop.
- **White-Perspective Scores**: All evaluation scores in `MoveAnalysis` (`eval_before_cp`, `eval_after_cp`, etc.) are White-perspective (positive = White winning). Side-to-move conversion happens strictly during ingestion in `Analyzer._process_analysis_results()`. Never re-flip scores in GUI widgets.
- **Engine Lifecycle**: Engine must be stopped in a `finally` block (`engine_manager.stop_engine()`). A fresh analysis must restart the engine; do not assume it is running.
- **Thermal Safety (Issue #5)**: Default `multi_pv=1`, `threads=min(cpu_count, 4)`, `hash=64MB`. Multi-PV > 1 multiplies search workload and causes severe thermal throttling on laptops. Keep `threads`/`hash` out of `DEFAULT_CONFIG` so module fallbacks apply.
- **Deterministic Game Identity**: `game_id = hashlib.md5(pgn_content.encode()).hexdigest()`. Never use random UUIDs; content hashing prevents duplicate history records.
- **Accuracy Floor (10.0%)**: Accuracy uses Lichess volatility-weighted + harmonic mean. A strict 10.0% accuracy floor per move is required to prevent a single blunder from collapsing game accuracy to zero.
- **Chess960 Compatibility**: Detect non-standard castling tags. Set `engine.configure({"UCI_Chess960": "true"})` and instantiate boards with `chess.Board(fen, chess960=True)`.

---

## 3. Tech Stack
- **Language**: Python 3.10+
- **GUI**: PyQt6 (≥6.4.0), QtAwesome (icons), Matplotlib (embedded charts)
- **Chess Engine & Logic**: python-chess (≥1.9.0), Stockfish (UCI protocol)
- **Persistence**: SQLite 3 (`analysis_cache.db`, WAL mode enabled), JSON (`config.json`)
- **LLM Integration**: `openai` Python SDK (≥1.0.0; compatible with Groq, OpenAI, LM Studio, MiniMax)
- **Tooling & Packaging**: Ruff (lint & format), pytest & pytest-qt (tests), PyInstaller (builds)
- **Package Manager**: `pip` or `uv`

---

## 4. Architecture & Boundaries
```
src/
├── constants.py            # App version (2.3.0), URLs, provider presets (Single source of truth)
├── backend/                # Pure Python. Zero Qt imports. Headless & independently testable.
│   ├── analysis/           # EngineManager, Analyzer, MoveClassifier, MathUtils, Opening Books
│   ├── api/                # Chess.com & Lichess REST clients (rate-limited, timeout-protected)
│   ├── engine/             # Stockfish multi-platform downloader & binary validator
│   ├── services/           # GroqService (OpenAI SDK client for LLMs; provider-agnostic via base_url)
│   ├── storage/            # Models (dataclasses), AnalysisCache, GameHistoryManager, PGNParser
│   └── updater/            # GitHub release checker & platform installers
├── gui/                    # PyQt6 presentation layer. Threaded; zero business logic computation.
│   ├── board/              # BoardWidget (SVG pieces, arrows), EvalBar
│   ├── analysis/           # MoveListPanel, AnalysisPanel, LiveAnalysisWorker
│   ├── views/              # Full pages: Analyze, History, Metrics, Settings
│   ├── dialogs/            # LoadGameDialog, SetupWizard, UpdateDialog
│   ├── theme/ & styles.py  # Centralized CSS generators and color constants (Styles.COLOR_*)
└── utils/                  # Singletons: logger.py, config.py (ConfigManager), path_utils.py (Zero Qt)
```

**Boundaries**:
- UI components render state and dispatch user actions; domain logic remains strictly independent of Qt.
- Shared utilities (`src/utils/`) must never import GUI modules.
- External network clients must be accessed through explicit backend service interfaces.

---

## 5. Coding Standards
- **Typing**: Python 3.10+ modern syntax required: use `X | None` (never `Optional[X]`), `list[T]`, `dict[K, V]`.
- **Logging**: Use `from src.utils.logger import logger`. **Never use `print()`**. Sensitive tokens (`sk-...`, `gsk_...`, Bearer) are automatically redacted.
- **Styling**: **Never hardcode hex colors** in widget files. Use `Styles.COLOR_*` and generator helpers from `src/gui/styles.py`.
- **Paths**: Use `src/utils/path_utils.py` (`get_resource_path`, `get_user_data_dir`). Never hardcode `/` or `\\`. Never propose `cd` in terminal commands.
- **Config**: `ConfigManager` uses class-level `_shared_config`. Do not instantiate in tight loops; call `config_manager.reload_config()` after external file changes.
- **Comments**: Explain non-obvious domain rationale (e.g. why a formula requires a 10% floor), not self-evident code syntax.

---

## 6. Commands
- **Install Dependencies**: `pip install -r requirements-dev.txt` (or `uv pip install -r requirements-dev.txt`)
- **Start Development**: `python main.py`
- **Lint**: `ruff check .` (auto-fix: `ruff check --fix .`)
- **Format**: `ruff format --check .` (auto-format: `ruff format .`)
- **Run All Tests**: `pytest tests/` (Headless Linux: `QT_QPA_PLATFORM=offscreen pytest tests/`)
- **Run Single Test**: `pytest tests/backend/test_analyzer.py`
- **Production Build**: `pyinstaller build.spec`

---

## 7. Testing & Verification
- All pull requests must maintain 100% pass rate: `pytest tests/` (270+ unit and GUI tests).
- Backend logic changes require headless unit tests in `tests/backend/`.
- GUI widget changes require tests using `pytest-qt` in `tests/gui/`.
- Linting must report 0 errors: `ruff check . && ruff format --check .`.

---

## 8. Security & Boundaries
- **Never commit secrets**: No API keys, credentials, or private tokens in commits or test fixtures.
- **Never edit generated files**: Do not touch `build/`, `dist/`, `installers/*/Output/`, `*.db`, or `*.log`.
- **Never suppress lint rules**: Maintain 0 errors under `ruff check .` — do not add `# noqa` without permission.
- **Ask first before adding dependencies**: Protect PyInstaller bundle size. New packages require approval.
- **Input Validation**: Validate untrusted PGN strings, FEN inputs, and API responses at backend ingestion boundaries.

---

## 9. Change Workflow & Git Rules
1. **Inspect**: Understand existing code and boundaries before proposing edits.
2. **Plan**: For complex refactors, align on an implementation plan before modifying files.
3. **Implement**: Keep changes modular and focused. Avoid mixing refactors with bug fixes.
4. **Verify**: Always run `ruff check .` and `pytest tests/` before considering work complete.
5. **Git Hygiene**: Never run destructive Git commands (`git reset --hard`, force pushes). Write meaningful Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`).

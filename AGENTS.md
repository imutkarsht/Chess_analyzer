# Chess Analyzer Pro — Agent Guidelines

## 1. Project Overview
Chess Analyzer Pro is a local-first desktop application for in-depth chess game analysis. Built for desktop chess players, coaches, and enthusiasts, it provides unlimited offline game analysis using Stockfish (UCI), SQLite persistence, full Chess960 (Fischer Random) support, and optional AI-powered game coaching via OpenAI-compatible LLM endpoints. See [README.md](README.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 2. Critical Invariants (Must Never Regress)
- **Offline-First Functionality**: Core analysis, Stockfish engine, PGN parsing, opening books, and history caching must work with 0 internet connection. Network calls are strictly optional (APIs, updater, LLM).
- **Keep Heavy Compute Off the UI Thread**: All Stockfish analysis, API fetches, and LLM requests must execute in `QThread` subclasses communicating solely via `pyqtSignal`. Never block the Qt event loop.
- **White-Perspective Scores**: All evaluation scores in `MoveAnalysis` (`eval_before_cp`, `eval_after_cp`, etc.) are White-perspective (positive = White winning). Side-to-move conversion happens strictly during ingestion in `Analyzer._process_analysis_results()`. Never re-flip scores in GUI widgets.
- **Engine Lifecycle**: Engine must be stopped in a `finally` block (`engine_manager.stop_engine()`). A fresh analysis must restart the engine; do not assume it is running.
- **Thermal Safety (Issue #5)**: Default `multi_pv=2`, `engine_threads=1`, `engine_hash=128MB`; the UI recommends up to `min(cpu_count, 4)` threads. Multi-PV > 2 multiplies search workload and causes severe thermal throttling on laptops. Keep `threads`/`hash` out of `DEFAULT_CONFIG` so module fallbacks apply.
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
├── constants.py            # App version (2.4.0), URLs, provider presets (Single source of truth)
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
- **DRY & Single Source of Truth**:
  - **Schema & SQL**: Maintain a single column specification tuple/list (`GAME_COLUMNS`, `GAME_CSV_COLUMNS`). Derive DDL, INSERT statements with named parameters (`:col`), and row dicts from it. Never maintain separate out-of-sync column lists.
  - **Mappers & Serialization**: Model serialization belongs on the models (`MoveAnalysis.to_dict()` and `MoveAnalysis.from_dict()`). Never hand-write ad-hoc dictionary conversions in UI panels or backend repos.
  - **Connection & Transaction Management**: Centralize DB connections, pragmas, commits, and rollbacks in a context manager (`_connect()`). Do not repeat manual `conn.commit()` / `conn.rollback()` in every query method.
  - **Symmetric Logic**: Never copy-paste near-identical blocks for White and Black (e.g., phase accuracies, tactics extraction). Iterate over `("white", "black")` or extract unified helper functions.
  - **Separation of Storage and Domain**: Repositories persist data; domain calculations (tactics, classification, termination detection) must be computed in backend domain services before passing to storage. Avoid circular dependencies or function-level lazy imports to mask design duplication.

---

## 6. Commands
- **Install Dependencies**: `pip install -r requirements-dev.txt` (or `uv pip install -r requirements-dev.txt`)
- **Start Development**: `python main.py`
- **Lint**: `ruff check .` (auto-fix: `ruff check --fix .`)
- **Format**: optional, not a gate. `ruff format .` only when a file is being substantially rewritten; never block or report work on `ruff format --check`.
- **Run All Tests**: `pytest tests/` (Headless Linux: `QT_QPA_PLATFORM=offscreen pytest tests/`)
- **Run Single Test**: `pytest tests/backend/test_analyzer.py`
- **Measure Coverage**: `pytest tests/ --cov=src --cov-branch --cov-report=term-missing` (branch coverage, GUI excluded, 85% floor)
- **Production Build**: `pyinstaller build.spec`

---

## 7. Testing & Verification
- All pull requests must maintain a 100% pass rate: `pytest tests/` (990+ unit and GUI tests). The full suite must stay under 20 seconds, and the coverage gate must pass.
- Backend logic changes require headless unit tests in `tests/backend/`.
- GUI widget changes require tests using `pytest-qt` in `tests/gui/`.
- Linting must report 0 errors: `ruff check .`
- Formatting is **not** verified. Do not run `ruff format --check`, do not reformat unrelated files, and never treat formatting drift as a failure.

### Coverage Requirements
- **Coverage Is a Floor, Not a Target**: Backend and utility code must keep branch coverage at or above the 85% `fail_under` threshold in `pyproject.toml`. GUI modules are excluded deliberately because they are expensive to instantiate and would make the metric noisy.
- **Test New Behavior, Not Line Counts**: New logic must ship with tests that assert its meaningful branches, calculations, state mutations, and failure fallbacks. Do not chase 100% or add tests for generated code, trivial delegation, or pure language behavior.
- **Fix Regressions, Don't Lower the Floor**: If coverage drops, add or strengthen a meaningful test. Do not lower `fail_under` or exclude modules to make the gate pass.

### Meaningful Testing Guidelines (No Bloat, No Tautologies)
- **Zero Language Tautologies**: Never write tests that merely verify Python's standard library or language behavior (e.g. asserting that a `@dataclass` assigns fields: `m = Model(x=1); assert m.x == 1`). Tests must assert domain logic, state mutations, calculations, or defensive fallbacks.
- **Black-Box Over Private Implementation**: Test through public contracts and interfaces. Do not write redundant unit tests for private helper functions whose outputs are already asserted by the public API.
- **Eliminate Cross-Module Duplication**: If domain behavior is exhaustively tested in a dedicated test file (e.g. `test_move_classifier.py` for classifications and win probabilities), do not copy-paste duplicate tests into other test suites (`test_analyzer.py`).
- **No Test Bloat**: Extend or parameterize an existing test instead of adding a near-duplicate. Delete tests that only smoke-check construction, duplicate another module's coverage, or do not protect app-breaking behavior.
- **Heavy GUI Test Conservation**: Instantiating full-app windows (`MainWindow`) is expensive (~2-3s per instance). Never boot multiple full `MainWindow` instances to test simple defensive or config parsing branches. Consolidate save/restore tests into a single lifecycle test, and test defensive methods directly on the instance.
- **Parameterize Over Duplication**: Use `@pytest.mark.parametrize` for multiple input variants, malformed strings, or platform formats rather than copy-pasting 4-5 near-identical test functions.
- **Consolidated Metadata Assertions**: Avoid re-reading or re-parsing the same fixture across multiple tests to assert one field at a time. Assert the full record in a single coherent test.
- **Guard Critical Invariants**: Tests must strictly protect core invariants: Stockfish UCI lifecycle, 10% accuracy floor, White-perspective scores, thermal safety defaults, deterministic MD5 hashing, and Chess960 castling.

### Speed & Determinism Rules
- **No Timeout-Based Tests**: Never make a test pass by letting a timer expire, and never use `time.sleep()`, `QTest.qWait()`, or real network/request timeouts to wait for work to finish. Run workers synchronously (`worker.run()`), observe emitted signals directly, or inject fake clocks so tests are deterministic and instant.
- **Wait on Conditions, Not Clocks**: `qtbot.waitUntil`/`waitSignal` are acceptable only for unavoidable Qt layout or debounce events, always with a tight timeout and a condition that would be true immediately in a correct implementation.
- **Keep Tests Fast**: The whole suite must finish in under 20 seconds. Any single test approaching ~1 second needs justification; find outliers with `pytest --durations=10`. Reuse fixtures/fakes and test logic directly instead of driving the full UI.
- **No Network in Tests**: Mock every HTTP client and LLM call. Tests must pass offline, and a local `.env` must never turn a unit test into a live request.
- **Never Write to Real Persistence**: Tests must never write to the user's real database, config, secrets, logs, or backup files. Use pytest's `tmp_path`/`tmp_path_factory`; the shared `tests/conftest.py` already redirects `get_user_data_dir()` and disables the OS keychain. Never bypass those patches or build a store without an explicit temporary path.
- **Cross-Platform by Default**: Every test must pass on Windows, macOS, and Linux. Build paths with `pathlib.Path`, never hardcoded separators or drive letters. Do not assert POSIX-only behavior (permission bits, exec bits, `chmod`, shell scripts) on Windows — guard it with `sys.platform`/`os.name` or mock the platform branch. Patch platform-specific APIs instead of depending on the host OS, and keep assertions OS-agnostic wherever the behavior is shared.

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
6. **Issue-First**: Every PR must close or target an existing issue. If no issue exists for the requested feature or fix, open one and get maintainer verification before implementing. Unlinked PRs are not approved.

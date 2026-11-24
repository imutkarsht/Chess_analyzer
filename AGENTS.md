# Chess Analyzer Pro — Engineering Rules

Chess Analyzer Pro is a local-first PyQt6 desktop chess analyzer built on
Stockfish, SQLite, and python-chess. This file holds the rules an agent or
automation must follow. System map: [ARCHITECTURE.md](ARCHITECTURE.md). Code
patterns: [docs/conventions.md](docs/conventions.md). Step-by-step changes:
[docs/recipes.md](docs/recipes.md).

## Commands

```bash
pip install -r requirements-dev.txt              # dependencies
python main.py                                   # run
ruff check .                                     # lint
pytest tests/                                    # all tests
QT_QPA_PLATFORM=offscreen pytest tests/          # headless Linux
pytest tests/backend/test_analyzer.py            # one file
pytest tests/ --cov=src --cov-branch --cov-report=term-missing  # coverage
pyinstaller build.spec                           # production build
```

## Boundaries

**Always**

- Run `ruff check .` and `pytest tests/` before finishing.
- Add tests for new behaviour and meaningful branches.
- Keep diffs focused; do not mix refactors with fixes.
- Use `pathlib` for paths and `logger` for diagnostics.

**Ask first**

- Adding a dependency.
- Changing the database schema or a migration.
- Changing the coverage floor or coverage exclusions.
- Changing the build or release configuration.
- Any destructive data operation.

**Never**

- Commit secrets, credentials, or private tokens.
- Edit generated artifacts.
- Add `# noqa` without permission.
- Run destructive Git commands or force-push.
- Import PyQt6 or `src.gui` in `src/backend`, `src/utils`, or `src/config`.
- Construct a raw Qt control where a shared component exists.
- Trust PGN, FEN, or API input without validation at the backend boundary.
- Use `print()` for application logging.

## Invariants

- Offline-first: analysis, PGN import, opening books, and history work with no
  network.
- No blocking work on the UI thread. Engine, network, and LLM work runs in
  `QThread` workers and is cleaned up on close.
- Scores are White-perspective. Flip only once, in
  `Analyzer._process_analysis_results()`.
- Stop the engine in `finally`; restart it for every fresh analysis.
- Thermal defaults are `multi_pv=2`, `threads=1`, and `hash=128MB`. Keep
  threads and hash out of `DEFAULT_CONFIG` so module fallbacks apply.
- `game_id = md5(pgn_content)`. Never use random UUIDs.
- Per-move accuracy never drops below 10.0%.
- Chess960: set `UCI_Chess960` and build boards with
  `chess.Board(fen, chess960=True)`.
- AI explanations come from deterministic facts, are validated against those
  facts, and have an offline fallback.
- The project is GPL-3.0-only. New Python files start with the SPDX header, and
  dependencies must be licence-compatible.

## Guardrail tests

`tests/architecture/test_boundaries.py` keeps pure packages Qt-free;
`tests/architecture/test_theme_guardrails.py` and `test_theme_tokens.py` protect
theming; `tests/gui/test_button.py` and `test_input.py` protect shared controls
and worker placement.

## Code rules

- Use Python 3.10+ typing: `X | None`, `list[T]`, `dict[K, V]`.
- Use `from src.utils.logger import logger`; never `print()`.
- Use `src.gui.components` for every control. Do not use raw Qt widgets or
  `create_button` / `create_icon_button` factories.
- Add settings through `src/config/settings_schema.py` and read them through
  typed `ConfigManager` properties.
- Static styling belongs in `theme_template.qss` through object names and
  dynamic properties. No declaration-only stylesheets, universal `QWidget`
  rules, descendant `QWidget` rules, or hardcoded hex.
- Keep one source of truth: `GAME_COLUMNS` for SQL, model `to_dict()` /
  `from_dict()` for serialisation, and one canonical helper per concern.
- Iterate over `("white", "black")` instead of copying symmetric branches.
- Comments explain non-obvious domain decisions, not syntax.

## Testing

- Backend tests live in `tests/backend/`; GUI tests use `pytest-qt` in
  `tests/gui/`; architecture guards live in `tests/architecture/`.
- No `time.sleep()`, `QTest.qWait()`, or real network calls. Run workers
  synchronously and observe signals.
- Use `tmp_path` for persistence. Never touch real user data or credentials.
- Tests must pass on Windows, macOS, and Linux. Use `pathlib`, and guard
  POSIX-only assertions.
- Parameterise instead of duplicating tests. Do not add tautologies or boot
  extra `MainWindow` instances.
- Keep branch coverage at or above 80%; GUI modules are excluded. Never lower
  the floor or exclude modules to pass.
- Formatting is not a gate. Do not run `ruff format --check`, and do not
  reformat unrelated files.
- Guard the critical invariants: UCI lifecycle, accuracy floor,
  White-perspective scores, thermal defaults, deterministic game IDs, and
  Chess960 castling.

## Workflow

1. Open or reference an issue before changing behaviour.
2. Inspect the existing code and boundaries.
3. Plan complex refactors before editing.
4. Implement in focused changes.
5. Run lint and tests.
6. Write a Conventional Commit (`feat:`, `fix:`, `docs:`, `refactor:`,
   `test:`, `chore:`).
7. Ask before changing the schema, a migration, or a layer boundary. Do not
   guess at business rules; check the tests and the domain modules.

Docs: [system map](ARCHITECTURE.md) ·
[topic guides](docs/architecture/) ·
[conventions](docs/conventions.md) ·
[recipes](docs/recipes.md) ·
[onboarding](docs/onboarding_doc.md) ·
[contribution process](CONTRIBUTING.md).

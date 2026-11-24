# Onboarding

This guide takes you from a fresh clone to a first meaningful change. For the
system map, read [ARCHITECTURE.md](../ARCHITECTURE.md); for rules and commands,
read [AGENTS.md](../AGENTS.md).

---

## 1. What you need

- Python 3.10 or newer.
- Stockfish, or use the in-app Setup Wizard to download it.
- Git.

## 2. Set up

```bash
git clone https://github.com/imutkarsht/Chess_analyzer.git
cd Chess_analyzer
```

Create and activate a virtual environment with your preferred tool, then
install dependencies and start the app:

```bash
pip install -r requirements-dev.txt
python main.py
```

On first run, the Setup Wizard configures the engine, theme, and optional
integrations.

## 3. Learn the shape

Read [ARCHITECTURE.md](../ARCHITECTURE.md). The short version:

- `src/backend/` is pure Python domain logic.
- `src/workers/` owns the Qt worker threads.
- `src/gui/` renders state and dispatches actions.
- `src/config/` defines settings; `src/utils/` holds shared helpers.

Pick the topic guide that matches your change:

| Area | Guide |
| --- | --- |
| Analysis, import, batch, coaching flows | [architecture/runtime-flows.md](architecture/runtime-flows.md) |
| Tactics and AI grounding | [architecture/tactics.md](architecture/tactics.md) |
| Database, history, termination | [architecture/storage.md](architecture/storage.md) |
| Components and theming | [architecture/gui.md](architecture/gui.md) |

## 4. Make a first change

A small, complete change is to adjust a move-classification threshold.

1. Open `src/backend/analysis/move_classifier.py`.
2. Find the threshold for the category you want to change.
3. Adjust it without changing the White-perspective score contract.
4. Update the classifier tests in `tests/backend/test_move_classifier.py`.
5. Run the focused tests:

```bash
pytest tests/backend/test_move_classifier.py
```

6. Run lint and the full suite before finishing:

```bash
ruff check .
pytest tests/
```

For other changes, use [recipes.md](recipes.md).

## 5. Verify

```bash
# Full suite
pytest tests/

# Headless Linux
QT_QPA_PLATFORM=offscreen pytest tests/

# Branch coverage
pytest tests/ --cov=src --cov-branch --cov-report=term-missing
```

The coverage floor is 80% branch coverage; GUI modules are excluded. Do not
lower the floor or exclude modules to pass.

## 6. Troubleshooting

- **Engine not found** — point Settings -> Chess Engine at the Stockfish
  executable, not the folder.
- **API key error** — activate a valid LLM profile in Settings -> AI Coach.
- **Logs** — the application log lives in the OS user-data directory.

## 7. Build from source

```bash
pip install pyinstaller
pyinstaller build.spec
```

Platform installer scripts live in `installers/`. `build.spec` includes the
assets and hidden imports needed by PyQt6 and python-chess.

## 8. Next steps

- Read [conventions.md](conventions.md) for code patterns and shared helpers.
- Read [recipes.md](recipes.md) before adding a page, setting, motif, or card.
- Read [CONTRIBUTING.md](../CONTRIBUTING.md) before opening a pull request.
- Read [AGENTS.md](../AGENTS.md) for the hard invariants.

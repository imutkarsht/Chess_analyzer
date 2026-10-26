# Contributing to Chess Analyzer Pro

First off, thank you for considering contributing! Every bug report, feature idea, and pull request makes the project better.

---

## 🤝 How Can I Contribute?

### Reporting Bugs

- **Search existing issues first** to avoid duplicates.
- **Use a clear and descriptive title**.
- **Describe the exact steps to reproduce** the problem, including your OS, Python version, and Stockfish version.
- Attach the application log if relevant (`~/Library/Application Support/ChessAnalyzerPro/` on macOS, `%APPDATA%\ChessAnalyzerPro\` on Windows).

### Suggesting Enhancements

- **Use a clear and descriptive title**.
- **Provide a step-by-step description** of the suggested enhancement.
- **Explain why this enhancement would be useful** to most users.

### Issue-First Contributions

Every contribution must start with an issue. This keeps work aligned with the
project's direction and avoids wasted effort on features that won't be merged.

- **Every PR must close or target an issue.** Link the issue in the PR
  description (for example, `Closes #123` or `Refs #123`).
- **Raise an issue before writing code.** If you think a feature is missing or a
  bug is unfixed, open an issue first and let a maintainer verify and scope it
  before you start working on it.
- **PRs without a linked issue will not be approved.** Unlinked PRs are closed
  without review, even if the code is good.

### Pull Requests

1. Pick an open issue and comment on it so maintainers know you're working on it
   (and to avoid duplicate effort).
2. Fork the repository and create your branch from `master`.
3. Follow the branch naming conventions below.
4. If you've added code that should be tested, add tests — new behavior needs
   meaningful tests (see [Test quality expectations](#8-test-quality-expectations)).
5. Ensure `ruff check .` and the full test suite pass.
6. Update documentation if you change any functionality.
7. Open the pull request against `master` and reference the issue with
   `Closes #<number>` so the PR is linked and auto-closed on merge.

---

## 💻 Development Setup

### 1. Clone the repo

```bash
git clone https://github.com/imutkarsht/Chess_analyzer.git
cd Chess_analyzer
```

### 2. Create and activate a virtual environment

```bash
# Using uv (recommended — faster)
pip install uv
uv venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows

# Or with standard venv
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
# Using uv (recommended)
uv pip install -r requirements-dev.txt

# Or with standard pip
pip install -r requirements-dev.txt
```

### 4. Run the app

```bash
python main.py
```

### 5. Run linters & code formatting

```bash
# Check code style & logic with Ruff
ruff check .

# Automatically fix lint issues
ruff check --fix .

# Format code
ruff format .
```

### 6. Run the test suite

```bash
# All tests (headless Qt)
pytest tests/ -v

# On Linux without a display
QT_QPA_PLATFORM=offscreen pytest tests/ -v

# Windows (PowerShell)
pytest tests/ -v
```

> The full suite should finish in under 20 seconds. If it gets slower, run
> `pytest tests/ --durations=10` and fix the outliers instead of accepting them.

### 7. Check coverage

Backend and utility modules are measured with branch coverage; GUI modules are
excluded on purpose (they are exercised through a handful of lifecycle tests,
which would make the number noisy). The build fails if coverage drops below the
`fail_under` threshold in `pyproject.toml`.

```bash
pytest tests/ --cov=src --cov-branch --cov-report=term-missing
```

### 8. Test quality expectations

- **Cover the behavior, not the line count.** New logic needs tests for its
  meaningful branches, calculations, and failure fallbacks. Do not add tests
  just to raise the percentage, and do not lower `fail_under` to make the gate
  pass.
- **No test bloat.** Extend or parameterize an existing test instead of adding a
  near-duplicate. Delete tests that only smoke-check construction, duplicate
  another module's coverage, or do not protect app-breaking behavior.
- **No lengthy tests.** Keep the whole suite under 20 seconds and avoid tests
  that approach one second without a clear reason. Reuse fixtures and test
  logic directly instead of booting the full `MainWindow`.
- **No timeout-based tests.** Never make a test pass by letting a timer expire,
  and never use `time.sleep()`, `QTest.qWait()`, or real request timeouts to wait
  for work to finish. Run workers synchronously (`worker.run()`), observe emitted
  signals, or inject fake clocks so tests are deterministic and instant.
  `qtbot.waitUntil`/`waitSignal` are only for unavoidable Qt layout or debounce
  events, with a tight timeout and an immediately-true condition.
- **Stay offline.** Mock every HTTP client and LLM call. A local `.env` must
  never turn a unit test into a live request.
- **Never write to real persistence.** Tests must not touch the user's real
  database, config, secrets, logs, or backups. Use pytest's
  `tmp_path`/`tmp_path_factory` and pass explicit temporary paths to caches,
  repositories, and `SecretStore`; the shared `conftest.py` already redirects
  `get_user_data_dir()` and disables the OS keychain, so never bypass it.

---

## 🌿 Branch Naming

| Type             | Pattern                     | Example                     |
| ---------------- | --------------------------- | --------------------------- |
| New feature      | `feat/<short-description>`  | `feat/share-analysis-card`  |
| Bug fix          | `fix/<short-description>`   | `fix/eval-bar-teardown`     |
| Documentation    | `docs/<short-description>`  | `docs/update-readme-badges` |
| Refactor / chore | `chore/<short-description>` | `chore/split-requirements`  |
| Release          | `release/v<version>`        | `release/v2.4.0`            |

---

## 📝 Code Style

- Follow **PEP 8** for Python formatting.
- All public functions must have **type hints** using modern Python 3.10+ syntax (`X | None`, `list[T]`, `dict[K, V]`).
- Use `from src.utils.logger import logger` — **never** use `print()` for internal messages.
- Never hardcode colors in widget files — use `Styles.COLOR_*` constants from `src/gui/styles.py`.
- Write meaningful commit messages (we loosely follow [Conventional Commits](https://www.conventionalcommits.org/)):
  - `feat:` for new features
  - `fix:` for bug fixes
  - `docs:` for documentation
  - `chore:` for maintenance / CI / tooling
  - `test:` for test additions or changes

---

## 🏗️ Architecture Notes

- **No Qt in backend**: `src/backend/` must have zero PyQt6 imports.
- **Long-running tasks** must run in `QThread` subclasses, communicating via `pyqtSignal`.
- **ConfigManager** is a singleton — do not instantiate in tight loops.
- **Score convention**: evaluation scores are stored relative to White (positive = White better).

See the full architecture and agent guidelines in [`AGENTS.md`](AGENTS.md).

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

### Pull Requests

1. Fork the repository and create your branch from `master`.
2. Follow the branch naming conventions below.
3. If you've added code that should be tested, add tests.
4. Ensure the full test suite passes.
5. Update documentation if you change any functionality.
6. Open the pull request against `master`.

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
# Production + dev dependencies
pip install -r requirements.txt -r requirements-dev.txt
```

### 4. Run the app

```bash
python main.py
```

### 5. Run the test suite

```bash
# All tests (headless Qt)
PYTHONPATH=. pytest tests/ -v

# On Linux without a display
QT_QPA_PLATFORM=offscreen PYTHONPATH=. pytest tests/ -v

# Windows (PowerShell)
$env:PYTHONPATH="."; pytest tests/ -v
```

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
- All public functions must have **type hints**.
- Use `Optional[X]` for nullable parameters (not `X | None` in public APIs).
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

See the full architecture reference in [`.agent/AGENTS.md`](.agent/AGENTS.md).

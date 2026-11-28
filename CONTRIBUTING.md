# Contributing to Chess Analyzer Pro

Thank you for helping improve Chess Analyzer Pro. Bug reports, feature ideas,
and pull requests are welcome.

## How to contribute

### Report a bug

- Search existing issues first.
- Use a clear title.
- Describe the exact steps to reproduce the problem, including your operating
  system, Python version, and Stockfish version.
- Attach the application log if it helps. Logs live in the OS user-data
  directory.

### Suggest an enhancement

- Search existing issues first.
- Describe the proposed behaviour and why it would help most users.
- Keep the scope concrete enough to become an issue.

### Issue-first contributions

Every contribution starts with an issue. This keeps work aligned with the
project direction and avoids wasted effort.

- Every pull request must close or reference an issue, for example `Closes #123`
  or `Refs #123`.
- Open an issue before writing code. A maintainer will verify and scope it.
- Pull requests without a linked issue are not approved.

### Pull requests

1. Pick an open issue and comment that you are working on it.
2. Fork the repository and branch from `master`.
3. Follow the branch naming conventions below.
4. Add meaningful tests for new behaviour.
5. Run `ruff check .`, `pytest tests/`, and the architecture guardrails below.
6. Update the relevant documentation.
7. Open the pull request against `master` and reference the issue with
   `Closes #<number>`.

## Licensing of contributions

Chess Analyzer Pro is licensed under **GPL-3.0-only**, including the section 7
additional terms in [`LICENSE`](LICENSE).

- By opening a pull request you agree that your contribution is licensed under
  the same terms. There is no CLA and no copyright assignment.
- Only submit code you have the right to license this way. Do not paste code
  from projects with an incompatible licence, such as AGPL-3.0-only code or code
  with no licence. If you adapted an algorithm or snippet, say where it came
  from in the pull request.
- New dependencies must be GPL-3.0-compatible. Raise the dependency in the issue
  before adding it.
- New Python files start with `# SPDX-License-Identifier: GPL-3.0-only`. Do not
  add headers to existing files.

## Development setup

### 1. Clone the repository

```bash
git clone https://github.com/imutkarsht/Chess_analyzer.git
cd Chess_analyzer
```

### 2. Create and activate a virtual environment

Use your preferred tool, then install dependencies:

```bash
pip install -r requirements-dev.txt
# or: uv pip install -r requirements-dev.txt
```

### 3. Run the app

```bash
python main.py
```

### 4. Lint

```bash
ruff check .
ruff check --fix .
```

Formatting is optional and is not a gate. Do not reformat unrelated files.

### 5. Test

```bash
pytest tests/ -v
QT_QPA_PLATFORM=offscreen pytest tests/ -v    # headless Linux
```

If the suite gets slower, run `pytest tests/ --durations=10` and fix the
outliers.

### 6. Check coverage

Backend and utility modules use branch coverage. GUI modules are excluded
because they are exercised through a smaller number of lifecycle tests.

```bash
pytest tests/ --cov=src --cov-branch --cov-report=term-missing
```

The build fails below the `fail_under` threshold in `pyproject.toml`.

### 7. Check architecture guardrails

Run the fast guardrail suites before opening a pull request:

```bash
ruff check .
pytest tests/architecture -q
pytest tests/gui/test_button.py tests/gui/test_input.py tests/gui/test_component_imports.py -q
python scripts/check_changed_hygiene.py --base origin/master
```

`check_changed_hygiene.py` checks only lines added relative to the base. It
requires the SPDX header on new `src/` and `tests/` Python files, a reason on
new `# noqa` comments, a code on new `# type: ignore[...]` comments, and rejects
new `print()`, `os.path`, raw font icon names, and raw Qt controls outside the
documented allowlists.

## Required CI checks

Branch protection on `master`, `main`, and `release/**` requires:

- `Lint / Ruff Linter`
- `Code Hygiene / architecture`
- `Code Hygiene / coverage`
- every `Test Suite` matrix leg

The `Code Hygiene` workflow runs on Ubuntu only. Maintainers enable these
checks in GitHub branch protection or repository rulesets after the workflow
has run at least once.

## Test quality expectations

- Cover behaviour, calculations, state changes, and failure fallbacks, not line
  counts.
- Do not lower `fail_under` below 80 or exclude modules to make the gate pass.
- Extend or parameterise an existing test instead of adding a near-duplicate.
  Delete tests that only smoke-check construction or duplicate another module's
  coverage.
- Avoid tests that approach one second without a clear reason. Reuse fixtures
  and test logic directly instead of booting a full `MainWindow`.
- Never use `time.sleep()`, `QTest.qWait()`, or real request timeouts to wait for
  work. Run workers synchronously, observe signals, or inject fake clocks.
  `qtbot.waitUntil` and `qtbot.waitSignal` are only for unavoidable Qt layout or
  debounce events, with a tight timeout and an immediately-true condition.
- Mock every HTTP client and LLM call. Tests must pass offline, and local
  credentials must never turn a unit test into a live request.
- Use `tmp_path` and `tmp_path_factory`. Never touch real user data,
  credentials, or backups. The shared `conftest.py` redirects user-data paths
  and disables the OS keychain; do not bypass those patches.
- Tests must pass on Windows, macOS, and Linux. Use `pathlib.Path`, and guard
  POSIX-only checks with `sys.platform` or `os.name`.

## Branch naming

| Type | Pattern | Example |
| --- | --- | --- |
| New feature | `feat/<short-description>` | `feat/share-analysis-card` |
| Bug fix | `fix/<short-description>` | `fix/eval-bar-teardown` |
| Documentation | `docs/<short-description>` | `docs/update-readme-badges` |
| Refactor or chore | `chore/<short-description>` | `chore/split-requirements` |
| Release | `release/v<version>` | `release/v2.6.1` |

## Code style

- Follow PEP 8.
- Use Python 3.10+ type hints: `X | None`, `list[T]`, `dict[K, V]`.
- Use `from src.utils.logger import logger`; never use `print()` for internal
  messages.
- Never hardcode colours in widget files. Use `Styles.COLOR_*`.
- Write meaningful commit messages, loosely following Conventional Commits:
  `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.

For components, settings, theming, shared helpers, and naming, see
[docs/conventions.md](docs/conventions.md).

## Architecture notes

The system map is [ARCHITECTURE.md](ARCHITECTURE.md). Runtime flows, tactics,
storage, and GUI details live under [docs/architecture/](docs/architecture/).

The rules contributors must not break are in [AGENTS.md](AGENTS.md). In
particular:

- `src/backend/`, `src/utils/`, and `src/config/` are Qt-free.
- Long-running work runs in `QThread` workers and is cleaned up on close.
- Repositories persist; domain services compute.
- Evaluation scores are White-perspective.
- The project is GPL-3.0-only.

## Documentation expectations

| Change | Update |
| --- | --- |
| System shape or layer edges | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Runtime flow | [docs/architecture/](docs/architecture/) |
| Code pattern or shared helper | [docs/conventions.md](docs/conventions.md) |
| Extension recipe | [docs/recipes.md](docs/recipes.md) |
| Hard rule or command | [AGENTS.md](AGENTS.md) |
| Contribution process | This file |
| User-facing feature | [docs/How_to_use.md](docs/How_to_use.md) |

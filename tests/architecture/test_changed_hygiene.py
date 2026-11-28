# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the changed-line hygiene script."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import check_changed_hygiene as hygiene

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_changed_hygiene.py"
GIT = shutil.which("git")
HEADER = f"{hygiene.SPDX_HEADER}\n"

requires_git = pytest.mark.skipif(GIT is None, reason="git is required")


def _run_git(repo: Path, *args: str) -> None:
    assert GIT is not None
    result = subprocess.run(
        [GIT, "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init")
    _run_git(repo, "config", "user.email", "hygiene@example.com")
    _run_git(repo, "config", "user.name", "Hygiene Tests")
    _run_git(repo, "config", "core.autocrlf", "false")
    _run_git(repo, "config", "commit.gpgsign", "false")
    (repo / "base.txt").write_text("base\n", encoding="utf-8", newline="\n")
    _commit(repo, "base")
    return repo


def _write(repo: Path, relative: str, content: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _commit(repo: Path, message: str) -> None:
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-m", message)


def _run_script(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--base", "HEAD~1"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_parse_added_lines_handles_multiple_hunks() -> None:
    diff = (
        "diff --git a/src/x.py b/src/x.py\n"
        "--- a/src/x.py\n"
        "+++ b/src/x.py\n"
        "@@ -1,2 +1,3 @@\n"
        " line\n"
        "+added\n"
        " line\n"
        "@@ -10,0 +12,2 @@\n"
        "+one\n"
        "+two\n"
        "@@ -20,1 +20,0 @@\n"
        "-gone\n"
        "\\ No newline at end of file\n"
    )

    assert hygiene._parse_added_lines(diff) == {2, 12, 13}


def test_noqa_requires_a_code_and_reason() -> None:
    text = (
        f"{hygiene.SPDX_HEADER}\n"
        "# noqa: F401 - unused import\n"
        "value = 1  # noqa: E501\n"
        'DOC = "# noqa: F401"\n'
        "other = 2  # noqa\n"
    )

    violations = hygiene.check_added_lines("tests/example.py", text, {1, 2, 3, 4, 5})

    assert [line for _, line, _ in violations] == [3, 5]


def test_type_ignore_requires_a_code() -> None:
    text = (
        f"{hygiene.SPDX_HEADER}\n"
        "value = 1  # type: ignore[assignment]\n"
        "other = 2  # type: ignore\n"
        'DOC = "# type: ignore"\n'
    )

    violations = hygiene.check_added_lines("src/example.py", text, {1, 2, 3, 4})

    assert [line for _, line, _ in violations] == [3]


def test_os_path_only_flags_added_lines() -> None:
    text = (
        "import os\n"
        "first = os.path.join('a', 'b')\n"
        "second = os.path.join('c', 'd')\n"
    )

    violations = hygiene.check_added_lines("src/app.py", text, {3})

    assert violations == [
        ("src/app.py", 3, "use pathlib instead of os.path")
    ]


def test_print_only_flags_added_lines() -> None:
    text = 'print("legacy")\nprint("new")\n'

    violations = hygiene.check_added_lines("src/app.py", text, {2})

    assert violations == [("src/app.py", 2, "use logger instead of print()")]


@pytest.mark.parametrize(
    ("relative", "source", "blocked"),
    [
        ("src/gui/views/foo.py", "widget = QPushButton()\n", True),
        (
            "src/gui/components/controls/button.py",
            "widget = QPushButton()\n",
            False,
        ),
        ("src/gui/analysis/moves/cell.py", "widget = QToolButton()\n", False),
        ("src/gui/views/foo.py", "widget = QComboBox()\n", True),
        ("src/gui/components/controls/foo.py", "widget = QComboBox()\n", False),
        ("src/gui/views/foo.py", "label = QLabel()\n", True),
        ("src/gui/components/controls/foo.py", "label = QLabel()\n", False),
        ("src/gui/board/mini_board.py", "label = QLabel()\n", False),
        ("src/gui/analysis/variation/graph.py", "field = QLineEdit()\n", False),
        (
            "src/gui/analysis/variation/graph.py",
            "widget = QComboBox()\n",
            True,
        ),
    ],
)
def test_raw_controls_follow_the_shared_allowlists(
    relative: str, source: str, blocked: bool
) -> None:
    violations = hygiene.check_added_lines(relative, source, {1})

    assert bool(violations) is blocked


def test_raw_font_names_respect_the_icon_layer_and_allowlist() -> None:
    source = 'icon = "fa5s.trash"\n'

    assert hygiene.check_added_lines("src/gui/views/foo.py", source, {1})
    assert not hygiene.check_added_lines("src/gui/icons/spec.py", source, {1})
    assert not hygiene.check_added_lines(
        "src/gui/components/layout/welcome_panel.py", source, {1}
    )


@pytest.mark.parametrize(
    ("relative", "text", "violates"),
    [
        ("src/new.py", "value = 1\n", True),
        ("src/new.py", f"{HEADER}value = 1\n", False),
        ("tests/new.py", "value = 1\n", True),
        ("tests/new.py", f"{HEADER}value = 1\n", False),
        ("scripts/new.py", "value = 1\n", False),
    ],
)
def test_spdx_is_required_for_new_src_and_test_files(
    relative: str, text: str, violates: bool
) -> None:
    message = hygiene.spdx_violation(relative, text)

    assert bool(message) is violates


@requires_git
def test_clean_new_files_pass(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _write(repo, "src/pkg/module.py", f"{HEADER}value = 1\n")
    _write(repo, "tests/test_module.py", f"{HEADER}value = 1\n")
    _commit(repo, "add clean modules")

    result = _run_script(repo)

    assert result.returncode == 0, result.stderr
    assert "clean" in result.stdout


@requires_git
@pytest.mark.parametrize(
    ("relative", "content", "needle"),
    [
        ("src/new.py", "value = 1\n", "SPDX"),
        ("src/new.py", f'{HEADER}print("debug")\n', "print()"),
        ("src/new.py", f"{HEADER}value = 1  # noqa: F401\n", "# noqa"),
        ("src/new.py", f"{HEADER}value = 1  # type: ignore\n", "type: ignore"),
        (
            "src/new.py",
            f"{HEADER}value = os.path.join('a', 'b')\n",
            "pathlib",
        ),
        ("src/new.py", f"{HEADER}widget = QComboBox()\n", "QComboBox"),
        ("src/new.py", f'{HEADER}icon = "fa5s.trash"\n', "fa5s.trash"),
    ],
)
def test_added_lines_reject_hygiene_regressions(
    tmp_path: Path, relative: str, content: str, needle: str
) -> None:
    repo = _init_repo(tmp_path)
    _write(repo, relative, content)
    _commit(repo, "regression")

    result = _run_script(repo)

    assert result.returncode == 1, result.stderr
    assert needle in result.stderr


@requires_git
def test_unchanged_legacy_violations_are_ignored(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _write(repo, "src/legacy.py", 'print("old")\n')
    _commit(repo, "legacy file")
    _write(repo, "src/legacy.py", 'print("old")\nvalue = 2\n')
    _commit(repo, "change legacy file")

    result = _run_script(repo)

    assert result.returncode == 0, result.stderr


@requires_git
def test_allowlisted_raw_editor_passes(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _write(repo, "src/gui/analysis/variation/graph.py", "value = 1\n")
    _commit(repo, "graph base")
    _write(
        repo,
        "src/gui/analysis/variation/graph.py",
        "value = 1\nfield = QLineEdit()\n",
    )
    _commit(repo, "add rename overlay editor")

    result = _run_script(repo)

    assert result.returncode == 0, result.stderr

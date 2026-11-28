#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Reject hygiene regressions on lines changed relative to a base commit.

Whole-repository guardrail tests catch new violations everywhere. This script
complements them by checking only added lines, so legacy files can keep their
documented exceptions while new code follows the current rules.

Checks:
- New ``src/`` and ``tests/`` Python files start with the SPDX header.
- Added ``# noqa`` comments include a code and a reason.
- Added ``print()`` calls in ``src/`` fail.
- Added raw Font Awesome names outside the icon layer/allowlist fail.
- Added raw Qt control constructors outside the shared-component/allowlist
  rules fail.
"""

from __future__ import annotations

import argparse
import ast
import io
import os
import re
import shutil
import subprocess
import sys
import tokenize
from pathlib import Path

if __package__:
    from scripts.hygiene_rules import (
        BUTTON_COMPONENT,
        RAW_BUTTON_ALLOWLIST,
        RAW_CONTROL_CLASSES,
        RAW_FONT_ALLOWLIST,
        RAW_FONT_ICON,
        RAW_FORM_CONTROLS,
        RAW_INPUT_ALLOWLIST,
        RAW_INPUT_CLASSES,
        RAW_PUSH_TOOL_CLASSES,
        SPDX_HEADER,
    )
else:
    from hygiene_rules import (
        BUTTON_COMPONENT,
        RAW_BUTTON_ALLOWLIST,
        RAW_CONTROL_CLASSES,
        RAW_FONT_ALLOWLIST,
        RAW_FONT_ICON,
        RAW_FORM_CONTROLS,
        RAW_INPUT_ALLOWLIST,
        RAW_INPUT_CLASSES,
        RAW_PUSH_TOOL_CLASSES,
        SPDX_HEADER,
    )

NOQA_RE = re.compile(
    r"#\s*noqa\s*:\s*[A-Z][A-Z0-9]*(?:\s*,\s*[A-Z][A-Z0-9]*)*\s+-\s+\S"
)
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
ZERO_SHA = re.compile(r"^0+$")
SPDX_PATHS = ("src/", "tests/")

Violation = tuple[str, int, str]


class HygieneError(RuntimeError):
    """Raised when the changed-file check cannot run."""


def _git_executable() -> str:
    executable = shutil.which("git")
    if executable is None:
        raise HygieneError("git executable not found")
    return executable


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_git_executable(), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _git_output(args: list[str]) -> str:
    result = _run_git(args)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise HygieneError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def repo_root() -> Path:
    """Return the root of the current Git worktree."""
    return Path(_git_output(["rev-parse", "--show-toplevel"]).strip())


def _resolve_commit(ref: str) -> str | None:
    result = _run_git(["rev-parse", "--verify", f"{ref}^{{commit}}"])
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def resolve_base(explicit: str | None) -> str | None:
    """Resolve the base commit, preferring an explicit value or CI event SHA."""
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)

    event_sha = os.environ.get("HYGIENE_BASE_SHA") or os.environ.get(
        "GITHUB_EVENT_BEFORE"
    )
    if event_sha and not ZERO_SHA.fullmatch(event_sha):
        candidates.append(event_sha)

    base_ref = os.environ.get("GITHUB_BASE_REF")
    if base_ref:
        candidates.append(f"origin/{base_ref}")

    candidates.extend(
        ["origin/master", "master", "origin/main", "main", "HEAD~1"]
    )

    for candidate in candidates:
        commit = _resolve_commit(candidate)
        if commit is None:
            continue
        if commit == "HEAD" or ZERO_SHA.fullmatch(commit):
            continue
        result = _run_git(["merge-base", commit, "HEAD"])
        if result.returncode == 0:
            return result.stdout.strip()
        return commit
    return None


def _parse_added_lines(diff: str) -> set[int]:
    """Return the new-file line numbers added by a unified diff."""
    added: set[int] = set()
    new_lineno = 0
    in_hunk = False
    for raw_line in diff.splitlines():
        header = HUNK_RE.match(raw_line)
        if header:
            new_lineno = int(header.group(1))
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if raw_line.startswith("+"):
            added.add(new_lineno)
            new_lineno += 1
        elif raw_line.startswith("-"):
            continue
        elif raw_line.startswith(" "):
            new_lineno += 1
        elif raw_line.startswith("\\"):
            continue
        else:
            in_hunk = False
    return added


def added_lines(base: str, relative: str) -> set[int]:
    """Return added line numbers for one file."""
    diff = _git_output(
        [
            "diff",
            "--unified=0",
            "--no-color",
            "--no-ext-diff",
            base,
            "HEAD",
            "--",
            relative,
        ]
    )
    return _parse_added_lines(diff)


def changed_python_files(base: str, *, added_only: bool = False) -> list[str]:
    """Return changed (or newly added) Python paths under the repository."""
    diff_filter = "A" if added_only else "AMR"
    output = _git_output(
        [
            "diff",
            "--name-only",
            "-z",
            f"--diff-filter={diff_filter}",
            base,
            "HEAD",
        ]
    )
    return sorted(
        path for path in output.split("\0") if path.endswith(".py")
    )


def spdx_violation(relative: str, text: str) -> str | None:
    """Return a violation message when a new source/test file lacks the header."""
    if not relative.startswith(SPDX_PATHS):
        return None
    lines = text.splitlines()
    first_line = lines[0].rstrip() if lines else ""
    if first_line == SPDX_HEADER:
        return None
    return f"new Python file must start with {SPDX_HEADER!r}"


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _control_allowed(relative: str, class_name: str) -> bool:
    if class_name in RAW_PUSH_TOOL_CLASSES:
        return relative == BUTTON_COMPONENT or relative in RAW_BUTTON_ALLOWLIST
    if class_name in RAW_FORM_CONTROLS:
        return relative.startswith("src/gui/components/")
    if class_name in RAW_INPUT_CLASSES:
        return relative in RAW_INPUT_ALLOWLIST
    return True


def _noqa_violations(text: str, relative: str, added: set[int]) -> list[Violation]:
    violations: list[Violation] = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        for token in tokens:
            if token.type != tokenize.COMMENT or token.start[0] not in added:
                continue
            if "noqa" not in token.string:
                continue
            if NOQA_RE.search(token.string):
                continue
            violations.append(
                (
                    relative,
                    token.start[0],
                    "new # noqa comments need a code and reason: "
                    "'# noqa: CODE - reason'",
                )
            )
    except (IndentationError, SyntaxError, tokenize.TokenError) as error:
        violations.append(
            (relative, 1, f"could not tokenize changed file: {error}")
        )
    return violations


def check_added_lines(
    relative: str, text: str, added: set[int]
) -> list[Violation]:
    """Check one changed Python file at the supplied added line numbers."""
    violations = _noqa_violations(text, relative, added)
    if not relative.startswith("src/"):
        return violations

    try:
        tree = ast.parse(text, filename=relative)
    except SyntaxError as error:
        violations.append(
            (relative, error.lineno or 1, f"could not parse changed file: {error.msg}")
        )
        tree = None

    if tree is not None:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name == "print" and node.lineno in added:
                violations.append(
                    (relative, node.lineno, "use logger instead of print()")
                )
            if (
                name in RAW_CONTROL_CLASSES
                and node.lineno in added
                and not _control_allowed(relative, name)
            ):
                violations.append(
                    (
                        relative,
                        node.lineno,
                        f"use src.gui.components instead of {name}()",
                    )
                )

    if not relative.startswith("src/gui/icons/") and relative not in RAW_FONT_ALLOWLIST:
        lines = text.splitlines()
        for lineno in added:
            if lineno > len(lines):
                continue
            match = RAW_FONT_ICON.search(lines[lineno - 1])
            if match:
                violations.append(
                    (
                        relative,
                        lineno,
                        f"use a pack-independent icon key instead of {match.group(0)!r}",
                    )
                )
    return violations


def check_new_files(root: Path, new_files: list[str]) -> list[Violation]:
    """Enforce the SPDX header on newly added source and test files."""
    violations: list[Violation] = []
    for relative in new_files:
        if not relative.startswith(SPDX_PATHS):
            continue
        path = root / relative
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            violations.append((relative, 1, f"could not read new file: {error}"))
            continue
        message = spdx_violation(relative, text)
        if message:
            violations.append((relative, 1, message))
    return violations


def _emit(message: str) -> None:
    sys.stdout.write(f"{message}\n")


def _fail(message: str) -> None:
    sys.stderr.write(f"{message}\n")


def main(argv: list[str] | None = None) -> int:
    """Run the changed-file hygiene check."""
    parser = argparse.ArgumentParser(
        description="Check changed lines for hygiene regressions."
    )
    parser.add_argument(
        "--base",
        help="Git ref to compare with (defaults to the CI event or origin/master).",
    )
    args = parser.parse_args(argv)

    try:
        root = repo_root()
        base = resolve_base(args.base)
    except HygieneError as error:
        _fail(f"Changed-file hygiene could not run: {error}")
        return 2

    if base is None:
        _fail("Changed-file hygiene could not resolve a base commit; skipping.")
        return 0

    try:
        changed = changed_python_files(base)
        new_files = changed_python_files(base, added_only=True)
    except HygieneError as error:
        _fail(f"Changed-file hygiene could not diff against {base}: {error}")
        return 2

    violations: list[Violation] = []
    violations.extend(check_new_files(root, new_files))

    for relative in changed:
        path = root / relative
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            violations.append((relative, 1, f"could not read changed file: {error}"))
            continue
        try:
            lines = added_lines(base, relative)
        except HygieneError as error:
            _fail(f"Changed-file hygiene could not diff {relative}: {error}")
            return 2
        violations.extend(check_added_lines(relative, text, lines))

    if not changed:
        _emit(f"Changed-file hygiene: no Python changes against {base}.")
        return 0

    if violations:
        for relative, lineno, message in sorted(set(violations)):
            _fail(f"{relative}:{lineno}: {message}")
        _fail(
            f"Changed-file hygiene failed with {len(set(violations))} violation(s)."
        )
        return 1

    _emit(
        f"Changed-file hygiene: {len(changed)} changed Python file(s) "
        f"clean against {base}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

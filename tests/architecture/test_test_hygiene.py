# SPDX-License-Identifier: GPL-3.0-only
"""Guard the test-suite rules that keep CI fast and deterministic."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"

SLEEP_CALLS = {"time.sleep", "QTest.qWait"}
SKIP_CALLS = {
    "pytest.mark.skip",
    "pytest.mark.skipif",
    "pytest.mark.xfail",
    "unittest.skip",
    "unittest.skipIf",
}


def _call_path(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _sleep_calls(root: Path) -> list[str]:
    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _call_path(node.func) in SLEEP_CALLS:
                offenders.append(
                    f"{path.relative_to(root).as_posix()}:{node.lineno}"
                )
    return offenders


def _skip_calls_without_reason(root: Path) -> list[str]:
    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            decorators = getattr(node, "decorator_list", [])
            for decorator in decorators:
                if _call_path(decorator) in SKIP_CALLS:
                    offenders.append(
                        f"{path.relative_to(root).as_posix()}:"
                        f"{decorator.lineno}: missing reason="
                    )
            if not isinstance(node, ast.Call):
                continue
            if _call_path(node.func) not in SKIP_CALLS:
                continue
            reason = next(
                (
                    keyword.value
                    for keyword in node.keywords
                    if keyword.arg == "reason"
                ),
                None,
            )
            if reason is None or (
                isinstance(reason, ast.Constant)
                and not str(reason.value).strip()
            ):
                offenders.append(
                    f"{path.relative_to(root).as_posix()}:{node.lineno}: "
                    "missing non-empty reason="
                )
    return offenders


def test_tests_do_not_sleep_or_wait() -> None:
    offenders = _sleep_calls(TESTS)
    assert offenders == [], (
        "Run workers synchronously or use bounded signal/layout waits instead "
        "of time.sleep()/QTest.qWait():\n" + "\n".join(offenders)
    )


def test_sleep_scanner_detects_calls(tmp_path: Path) -> None:
    (tmp_path / "module.py").write_text(
        "time.sleep(1)\nQTest.qWait(1)\n",
        encoding="utf-8",
        newline="\n",
    )

    assert _sleep_calls(tmp_path) == ["module.py:1", "module.py:2"]


def test_skips_and_xfails_have_reasons() -> None:
    offenders = _skip_calls_without_reason(TESTS)
    assert offenders == [], (
        "Every skip/skipif/xfail needs a non-empty reason=:\n"
        + "\n".join(offenders)
    )


def test_skip_scanner_detects_missing_reasons(tmp_path: Path) -> None:
    (tmp_path / "module.py").write_text(
        "import pytest\n"
        "@pytest.mark.skip\n"
        "def test_a():\n"
        "    pass\n"
        "@pytest.mark.skipif(True)\n"
        "def test_b():\n"
        "    pass\n"
        '@pytest.mark.skip(reason="platform")\n'
        "def test_c():\n"
        "    pass\n",
        encoding="utf-8",
        newline="\n",
    )

    offenders = _skip_calls_without_reason(tmp_path)

    assert offenders == [
        "module.py:2: missing reason=",
        "module.py:5: missing non-empty reason=",
    ]

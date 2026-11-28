# SPDX-License-Identifier: GPL-3.0-only
"""Whole-source hygiene guards that are not tied to a GUI widget."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def _print_calls(root: Path) -> list[str]:
    calls: list[str] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
            ):
                calls.append(
                    f"{path.relative_to(root).as_posix()}:{node.lineno}"
                )
    return calls


def test_src_does_not_call_print() -> None:
    calls = _print_calls(SRC)
    assert calls == [], (
        "Use src.utils.logger instead of print() in application code:\n"
        + "\n".join(calls)
    )


def test_print_scanner_detects_a_call(tmp_path: Path) -> None:
    (tmp_path / "module.py").write_text(
        'print("debug")\n', encoding="utf-8", newline="\n"
    )

    assert _print_calls(tmp_path) == ["module.py:1"]

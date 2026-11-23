# SPDX-License-Identifier: GPL-3.0-only
"""Migration guard: controller methods called as ``self.foo`` need a delegate."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _method_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _self_calls(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
            calls.add(node.func.attr)
    return calls


def test_main_window_controller_calls_have_a_mixin_delegate():
    """A controller method reached through ``self`` must exist on the window mixins."""
    controller_methods: set[str] = set()
    for path in (ROOT / "src" / "gui" / "app").glob("*_controller.py"):
        controller_methods |= _method_names(path)

    mixin_paths = sorted((ROOT / "src" / "gui" / "main_window").glob("*.py"))
    mixin_methods: set[str] = set()
    for path in mixin_paths:
        mixin_methods |= _method_names(path)

    missing: list[str] = []
    for path in mixin_paths:
        for name in _self_calls(path):
            if name in controller_methods and name not in mixin_methods:
                missing.append(f"{path.relative_to(ROOT)}: self.{name}")

    assert missing == []

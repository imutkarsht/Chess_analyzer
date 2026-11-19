# SPDX-License-Identifier: GPL-3.0-only
"""Architecture guards: pure packages must never reach into Qt or the GUI layer."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = ("PyQt6", "src.gui")


def _package_parts(path: Path) -> list[str]:
    # Drop the module (or ``__init__``) name, leaving the containing package.
    return list(path.relative_to(ROOT).with_suffix("").parts)[:-1]


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    resolved: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            resolved.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                package = _package_parts(path)
                base = package[: len(package) - (node.level - 1)]
                module = ".".join([*base, module]) if module else ".".join(base)
            resolved.append(module)
    return resolved


def _violations(subpackage: str) -> list[str]:
    found: list[str] = []
    for path in sorted((ROOT / "src" / subpackage).rglob("*.py")):
        for module in _imports(path):
            if any(module == bad or module.startswith(f"{bad}.") for bad in FORBIDDEN):
                found.append(f"{path.relative_to(ROOT)}: {module}")
    return found


def test_utils_does_not_import_gui():
    violations = _violations("utils")
    assert not violations, "src/utils must stay Qt-free:\n" + "\n".join(violations)


@pytest.mark.xfail(strict=True, reason="Wave 3: move QThread workers to src/workers/")
def test_backend_does_not_import_gui():
    violations = _violations("backend")
    assert not violations, (
        "src/backend must stay Qt-free — move QThread workers to src/workers/:\n"
        + "\n".join(violations)
    )

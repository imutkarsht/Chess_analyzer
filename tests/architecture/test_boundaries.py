# SPDX-License-Identifier: GPL-3.0-only
"""Architecture guards: pure packages and workers must respect layer edges."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = ("PyQt6", "src.gui")
PURE_PACKAGES = ("backend", "utils", "config")
WORKER_FORBIDDEN = ("PyQt6.QtWidgets", "PyQt6.QtGui", "src.gui")


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


def _violations(subpackage: str, forbidden: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    for path in sorted((ROOT / "src" / subpackage).rglob("*.py")):
        for module in _imports(path):
            if any(module == bad or module.startswith(f"{bad}.") for bad in forbidden):
                found.append(f"{path.relative_to(ROOT)}: {module}")
    return found


@pytest.mark.parametrize("subpackage", PURE_PACKAGES)
def test_pure_packages_do_not_import_qt_or_gui(subpackage: str):
    violations = _violations(subpackage, FORBIDDEN)
    assert not violations, (
        f"src/{subpackage} must stay Qt-free — move QThread workers to src/workers/:\n"
        + "\n".join(violations)
    )


def test_workers_do_not_import_gui_or_widgets():
    violations = _violations("workers", WORKER_FORBIDDEN)
    assert not violations, (
        "src/workers must stay headless — use PyQt6.QtCore only and keep "
        "widgets in src/gui/:\n" + "\n".join(violations)
    )

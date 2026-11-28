# SPDX-License-Identifier: GPL-3.0-only
"""Whole-source hygiene guards that are not tied to a GUI widget."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
LOGGER_MODULE = SRC / "utils" / "logger.py"


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
                calls.append(f"{path.relative_to(root).as_posix()}:{node.lineno}")
    return calls


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def _logging_imports(root: Path) -> list[str]:
    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if path == LOGGER_MODULE:
            continue
        for module in _imports(path):
            if module == "logging" or module.startswith("logging."):
                offenders.append(
                    f"{path.relative_to(root).as_posix()}: {module}"
                )
    return offenders


def _owned_calls(root: Path) -> list[str]:
    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id == "QSettings":
                offenders.append(
                    f"{path.relative_to(root).as_posix()}:{node.lineno}: "
                    "QSettings()"
                )
            elif (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "QToolTip"
            ):
                offenders.append(
                    f"{path.relative_to(root).as_posix()}:{node.lineno}: "
                    f"QToolTip.{func.attr}()"
                )
    return offenders


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


def test_only_the_logger_module_imports_logging() -> None:
    offenders = _logging_imports(SRC)
    assert offenders == [], (
        "Use src.utils.logger instead of importing logging directly:\n"
        + "\n".join(offenders)
    )


def test_logging_scanner_detects_an_import(tmp_path: Path) -> None:
    (tmp_path / "module.py").write_text(
        "import logging\n", encoding="utf-8", newline="\n"
    )

    assert _logging_imports(tmp_path) == ["module.py: logging"]


def test_tooltips_and_settings_use_their_owners() -> None:
    offenders = _owned_calls(SRC)
    assert offenders == [], (
        "Use TooltipManager/attach_tooltip instead of QToolTip, and "
        "ConfigManager/QSettings through src.config instead of raw QSettings:\n"
        + "\n".join(offenders)
    )


def test_owned_call_scanner_detects_calls(tmp_path: Path) -> None:
    (tmp_path / "module.py").write_text(
        "QSettings()\nQToolTip.showText(None, 'text')\n",
        encoding="utf-8",
        newline="\n",
    )

    assert _owned_calls(tmp_path) == [
        "module.py:1: QSettings()",
        "module.py:2: QToolTip.showText()",
    ]

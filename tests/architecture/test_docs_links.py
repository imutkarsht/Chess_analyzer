# SPDX-License-Identifier: GPL-3.0-only
"""Keep relative Markdown links in project documentation pointing at real files."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC_FILES = [
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "ARCHITECTURE.md",
    *sorted((ROOT / "docs").rglob("*.md")),
]

_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_SKIP_PREFIXES = ("http://", "https://", "mailto:", "#")


def _relative_targets(text: str) -> list[str]:
    targets: list[str] = []
    for raw in _LINK.findall(text):
        target = raw.strip().split()[0].strip("<>")
        if target.startswith(_SKIP_PREFIXES):
            continue
        target = target.split("#", 1)[0]
        if target:
            targets.append(target)
    return targets


def test_relative_documentation_links_resolve():
    missing: list[str] = []
    for document in DOC_FILES:
        for target in _relative_targets(document.read_text(encoding="utf-8")):
            resolved = (document.parent / target).resolve()
            if not resolved.exists():
                missing.append(f"{document.relative_to(ROOT)} -> {target}")

    assert not missing, "Broken relative documentation links:\n" + "\n".join(missing)

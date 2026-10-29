"""Import boundary for the shared component library.

Components live in subpackages (controls, lists, feedback, layout, display) so the
folder can stay navigable as it grows. Call sites must import through the
``src.gui.components`` facade so regrouping never breaks them; this test pins that
rule and would have caught the flat-module imports that predated the reorg.
"""

import re
from pathlib import Path

COMPONENT_GROUPS = {"controls", "lists", "feedback", "layout", "display"}
_MODULE_REFERENCE = re.compile(r"components\.([a-z_]+)")


def test_components_are_imported_through_the_facade_only():
    repo_root = Path(__file__).resolve().parents[2]
    package_root = (repo_root / "src" / "gui" / "components").as_posix()

    offenders: list[str] = []
    for path in list((repo_root / "src").rglob("*.py")) + list(
        (repo_root / "tests").rglob("*.py")
    ):
        if package_root in path.as_posix():
            continue
        text = path.read_text(encoding="utf-8")
        for match in _MODULE_REFERENCE.finditer(text):
            module = match.group(1)
            if module not in COMPONENT_GROUPS:
                offenders.append(f"{path.relative_to(repo_root).as_posix()}: components.{module}")

    assert not offenders, "Import from src.gui.components, not a subpackage:\n" + "\n".join(
        offenders
    )

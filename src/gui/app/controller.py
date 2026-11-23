# SPDX-License-Identifier: GPL-3.0-only
"""Lifecycle contract for MainWindow workflow controllers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PageController(Protocol):
    """A workflow owner attached to MainWindow with deterministic teardown."""

    def attach(self, host) -> None:
        """Bind the controller to the window that owns its widgets."""
        ...

    def shutdown(self) -> None:
        """Stop workers/timers and release owned resources."""
        ...

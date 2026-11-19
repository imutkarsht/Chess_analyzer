# SPDX-License-Identifier: GPL-3.0-only
"""Consistent external URL and local-path opening for GUI callers."""

from __future__ import annotations

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices


def open_url(url: str) -> bool:
    """Open an external URL with the platform's default handler."""
    return QDesktopServices.openUrl(QUrl(url))


def open_path(path: str) -> bool:
    """Open a local file or directory with the platform's default handler."""
    return QDesktopServices.openUrl(QUrl.fromLocalFile(path))

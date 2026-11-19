# SPDX-License-Identifier: GPL-3.0-only
"""Shared GitHub release API access for updates and engine downloads."""

from __future__ import annotations

import requests

from src.constants import APP_VERSION, GITHUB_REPO_URL

GITHUB_ACCEPT = "application/vnd.github+json"
GITHUB_USER_AGENT = f"ChessAnalyzerPro/{APP_VERSION} ({GITHUB_REPO_URL})"


def fetch_release(api_url: str, *, timeout: float = 15) -> dict:
    """Fetch one GitHub release payload, raising on HTTP errors."""
    response = requests.get(
        api_url,
        headers={
            "Accept": GITHUB_ACCEPT,
            "User-Agent": GITHUB_USER_AGENT,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def fetch_release_assets(api_url: str, *, timeout: float = 15) -> list[dict]:
    """Fetch the raw asset list for one GitHub release."""
    return fetch_release(api_url, timeout=timeout).get("assets", [])

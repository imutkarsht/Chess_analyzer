"""Live, network-dependent check for the Stockfish downloader.

These tests hit the real GitHub release API to confirm upstream asset names
still resolve. They are skipped by default; run them explicitly with:

    RUN_LIVE_STOCKFISH_TESTS=1 pytest tests/backend/test_stockfish_live.py

Handy after touching src/backend/engine/downloader.py or before a release.
"""
import os

import pytest

from src.backend.engine.downloader import (
    get_current_platform,
    get_download_candidates,
    select_assets,
    get_official_releases,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_STOCKFISH_TESTS") != "1",
    reason="live network test; set RUN_LIVE_STOCKFISH_TESTS=1 to run",
)


def test_latest_release_has_a_match_for_this_platform():
    releases = get_official_releases()
    assert releases, "GitHub returned no assets for the latest Stockfish release"

    matches = select_assets(releases)
    if not matches:
        available = ", ".join(a.name for a in releases)
        pytest.fail(
            f"No Stockfish asset matched platform {get_current_platform()}. "
            f"Available assets: {available}"
        )

    assert matches[0].url.startswith("https://")


def test_download_candidates_are_available():
    candidates = get_download_candidates()
    assert candidates, "No download candidates resolved from latest or pinned release"

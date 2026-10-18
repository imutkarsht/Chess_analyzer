"""
Tests for the piece theme loader.

The piece graphics used to be embedded as inline SVG strings inside
``src/gui/board/piece_themes.py``. This caused license-separation issues
because copyleft third-party graphics lived in the same MIT-licensed
source file. The refactor moved the graphics into individual
``assets/pieces/*.svg`` files and turned the Python module into a
thin loader.

These tests pin down the new behaviour:

* ``get_piece_defs`` must return a non-empty string that contains
  one ``<g>`` element for every piece.
* The piece symbols K, Q, R, B, N, P, k, q, r, b, n, p must all be
  present (this matches the SAN-style letters used by python-chess).
* The theme-name API must keep working for backwards compatibility
  with ``settings_view.py`` and the config system.
* The graphics are loaded from disk on every call (so a hot-reload
  workflow would pick up a new theme after restart). We don't test
  for caching here on purpose: the contract is "load at call time".
"""

import os

from src.gui.board.piece_themes import (
    PIECE_THEMES,
    STANDARD_THEME_FILES,
    _load_theme,
    get_piece_defs,
    get_piece_theme_names,
)
from src.utils.path_utils import get_resource_path

# All 12 piece symbols, in the order returned by get_piece_defs().
EXPECTED_PIECE_IDS = [
    "white-king",
    "white-queen",
    "white-rook",
    "white-bishop",
    "white-knight",
    "white-pawn",
    "black-king",
    "black-queen",
    "black-rook",
    "black-bishop",
    "black-knight",
    "black-pawn",
]


def test_standard_theme_assets_exist():
    """Each entry in STANDARD_THEME_FILES must exist in assets/pieces/ and outside src/."""
    assert set(STANDARD_THEME_FILES.keys()) == set("KQRBNPkqrbnp")
    assert len(STANDARD_THEME_FILES) == 12

    for _symbol, filename in STANDARD_THEME_FILES.items():
        asset_path = get_resource_path(os.path.join("assets/pieces", filename))
        assert os.path.isfile(asset_path), f"Missing piece file: {asset_path}"
        assert os.sep + "src" + os.sep not in asset_path, (
            f"Asset {asset_path!r} lives under src/, graphics must be kept in assets/pieces/"
        )


def test_get_piece_defs_structure():
    """get_piece_defs returns all 12 piece <g id="..."> IDs and defaults to Standard."""
    defs_default = get_piece_defs()
    defs_standard = get_piece_defs("Standard")
    assert defs_default == defs_standard
    assert len(defs_standard) > 0

    for piece_id in EXPECTED_PIECE_IDS:
        assert f'id="{piece_id}"' in defs_standard, f"Expected piece id={piece_id!r} in defs"


def test_piece_theme_names_and_lookup():
    """Theme naming and lookup dictionaries maintain compatibility."""
    names = get_piece_theme_names()
    assert "Standard" in names
    assert isinstance(names, list)
    assert "Standard" in PIECE_THEMES
    assert PIECE_THEMES["Standard"] is STANDARD_THEME_FILES


def test_piece_themes_caching():
    """get_piece_defs must hit the cache on subsequent calls."""
    from src.gui.board.piece_themes import _load_theme_cached

    _load_theme_cached.cache_clear()
    assert _load_theme_cached.cache_info().hits == 0

    # First call: cache miss
    get_piece_defs("Standard")
    assert _load_theme_cached.cache_info().misses == 1
    assert _load_theme_cached.cache_info().hits == 0

    # Second call: cache hit
    get_piece_defs("Standard")
    assert _load_theme_cached.cache_info().misses == 1
    assert _load_theme_cached.cache_info().hits == 1


def test_piece_themes_fallbacks_and_fatal_failure(mocker):
    """Unknown or broken themes fall back to Standard; fatal errors return empty string."""
    from src.gui.board.piece_themes import _load_theme_cached

    _load_theme_cached.cache_clear()

    # Case 1: Unknown theme name falls back to Standard
    defs_unknown = get_piece_defs("DefinitelyDoesNotExist")
    defs_standard = get_piece_defs("Standard")
    assert defs_unknown == defs_standard

    # Case 2: Broken theme falls back to Standard
    original_load = _load_theme

    def mock_load(theme_name):
        if theme_name == "BrokenTheme":
            raise FileNotFoundError("Mock broken theme file missing")
        return original_load(theme_name)

    mocker.patch("src.gui.board.piece_themes._load_theme", side_effect=mock_load)
    defs_broken = get_piece_defs("BrokenTheme")
    assert 'id="white-king"' in defs_broken

    # Case 3: Fatal failure (even fallback missing) returns empty string without crashing
    _load_theme_cached.cache_clear()
    mocker.patch(
        "src.gui.board.piece_themes._load_theme",
        side_effect=FileNotFoundError("Standard missing too"),
    )
    assert get_piece_defs("Standard") == ""

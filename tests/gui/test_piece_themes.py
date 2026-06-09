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

import pytest

from src.gui.board.piece_themes import (
    PIECE_THEMES,
    STANDARD_THEME_FILES,
    _extract_g_element,
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


def test_standard_theme_files_contains_all_12_pieces():
    """The Standard theme must list exactly the 12 SAN-style pieces."""
    assert set(STANDARD_THEME_FILES.keys()) == set("KQRBNPkqrbnp")
    assert len(STANDARD_THEME_FILES) == 12


def test_every_svg_file_exists():
    """Each entry in STANDARD_THEME_FILES must point to a real file."""
    for symbol, filename in STANDARD_THEME_FILES.items():
        path = get_resource_path(os.path.join("assets/pieces", filename))
        assert os.path.isfile(path), f"Missing piece file: {path}"


def test_get_piece_defs_returns_non_empty_string():
    """get_piece_defs must return a non-empty string."""
    defs = get_piece_defs("Standard")
    assert isinstance(defs, str)
    assert len(defs) > 0


def test_get_piece_defs_contains_all_12_piece_ids():
    """get_piece_defs must include the <g id="..."> for every piece."""
    defs = get_piece_defs("Standard")
    for piece_id in EXPECTED_PIECE_IDS:
        assert f'id="{piece_id}"' in defs, (
            f"Expected piece id={piece_id!r} in defs, got: {defs[:200]!r}"
        )


def test_get_piece_defs_default_is_standard():
    """Calling get_piece_defs() with no args must yield the Standard theme."""
    defs_default = get_piece_defs()
    defs_standard = get_piece_defs("Standard")
    assert defs_default == defs_standard


def test_get_piece_defs_unknown_theme_falls_back_to_standard():
    """Unknown theme names must fall back to the Standard theme."""
    defs_unknown = get_piece_defs("DefinitelyDoesNotExist")
    defs_standard = get_piece_defs("Standard")
    assert defs_unknown == defs_standard


def test_get_piece_theme_names_includes_standard():
    """get_piece_theme_names must list at least the Standard theme."""
    names = get_piece_theme_names()
    assert "Standard" in names
    assert isinstance(names, list)


def test_piece_themes_dict_still_contains_standard():
    """Backwards-compat: PIECE_THEMES['Standard'] must still be present."""
    assert "Standard" in PIECE_THEMES
    assert PIECE_THEMES["Standard"] is STANDARD_THEME_FILES


def test_extract_g_element_returns_g_string():
    """_extract_g_element must return a <g> element string."""
    path = get_resource_path(
        os.path.join("assets/pieces", "white-king.svg")
    )
    g_str = _extract_g_element(path)
    assert g_str.startswith("<g")
    assert g_str.rstrip().endswith("</g>")
    assert 'id="white-king"' in g_str


def test_load_theme_returns_all_12_pieces():
    """_load_theme must return a dict with all 12 SAN-style symbols."""
    pieces = _load_theme("Standard")
    assert set(pieces.keys()) == set("KQRBNPkqrbnp")
    for symbol, g_str in pieces.items():
        assert g_str.startswith("<g"), (
            f"Piece {symbol!r} did not yield a <g> string: {g_str[:60]!r}"
        )


def test_assets_pieces_directory_is_separate_from_source():
    """The piece SVGs must live under assets/, not next to the loader.

    This is the whole point of the refactor: MIT-licensed source code
    stays in src/, CC BY-SA / GPLv2+ graphics stay in assets/. The
    refactor would be undone by moving the files back.
    """
    # piece_themes.py is at src/gui/board/piece_themes.py
    loader_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..", "..",
            "src", "gui", "board", "piece_themes.py",
        )
    )
    assert os.path.isfile(loader_path)

    # Every asset path is resolved through get_resource_path(assets/pieces/..)
    # and must NOT live under src/.
    for filename in STANDARD_THEME_FILES.values():
        asset_path = get_resource_path(os.path.join("assets/pieces", filename))
        assert os.path.isfile(asset_path)
        assert os.sep + "src" + os.sep not in asset_path, (
            f"Asset {asset_path!r} lives under src/, the third-party "
            f"graphics must be kept in assets/pieces/ for license separation"
        )


def test_piece_themes_caching():
    """get_piece_defs must hit the cache on subsequent calls."""
    from src.gui.board.piece_themes import _load_theme_cached
    _load_theme_cached.cache_clear()
    
    info_before = _load_theme_cached.cache_info()
    assert info_before.hits == 0
    assert info_before.misses == 0

    # First call: cache miss
    get_piece_defs("Standard")
    info_after_first = _load_theme_cached.cache_info()
    assert info_after_first.misses == 1
    assert info_after_first.hits == 0

    # Second call: cache hit
    get_piece_defs("Standard")
    info_after_second = _load_theme_cached.cache_info()
    assert info_after_second.misses == 1
    assert info_after_second.hits == 1


def test_piece_themes_fallback_to_standard(mocker):
    """When a theme fails to load, it must fall back to the Standard theme."""
    from src.gui.board.piece_themes import _load_theme_cached
    _load_theme_cached.cache_clear()

    original_load = _load_theme

    def mock_load(theme_name):
        if theme_name == "BrokenTheme":
            raise FileNotFoundError("Mock broken theme file missing")
        return original_load(theme_name)

    mocker.patch(
        "src.gui.board.piece_themes._load_theme",
        side_effect=mock_load
    )

    # Calling broken theme should return the standard theme definitions via fallback
    defs = get_piece_defs("BrokenTheme")
    assert len(defs) > 0
    assert 'id="white-king"' in defs


def test_piece_themes_fatal_failure_returns_empty_string(mocker):
    """When the fallback theme also fails to load, get_piece_defs must return an empty string."""
    from src.gui.board.piece_themes import _load_theme_cached
    _load_theme_cached.cache_clear()

    mocker.patch(
        "src.gui.board.piece_themes._load_theme",
        side_effect=FileNotFoundError("Standard missing too")
    )
    defs = get_piece_defs("Standard")
    assert defs == ""


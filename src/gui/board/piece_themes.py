"""
Chess piece theme loader for custom board rendering.

This module is a thin loader that reads SVG piece graphics from the
``assets/pieces/`` directory at runtime. The graphics themselves live in
external SVG files so the MIT-licensed project source and the
third-party CC BY-SA / GPLv2+ graphics remain physically separate.

The piece graphics are the **Cburnett** set, originally by
Colin M.L. Burnett, distributed via Wikimedia Commons:
    https://commons.wikimedia.org/wiki/Category:SVG_chess_pieces
They are dual-licensed under GPLv2+ and CC BY-SA 3.0 (Unported).

They are NOT covered by the MIT License that applies to the rest
of this project. See ``assets/pieces/THIRD-PARTY-README.md`` and the
``THIRD-PARTY COMPONENT NOTICE`` section in the project root
``LICENSE`` file for the full attribution and license terms.
"""

import os
import xml.etree.ElementTree as ET
from functools import lru_cache

from ...utils.path_utils import get_resource_path
from ...utils.logger import logger


# Directory that holds the third-party piece SVGs.
# This path is intentionally outside of the Python source tree so that the
# MIT-licensed code and the CC BY-SA / GPLv2+ graphics can be licensed
# independently (see THIRD-PARTY-README.md).
PIECE_ASSETS_DIR = "assets/pieces"

# Map of piece symbol (the SAN-style letter used by python-chess) to the
# SVG file that contains the corresponding graphic. The file content is
# loaded at runtime by :func:`get_piece_defs`.
STANDARD_THEME_FILES = {
    "K": "white-king.svg",
    "Q": "white-queen.svg",
    "R": "white-rook.svg",
    "B": "white-bishop.svg",
    "N": "white-knight.svg",
    "P": "white-pawn.svg",
    "k": "black-king.svg",
    "q": "black-queen.svg",
    "r": "black-rook.svg",
    "b": "black-bishop.svg",
    "n": "black-knight.svg",
    "p": "black-pawn.svg",
}

# All available themes. A theme is a name plus a mapping of piece-symbol
# to SVG-filename. Additional themes can be added in the future by adding
# a new subdirectory under ``assets/pieces/<theme-name>/`` with the same
# 12 file names.
PIECE_THEMES = {
    "Standard": STANDARD_THEME_FILES,
}


def _extract_g_element(svg_path: str) -> str:
    """
    Read an SVG file and return the inner ``<g>...</g>`` string.

    The renderer in :mod:`board_widget` embeds the pieces as a single
    ``<defs><g id="...">...</g></defs>`` block, so we strip the wrapping
    ``<svg>`` element here and return only the ``<g>`` content.

    Args:
        svg_path: Absolute path to the SVG file on disk.

    Returns:
        The ``<g>`` element as a string (without the wrapping ``<svg>``).

    Raises:
        FileNotFoundError: If the SVG file does not exist.
        ET.ParseError: If the file is not well-formed XML.
        ValueError: If the SVG does not contain a ``<g>`` element.
    """
    tree = ET.parse(svg_path)
    root = tree.getroot()

    g_elements = [
        child
        for child in root
        if child.tag.endswith("}g") or child.tag == "g"
    ]
    if not g_elements:
        raise ValueError(
            f"SVG file {svg_path!r} does not contain a <g> element"
        )

    # We only support single-piece SVG files, so there should be exactly
    # one <g> inside the wrapping <svg>.
    if len(g_elements) != 1:
        raise ValueError(
            f"SVG file {svg_path!r} contains {len(g_elements)} <g> "
            f"elements, expected exactly 1"
        )

    g_elem = g_elements[0]

    # Strip the default XML namespace so the serialised <g> renders as
    # ``<g>`` (and not ``<ns0:g xmlns:ns0=...>``). The namespace is only
    # needed at the wrapping <svg> root, which we discard here. Browsers
    # and QtSvg handle the un-prefixed form correctly, and downstream
    # code in board_widget.py parses the result with a wrapping <root
    # xmlns="..."> container that re-introduces the namespace cleanly.
    if "}" in g_elem.tag:
        g_elem.tag = "g"
    for descendant in g_elem.iter():
        if "}" in descendant.tag:
            descendant.tag = descendant.tag.split("}", 1)[1]

    return ET.tostring(g_elem, encoding="unicode")


@lru_cache(maxsize=16)
def _load_theme_cached(theme_name: str) -> dict:
    """
    Cache-wrapped internal helper to load a theme.
    
    This function will raise FileNotFoundError, ET.ParseError, or ValueError
    on failure. Exceptions are not cached by lru_cache, ensuring that retries
    will attempt to read from disk again.
    """
    return _load_theme(theme_name)


def _load_theme(theme_name: str) -> dict:
    """
    Load a piece theme by name and return a ``{piece_symbol: <g>...</g>}``
    dict.

    Args:
        theme_name: The theme name (a key of :data:`PIECE_THEMES`).

    Returns:
        Dict mapping piece symbol to the corresponding ``<g>`` element
        string, ready to be embedded inside an SVG ``<defs>`` block.
    """
    theme_files = PIECE_THEMES.get(theme_name, STANDARD_THEME_FILES)
    pieces = {}
    for symbol, filename in theme_files.items():
        svg_path = get_resource_path(os.path.join(PIECE_ASSETS_DIR, filename))
        pieces[symbol] = _extract_g_element(svg_path)
    return pieces


def get_piece_defs(theme_name: str = "Standard") -> str:
    """
    Generate SVG defs section with piece definitions for the given theme.

    This loads the piece graphics from ``assets/pieces/`` and caches successful
    results. If a theme fails to load, it falls back to the Standard theme.
    If the Standard theme also fails to load, it returns an empty string.

    Args:
        theme_name: Name of the piece theme to use.

    Returns:
        SVG string containing the ``<g>`` elements for all 12 pieces,
        ready to be embedded in a parent ``<svg>`` ``<defs>`` block.
    """
    try:
        pieces = _load_theme_cached(theme_name)
        return "\n".join(pieces[symbol] for symbol in STANDARD_THEME_FILES)
    except Exception as e:
        logger.error(f"Failed to load piece theme {theme_name!r}: {e}")
        if theme_name != "Standard":
            logger.info("Attempting fallback to 'Standard' piece theme.")
            try:
                pieces = _load_theme_cached("Standard")
                return "\n".join(pieces[symbol] for symbol in STANDARD_THEME_FILES)
            except Exception as fallback_err:
                logger.error(
                    f"Failed to load fallback 'Standard' piece theme: {fallback_err}"
                )
        return ""


def get_piece_theme_names() -> list:
    """
    Get list of available piece theme names.

    Returns:
        List of theme name strings.
    """
    return list(PIECE_THEMES.keys())

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
import re
import shutil
import xml.etree.ElementTree as ET
from functools import lru_cache

import chess

from ...utils.path_utils import get_resource_path, get_user_data_dir
from ...utils.logger import logger


PIECE_ASSETS_DIR = "assets/pieces"
USER_THEMES_DIR_NAME = "themes"

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

SHORT_THEME_FILES = {
    "K": "wk.svg", "Q": "wq.svg", "R": "wr.svg", "B": "wb.svg",
    "N": "wn.svg", "P": "wp.svg",
    "k": "bk.svg", "q": "bq.svg", "r": "br.svg", "b": "bb.svg",
    "n": "bn.svg", "p": "bp.svg",
}

PIECE_THEMES: dict[str, dict[str, str]] = {
    "Standard": STANDARD_THEME_FILES,
}

REQUIRED_THEME_FILES = set(SHORT_THEME_FILES.values())
_PIECE_TYPE_INDEX = {"p": 1, "n": 2, "b": 3, "r": 4, "q": 5, "k": 6}


def _expected_id(symbol: str) -> str:
    """Return the SVG element id that board_widget.py references via <use>."""
    color = "white" if symbol.isupper() else "black"
    return f"{color}-{chess.PIECE_NAMES[_PIECE_TYPE_INDEX[symbol.lower()]]}"


def get_user_themes_dir() -> str:
    themes_dir = os.path.join(get_user_data_dir(), USER_THEMES_DIR_NAME)
    os.makedirs(themes_dir, exist_ok=True)
    return themes_dir


def validate_theme_folder(folder_path: str) -> tuple[bool, list[str]]:
    """Check *folder_path* contains all 12 required SVG files (existence + valid XML)."""
    errors: list[str] = []

    if not os.path.isdir(folder_path):
        return False, [f"Folder does not exist: {folder_path}"]

    missing = []
    for filename in sorted(REQUIRED_THEME_FILES):
        if not os.path.isfile(os.path.join(folder_path, filename)):
            missing.append(filename)

    if missing:
        errors.append(
            f"Missing {len(missing)} of 12 required files: {', '.join(missing)}"
        )

    for filename in sorted(REQUIRED_THEME_FILES):
        file_path = os.path.join(folder_path, filename)
        if not os.path.isfile(file_path):
            continue
        try:
            _extract_g_element(file_path)
        except ET.ParseError:
            errors.append(f"{filename} is not valid XML/SVG")
        except OSError as e:
            errors.append(f"{filename}: {e}")

    return len(errors) == 0, errors


def import_theme_from_folder(folder_path: str) -> str | None:
    """Validate, copy, and register a user piece-theme folder. Returns the theme name or None."""
    is_valid, validation_errors = validate_theme_folder(folder_path)
    if not is_valid:
        logger.error(f"Cannot import theme: {validation_errors}")
        return None

    base_name = os.path.basename(os.path.normpath(folder_path))
    if not base_name:
        base_name = "Imported Theme"

    # "Standard" is reserved for the built-in Cburnett set
    if base_name == "Standard":
        base_name = "Custom Standard"

    final_name = _unique_theme_name(base_name)

    dest = os.path.join(get_user_themes_dir(), final_name)
    try:
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(folder_path, dest)
    except Exception as e:
        logger.error(f"Failed to copy theme folder to {dest}: {e}")
        return None

    scan_user_themes()
    clear_theme_cache()

    logger.info(f"Imported piece theme {final_name!r} from {folder_path}")
    return final_name


def _unique_theme_name(base_name: str) -> str:
    """Return *base_name* if unused, otherwise append a counter suffix."""
    if base_name not in PIECE_THEMES:
        return base_name
    counter = 2
    while f"{base_name} ({counter})" in PIECE_THEMES:
        counter += 1
    return f"{base_name} ({counter})"


def scan_user_themes() -> None:
    """Scan the user themes directory and register valid themes."""
    user_dir = get_user_themes_dir()

    new_themes: dict[str, dict[str, str]] = {"Standard": STANDARD_THEME_FILES}

    if os.path.isdir(user_dir):
        for entry in sorted(os.listdir(user_dir)):
            theme_dir = os.path.join(user_dir, entry)
            if not os.path.isdir(theme_dir):
                continue
            if not _has_required_files(theme_dir):
                logger.debug(f"Skipping incomplete theme folder {entry!r}")
                continue
            abs_files: dict[str, str] = {}
            for symbol, rel_path in SHORT_THEME_FILES.items():
                abs_files[symbol] = os.path.join(theme_dir, rel_path)
            new_themes[entry] = abs_files

    PIECE_THEMES.clear()
    PIECE_THEMES.update(new_themes)


def _has_required_files(theme_dir: str) -> bool:
    """Return True if *theme_dir* contains all 12 required files."""
    for filename in REQUIRED_THEME_FILES:
        if not os.path.isfile(os.path.join(theme_dir, filename)):
            return False
    return True


_RE_NUM = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
_RE_URL_REF = re.compile(r"url\(\s*#([^)\s]+)\s*\)")


def _prefix_def_refs(elem: ET.Element, prefix: str) -> None:
    """Prefix ``url(#id)`` and ``href=\"#id\"`` references in *elem* with *prefix*."""
    for child in elem.iter():
        for attr in list(child.attrib):
            val = child.attrib[attr]
            new_val = _RE_URL_REF.sub(
                lambda m: f"url(#{prefix}_{m.group(1)})", val
            )
            if attr == "href" and val.startswith("#") and len(val) > 1:
                new_val = f"#{prefix}_{val[1:]}"
            if new_val != val:
                child.attrib[attr] = new_val


def _parse_path_points(d: str) -> list[tuple[float, float]]:
    """Extract all (x, y) coordinate pairs from SVG path data."""
    tokens = re.findall(
        r"[MLHVCSQTAZmlhvcsqtaz]|-?\d*\.?\d+(?:[eE][-+]?\d+)?", d
    )
    points = []
    i = 0
    cur_x = cur_y = 0.0

    while i < len(tokens):
        cmd = tokens[i]
        i += 1
        nums = []
        while i < len(tokens) and re.match(r"^-?\d", tokens[i]):
            nums.append(float(tokens[i]))
            i += 1

        j = 0
        while j < len(nums):
            if cmd in "Zz":
                break
            elif cmd in "Hh":
                x = nums[j]; j += 1
                cur_x = cur_x + x if cmd.islower() else x
                points.append((cur_x, cur_y))
            elif cmd in "Vv":
                y = nums[j]; j += 1
                cur_y = cur_y + y if cmd.islower() else y
                points.append((cur_x, cur_y))
            elif cmd in "Aa":
                if j + 7 <= len(nums):
                    x = nums[j + 5]; y = nums[j + 6]
                    j += 7
                    cur_x = cur_x + x if cmd.islower() else x
                    cur_y = cur_y + y if cmd.islower() else y
                    points.append((cur_x, cur_y))
                else:
                    break
            elif cmd in "Cc":
                if j + 6 <= len(nums):
                    pts = nums[j:j + 6]; j += 6
                    if cmd.islower():
                        pts[0] += cur_x; pts[1] += cur_y
                        pts[2] += cur_x; pts[3] += cur_y
                        pts[4] += cur_x; pts[5] += cur_y
                    points.extend([(pts[0], pts[1]), (pts[2], pts[3]), (pts[4], pts[5])])
                    cur_x, cur_y = pts[4], pts[5]
                else:
                    break
            elif cmd in "Ss":
                if j + 4 <= len(nums):
                    pts = nums[j:j + 4]; j += 4
                    if cmd.islower():
                        pts[0] += cur_x; pts[1] += cur_y
                        pts[2] += cur_x; pts[3] += cur_y
                    points.extend([(pts[0], pts[1]), (pts[2], pts[3])])
                    cur_x, cur_y = pts[2], pts[3]
                else:
                    break
            elif cmd in "Qq":
                if j + 4 <= len(nums):
                    pts = nums[j:j + 4]; j += 4
                    if cmd.islower():
                        pts[0] += cur_x; pts[1] += cur_y
                        pts[2] += cur_x; pts[3] += cur_y
                    points.extend([(pts[0], pts[1]), (pts[2], pts[3])])
                    cur_x, cur_y = pts[2], pts[3]
                else:
                    break
            elif cmd in "Tt":
                if j + 2 <= len(nums):
                    x = nums[j]; y = nums[j + 1]; j += 2
                    if cmd.islower():
                        x += cur_x; y += cur_y
                    points.append((x, y))
                    cur_x, cur_y = x, y
                else:
                    break
            else:  # M, L, m, l
                if j + 2 <= len(nums):
                    x = nums[j]; y = nums[j + 1]; j += 2
                    if cmd.islower():
                        cur_x += x
                        cur_y += y
                    else:
                        cur_x, cur_y = x, y
                    points.append((cur_x, cur_y))
                else:
                    break

    return points


def _parse_points_attr(attr: str) -> list[tuple[float, float]]:
    """Parse SVG points attribute into coordinate pairs."""
    nums = list(map(float, _RE_NUM.findall(attr)))
    return [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]


def _strip_ns(elem: ET.Element) -> None:
    """Strip XML namespace from *elem* tags and attribute keys in-place."""
    if "}" in elem.tag:
        elem.tag = elem.tag.split("}", 1)[1]
    for child in elem.iter():
        if "}" in child.tag:
            child.tag = child.tag.split("}", 1)[1]
        ns_keys = [k for k in child.attrib if "}" in k]
        for k in ns_keys:
            child.attrib[k.split("}", 1)[1]] = child.attrib.pop(k)


def _get_svg_canvas(root: ET.Element) -> tuple[float, float] | None:
    """Return (width, height) from viewBox or width/height attributes."""
    viewbox = root.get("viewBox", "")
    if viewbox:
        parts = viewbox.split()
        if len(parts) == 4:
            return float(parts[2]), float(parts[3])

    w_str = root.get("width", "")
    h_str = root.get("height", "")
    if w_str and h_str:
        try:
            return (float(_RE_NUM.search(w_str).group()),
                    float(_RE_NUM.search(h_str).group()))
        except (ValueError, AttributeError):
            pass

    return None


@lru_cache(maxsize=128)
def _get_content_bbox(svg_path: str) -> tuple[float, float, float, float]:
    """Return (min_x, min_y, max_x, max_y) of all graphical elements in *svg_path*."""
    tree = ET.parse(svg_path)
    root = tree.getroot()

    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")

    def _accumulate(x: float, y: float) -> None:
        nonlocal min_x, min_y, max_x, max_y
        if x < min_x: min_x = x
        if y < min_y: min_y = y
        if x > max_x: max_x = x
        if y > max_y: max_y = y

    for elem in root.iter():
        tag = elem.tag.split("}", 1)[1] if "}" in elem.tag else elem.tag

        t = elem.get("transform", "")
        m = re.search(r"matrix\(([^)]+)\)", t)
        if m:
            values = list(map(float, _RE_NUM.findall(m.group(1))))
            if len(values) == 6:
                a, b, c, d_val, e, f = values
            else:
                a, b, c, d_val, e, f = 1.0, 0.0, 0.0, 1.0, 0.0, 0.0
        else:
            a, b, c, d_val, e, f = 1.0, 0.0, 0.0, 1.0, 0.0, 0.0

        def _apply(x: float, y: float) -> tuple[float, float]:
            return a * x + c * y + e, b * x + d_val * y + f

        if tag == "path":
            d = elem.get("d", "")
            if not d:
                continue
            for px, py in _parse_path_points(d):
                _accumulate(*_apply(px, py))

        elif tag in ("polygon", "polyline"):
            pts = elem.get("points", "")
            if not pts:
                continue
            for px, py in _parse_points_attr(pts):
                _accumulate(*_apply(px, py))

        elif tag == "circle":
            cx = float(elem.get("cx", 0))
            cy = float(elem.get("cy", 0))
            r = float(elem.get("r", 0))
            for px, py in [(cx - r, cy - r), (cx + r, cy + r)]:
                _accumulate(*_apply(px, py))

        elif tag == "rect":
            rx = float(elem.get("x", 0))
            ry = float(elem.get("y", 0))
            rw = float(elem.get("width", 0))
            rh = float(elem.get("height", 0))
            for px, py in [(rx, ry), (rx + rw, ry), (rx, ry + rh), (rx + rw, ry + rh)]:
                _accumulate(*_apply(px, py))

        elif tag == "ellipse":
            cx = float(elem.get("cx", 0))
            cy = float(elem.get("cy", 0))
            rx = float(elem.get("rx", 0))
            ry = float(elem.get("ry", 0))
            for px, py in [(cx - rx, cy - ry), (cx + rx, cy + ry)]:
                _accumulate(*_apply(px, py))

    if min_x == float("inf"):
        return 0.0, 0.0, 0.0, 0.0

    return min_x, min_y, max_x, max_y


def _extract_g_element(
    svg_path: str,
    element_id: str | None = None,
    target_size: int | None = None,
    symbol: str | None = None,
) -> str:
    """
    Read an SVG file and return the inner ``<g>...</g>`` string.
    """
    tree = ET.parse(svg_path)
    root = tree.getroot()

    g_elements = [
        child
        for child in root
        if (child.tag.endswith("}g") or child.tag == "g")
    ]

    if len(g_elements) == 1:
        g_elem = g_elements[0]
    else:
        g_elem = ET.Element("g")
        for child in root:
            local_tag = child.tag.split("}", 1)[1] if "}" in child.tag else child.tag
            if local_tag in {"defs", "metadata", "namedview", "title", "script", "style"}:
                continue
            g_elem.append(child)

    # Auto-scale to target size
    if target_size is not None:
        canvas = _get_svg_canvas(root)
        if canvas is not None and canvas != (target_size, target_size):
            bbox = _get_content_bbox(svg_path)
            bw = bbox[2] - bbox[0]
            bh = bbox[3] - bbox[1]
            if bw > 0 and bh > 0:
                scale = min(target_size / bw, target_size / bh)
                cx = (bbox[0] + bbox[2]) / 2.0
                cy = (bbox[1] + bbox[3]) / 2.0
                tx = target_size / 2.0 - cx * scale
                ty = target_size / 2.0 - cy * scale
                wrapper = ET.Element("g", {
                    "transform": f"translate({tx:.2f},{ty:.2f}) "
                                 f"scale({scale:.6f})"
                })
                if element_id:
                    wrapper.set("id", element_id)
                    element_id = None
                wrapper.append(g_elem)
                g_elem = wrapper

    if element_id is not None:
        g_elem.set("id", element_id)

    _strip_ns(g_elem)

    if symbol:
        _prefix_def_refs(g_elem, symbol)

    return ET.tostring(g_elem, encoding="unicode")


@lru_cache(maxsize=16)
def _load_theme_cached(theme_name: str) -> dict:
    return _load_theme(theme_name)


@lru_cache(maxsize=16)
def _collect_theme_defs_cached(theme_name: str) -> str:
    return _collect_theme_defs(theme_name)


def _collect_theme_defs(theme_name: str) -> str:
    """Collect and deduplicate ``<defs>`` children from each SVG in *theme_name*.

    Returns concatenated gradient/filter elements (no wrapping ``<defs>``).
    """
    theme_files = PIECE_THEMES.get(theme_name, STANDARD_THEME_FILES)
    seen_ids: set[str] = set()
    defs_children: list[str] = []

    for symbol, file_path in theme_files.items():
        if os.path.isabs(file_path):
            svg_path = file_path
        else:
            svg_path = get_resource_path(
                os.path.join(PIECE_ASSETS_DIR, file_path)
            )

        try:
            tree = ET.parse(svg_path)
        except (FileNotFoundError, ET.ParseError):
            continue
        root = tree.getroot()

        for child in root:
            tag = child.tag
            local = tag.split("}", 1)[1] if "}" in tag else tag
            if local != "defs":
                continue
            for def_child in child:
                def_id = def_child.get("id")
                prefixed = f"{symbol}_{def_id}" if def_id else None
                if prefixed and prefixed in seen_ids:
                    continue
                if prefixed:
                    seen_ids.add(prefixed)
                    def_child.set("id", prefixed)
                _strip_ns(def_child)
                if prefixed:
                    _prefix_def_refs(def_child, symbol)
                defs_children.append(ET.tostring(def_child, encoding="unicode"))

    if not defs_children:
        return ""

    return "".join(defs_children) + "\n"


def _load_theme(theme_name: str) -> dict:
    """Return ``{piece_symbol: <g>...</g>}`` for *theme_name*.

    Args:
        theme_name: The theme name (a key of :data:`PIECE_THEMES`).

    Returns:
        Dict mapping piece symbol to the corresponding ``<g>`` string.
    """
    theme_files = PIECE_THEMES.get(theme_name, STANDARD_THEME_FILES)
    pieces: dict[str, str] = {}
    for symbol, file_path in theme_files.items():
        if os.path.isabs(file_path):
            svg_path = file_path
        else:
            svg_path = get_resource_path(
                os.path.join(PIECE_ASSETS_DIR, file_path)
            )
        pieces[symbol] = _extract_g_element(
            svg_path, element_id=_expected_id(symbol), target_size=45,
            symbol=symbol,
        )
    return pieces


def get_piece_defs(theme_name: str = "Standard") -> str:
    """Return SVG pieces for *theme_name* (gradient defs + 12 ``<g>`` elements).

    Falls back to Standard on failure, then to empty string.
    """
    try:
        pieces = _load_theme_cached(theme_name)
        defs_block = _collect_theme_defs_cached(theme_name)
        return defs_block + "\n".join(
            pieces[symbol] for symbol in STANDARD_THEME_FILES
        )
    except Exception as e:
        logger.error(f"Failed to load piece theme {theme_name!r}: {e}")
        if theme_name != "Standard":
            logger.info("Attempting fallback to 'Standard' piece theme.")
            try:
                pieces = _load_theme_cached("Standard")
                return "\n".join(
                    pieces[symbol] for symbol in STANDARD_THEME_FILES
                )
            except Exception as fallback_err:
                logger.error(
                    f"Failed to load fallback 'Standard' piece theme: {fallback_err}"
                )
        return ""


def get_piece_theme_names() -> list:
    return list(PIECE_THEMES.keys())


def get_current_theme_name() -> str:
    from ...utils.config import ConfigManager
    return ConfigManager().get("piece_theme", "Standard")


def clear_theme_cache() -> None:
    _load_theme_cached.cache_clear()
    _collect_theme_defs_cached.cache_clear()


scan_user_themes()

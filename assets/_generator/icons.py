"""
Custom move-evaluation and game-outcome SVGs for Chess Analyzer Pro.

All icons are original artwork released into the public domain (CC0).
The visual language is deliberately simple — a coloured rounded square
plus a glyph or letter — so the icon set cannot be confused with the
proprietary Chess.com badge designs this project used to ship.

Every helper below returns a complete, self-contained SVG string. The
high-level ``write_all()`` writes the file set expected by
``src/utils/resources.py`` and ``src/gui/board/board_widget.py``.

Run as a script to regenerate every icon in ``assets/images/``.
"""

from __future__ import annotations

import os
from typing import Iterable

# ---------------------------------------------------------------------------
# Visual design tokens
# ---------------------------------------------------------------------------

# 24x24 viewBox, 4-unit corner radius, 1.5-unit outline. Keeping every icon
# at the same scale and stroke width makes them visually consistent.
VB = 24
R = 4
STROKE = 1.5

# Foreground colour for every glyph and outline.
INK = "#1A1A1D"
# Default background tint (the "neutral" classification).
NEUTRAL_BG = "#7B7B85"

# Move-classification colours. The teal/red/yellow/green hues are
# the conventional chess-evaluation palette; the exact hex codes here
# are distinct from Chess.com's brand palette.
EVAL_COLOURS = {
    # name          : (background, glyph colour)
    "brilliant":    ("#1FB8A6", "#FFFFFF"),
    "great_find":   ("#3E8EDE", "#FFFFFF"),
    "best_v2":      ("#5BAE3F", "#FFFFFF"),
    "excellent":    ("#6FBE3F", "#FFFFFF"),
    "good":         ("#8DBE3F", "#FFFFFF"),
    "book":         ("#9A7B4B", "#FFFFFF"),
    "forced":       ("#6E6E78", "#FFFFFF"),
    "sharp":        ("#D64545", "#FFFFFF"),
    "alternative":  ("#9A9AA3", "#FFFFFF"),
    "inaccuracy":   ("#E5B53A", INK),
    "mistake":      ("#E68A2E", "#FFFFFF"),
    "blunder":      ("#D6443B", "#FFFFFF"),
    "missed_win":   ("#C24A8A", "#FFFFFF"),
    "threat":       ("#A04AC2", "#FFFFFF"),
    "correct":      ("#5BAE3F", "#FFFFFF"),
    "critical":     ("#D6443B", "#FFFFFF"),
    "incorrect":    ("#D6443B", "#FFFFFF"),
    "mate":         ("#111111", "#FFFFFF"),
}

# Outcome / game-state icons.
OUTCOME_COLOURS = {
    "checkmate_white": ("#111111", "#FFFFFF"),
    "checkmate_black": ("#F0F0F0", "#111111"),
    "draw_white":      ("#F0F0F0", "#111111"),
    "draw_black":      ("#111111", "#FFFFFF"),
    "resign_white":    ("#F0F0F0", "#111111"),
    "resign_black":    ("#111111", "#FFFFFF"),
    "winner":          ("#E5A22E", "#FFFFFF"),
    "fast_win":        ("#3E8EDE", "#FFFFFF"),
    "free_piece":      ("#1FB8A6", "#FFFFFF"),
    "take_back":       ("#9A9AA3", "#FFFFFF"),
    "unnamed_redo":    ("#9A9AA3", "#FFFFFF"),
    "unnamed_clock_white": ("#F0F0F0", "#111111"),
    "unnamed_clock_black": ("#111111", "#FFFFFF"),
    "unnamed_updown_arrow": ("#9A9AA3", "#FFFFFF"),
}


# ---------------------------------------------------------------------------
# SVG primitives
# ---------------------------------------------------------------------------

def _background(bg: str) -> str:
    """A filled rounded-square background."""
    return f'<rect x="1" y="1" width="{VB - 2}" height="{VB - 2}" rx="{R}" ry="{R}" fill="{bg}"/>'


def _ink_path(d: str, ink: str = INK, stroke: bool = False, sw: float = STROKE) -> str:
    extra = f' stroke="{ink}" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round" fill="none"' if stroke else f' fill="{ink}"'
    return f'<path d="{d}"{extra}/>'


# ---------------------------------------------------------------------------
# Glyphs (single letters / shapes) for the move-evaluation set
# ---------------------------------------------------------------------------

def _plus(ink: str) -> str:
    """A plus / tick shape for 'Good' style moves."""
    d = "M12 5v14M5 12h14"
    return _ink_path(d, ink=ink, stroke=True, sw=2.4)


def _double_plus(ink: str) -> str:
    """A double plus for 'Excellent'."""
    d = "M8.5 4.5v15M3.5 12h10 M15.5 4.5v15M10.5 12h10"
    return _ink_path(d, ink=ink, stroke=True, sw=2.0)


def _tick(ink: str) -> str:
    """A checkmark for 'Best' / 'Forced' style moves."""
    d = "M5 12.5l4 4 10-10"
    return _ink_path(d, ink=ink, stroke=True, sw=2.6)


def _cross(ink: str) -> str:
    """An X cross for 'Mistake' / 'Blunder' style moves."""
    d = "M6 6l12 12M18 6L6 18"
    return _ink_path(d, ink=ink, stroke=True, sw=2.6)


def _exclamation(ink: str) -> str:
    """An exclamation mark for 'Inaccuracy' / 'Missed Win'."""
    d = "M12 5v8"
    body = _ink_path(d, ink=ink, stroke=True, sw=2.6)
    dot = f'<circle cx="12" cy="17.5" r="1.6" fill="{ink}"/>'
    return body + dot


def _asterisk(ink: str) -> str:
    """A 6-arm sparkle for 'Brilliant' — the project's signature badge."""
    arms = (
        "M12 4v16",
        "M5.6 7.5l12.8 9",
        "M5.6 16.5l12.8-9",
    )
    return "".join(_ink_path(d, ink=ink, stroke=True, sw=2.0) for d in arms)


def _book(ink: str) -> str:
    """An open book glyph for 'Book' moves."""
    d = (
        "M3 6.5C3 6.5 5 5 12 5s9 1.5 9 1.5v12.5C21 18 19 19 12 19s-9-1-9-1Z "
        "M12 5v14"
    )
    return _ink_path(d, ink=ink, stroke=True, sw=1.6)


def _letter(ch: str, ink: str) -> str:
    """A bold capital letter, centred in the 24x24 viewBox."""
    return (
        f'<text x="12" y="17" text-anchor="middle" font-family="Verdana,Geneva,sans-serif" '
        f'font-weight="700" font-size="15" fill="{ink}">{ch}</text>'
    )


def _letter_M(ink: str) -> str:
    """Letter 'M' for 'Mistake'."""
    return _letter("M", ink)


def _letter_F(ink: str) -> str:
    """Letter 'F' for 'Free piece'."""
    return _letter("F", ink)


def _arrow_curve(ink: str) -> str:
    """A curved arrow for 'Alternative'."""
    d = "M5 7C9 5 15 5 19 9"
    body = _ink_path(d, ink=ink, stroke=True, sw=2.0)
    head = f'<path d="M16 6l3 3-3 3" fill="none" stroke="{ink}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    return body + head


def _dot(ink: str) -> str:
    """A single filled dot for 'Forced' style moves."""
    return f'<circle cx="12" cy="12" r="3" fill="{ink}"/>'


def _lightning(ink: str) -> str:
    """A lightning bolt for 'Sharp' / 'Critical'."""
    d = "M13 3L7 13h4l-2 8 8-11h-4l2-7z"
    return _ink_path(d, ink=ink)


def _arrow_up(ink: str) -> str:
    """An upward triangle for 'Missed Win'."""
    d = "M12 4l7 12H5z"
    return _ink_path(d, ink=ink)


def _flame(ink: str) -> str:
    """A flame-like shape for 'Threat'."""
    d = (
        "M12 3C13 6 16 7 16 11a4 4 0 0 1-8 0c0-2 1-3 2-4 0 1 1 2 2 2 0-2-1-4 0-6z"
    )
    return _ink_path(d, ink=ink)


def _undo(ink: str) -> str:
    """A counter-clockwise arrow for 'Take Back'."""
    d = "M9 4L4 9l5 5"
    body = _ink_path(d, ink=ink, stroke=True, sw=2.0)
    head = f'<path d="M4 9h9a5 5 0 1 1 0 10h-2" fill="none" stroke="{ink}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    return body + head


def _redo(ink: str) -> str:
    """A clockwise arrow for 'Redo'."""
    d = "M15 4l5 5-5 5"
    body = _ink_path(d, ink=ink, stroke=True, sw=2.0)
    head = f'<path d="M20 9H11a5 5 0 1 0 0 10h2" fill="none" stroke="{ink}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    return body + head


def _clock(ink: str) -> str:
    """A simple clock face for the clock-state icons."""
    parts = [
        f'<circle cx="12" cy="12" r="8" fill="none" stroke="{ink}" stroke-width="1.8"/>',
        f'<path d="M12 7v5l3.5 2" fill="none" stroke="{ink}" stroke-width="1.8" stroke-linecap="round"/>',
    ]
    return "".join(parts)


def _updown(ink: str) -> str:
    """An up-down arrow pair for 'unnamed_updown_arrow'."""
    parts = [
        f'<path d="M12 4v16" stroke="{ink}" stroke-width="1.8" stroke-linecap="round" fill="none"/>',
        f'<path d="M7 9l5-5 5 5" fill="none" stroke="{ink}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
        f'<path d="M7 15l5 5 5-5" fill="none" stroke="{ink}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    ]
    return "".join(parts)


def _pawn_silhouette(ink: str) -> str:
    """A generic chess pawn silhouette for mate/check outcomes."""
    d = (
        "M9 4a3 3 0 0 1 6 0c0 1.4-1 2.5-2 3 0 1 1 2 1 3.5 1 1 1 2 1 3 0 .8-.7 1.5-1.5 1.5h-3C9.7 15 9 14.3 9 13.5c0-1 0-2 1-3 .5-1.5 1-2.5 1-3.5-1-.5-2-1.6-2-3z "
        "M7 19c0-1 1-1.5 5-1.5s5 .5 5 1.5v1H7z"
    )
    return _ink_path(d, ink=ink)


def _knight_silhouette(ink: str) -> str:
    """A simple knight head silhouette for 'winner' / 'fast_win'."""
    d = (
        "M5 19c0-3 1-5 2-7 0-2 1-3 1-4 1-2 3-3 5-3 1 0 2 0 3 1l3-2-1 4 1 2c1 1 1 2 0 3l-1 2v3H5z"
    )
    return _ink_path(d, ink=ink)


def _handshake_silhouette(ink: str) -> str:
    """Two clasping hands for 'draw'."""
    d = (
        "M2 13l3-3 3 1 3 1 2-1 3 1 2-1 3 1 1 1-1 3-3 1-3-1-2 1-3-1-2 1-3-1-2-2z"
    )
    return _ink_path(d, ink=ink)


def _flag_silhouette(ink: str) -> str:
    """A surrender flag for 'resign'."""
    parts = [
        f'<path d="M6 4v16" stroke="{ink}" stroke-width="1.8" stroke-linecap="round" fill="none"/>',
        f'<path d="M6 5h11l-2 3 2 3H6z" fill="{ink}"/>',
    ]
    return "".join(parts)


def _crown(ink: str) -> str:
    """A simple crown for 'winner'."""
    d = "M4 9l3 6h10l3-6-4 3-4-5-4 5z"
    return _ink_path(d, ink=ink)


# ---------------------------------------------------------------------------
# SVG assembly
# ---------------------------------------------------------------------------

def _wrap_svg(inner: str, title: str) -> str:
    """Wrap icon bodies in a full SVG document with a title (a11y)."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" '
        f'viewBox="0 0 {VB} {VB}" role="img" aria-label="{title}">'
        f'<title>{title}</title>'
        f'{inner}'
        f'</svg>'
    )


# Map: filename -> (background-fg, glyph-builder, title)
EVAL_GLYPHS: dict[str, tuple[tuple[str, str], callable, str]] = {
    "brilliant.svg":    (EVAL_COLOURS["brilliant"],   _asterisk,    "Brilliant move"),
    "great_find.svg":   (EVAL_COLOURS["great_find"],  _double_plus, "Great find"),
    "best_v2.svg":      (EVAL_COLOURS["best_v2"],     _tick,        "Best move"),
    "excellent.svg":    (EVAL_COLOURS["excellent"],   _double_plus, "Excellent move"),
    "good.svg":         (EVAL_COLOURS["good"],        _plus,        "Good move"),
    "book.svg":         (EVAL_COLOURS["book"],        _book,        "Book move"),
    "forced.svg":       (EVAL_COLOURS["forced"],      _dot,         "Forced move"),
    "sharp.svg":        (EVAL_COLOURS["sharp"],       _lightning,   "Sharp move"),
    "alternative.svg":  (EVAL_COLOURS["alternative"], _arrow_curve, "Alternative move"),
    "inaccuracy.svg":   (EVAL_COLOURS["inaccuracy"],  _exclamation, "Inaccuracy"),
    "mistake.svg":      (EVAL_COLOURS["mistake"],     _letter_M,    "Mistake"),
    "blunder.svg":      (EVAL_COLOURS["blunder"],     _cross,       "Blunder"),
    "missed_win.svg":   (EVAL_COLOURS["missed_win"],  _arrow_up,    "Missed win"),
    "threat.svg":       (EVAL_COLOURS["threat"],      _flame,       "Threat"),
    "correct.svg":      (EVAL_COLOURS["correct"],     _tick,        "Correct move"),
    "critical.svg":     (EVAL_COLOURS["critical"],    _lightning,   "Critical moment"),
    "incorrect.svg":    (EVAL_COLOURS["incorrect"],   _cross,       "Incorrect move"),
    "mate.svg":         (EVAL_COLOURS["mate"],        _letter_M,    "Mate"),
}


OUTCOME_GLYPHS: dict[str, tuple[tuple[str, str], callable, str]] = {
    "checkmate_white.svg":  (OUTCOME_COLOURS["checkmate_white"],  _pawn_silhouette, "Checkmate — white wins"),
    "checkmate_black.svg":  (OUTCOME_COLOURS["checkmate_black"],  _pawn_silhouette, "Checkmate — black wins"),
    "draw_white.svg":       (OUTCOME_COLOURS["draw_white"],       _handshake_silhouette, "Draw"),
    "draw_black.svg":       (OUTCOME_COLOURS["draw_black"],       _handshake_silhouette, "Draw"),
    "resign_white.svg":     (OUTCOME_COLOURS["resign_white"],     _flag_silhouette, "White resigned"),
    "resign_black.svg":     (OUTCOME_COLOURS["resign_black"],     _flag_silhouette, "Black resigned"),
    "winner.svg":           (OUTCOME_COLOURS["winner"],           _crown, "Winner"),
    "fast_win.svg":         (OUTCOME_COLOURS["fast_win"],         _knight_silhouette, "Fast win"),
    "free_piece.svg":       (OUTCOME_COLOURS["free_piece"],       _letter_F, "Free piece"),
    "take_back.svg":        (OUTCOME_COLOURS["take_back"],        _undo, "Take back"),
    "unnamed_redo.svg":     (OUTCOME_COLOURS["unnamed_redo"],    _redo, "Redo"),
    "unnamed_clock_white.svg": (OUTCOME_COLOURS["unnamed_clock_white"], _clock, "Clock"),
    "unnamed_clock_black.svg": (OUTCOME_COLOURS["unnamed_clock_black"], _clock, "Clock"),
    "unnamed_updown_arrow.svg": (OUTCOME_COLOURS["unnamed_updown_arrow"], _updown, "Move order"),
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_icon(filename: str) -> str:
    """Build the SVG content for a single icon filename."""
    if filename in EVAL_GLYPHS:
        (bg, ink), builder, title = EVAL_GLYPHS[filename]
    elif filename in OUTCOME_GLYPHS:
        (bg, ink), builder, title = OUTCOME_GLYPHS[filename]
    else:
        raise KeyError(f"Unknown icon: {filename}")
    return _wrap_svg(_background(bg) + builder(ink), title)


def iter_icon_filenames() -> Iterable[str]:
    """Every file the build step should write."""
    return list(EVAL_GLYPHS) + list(OUTCOME_GLYPHS)


def write_all(target_dir: str) -> int:
    """Write every icon to *target_dir*. Returns the number written."""
    os.makedirs(target_dir, exist_ok=True)
    written = 0
    for name in iter_icon_filenames():
        with open(os.path.join(target_dir, name), "w", encoding="utf-8") as fh:
            fh.write(build_icon(name))
        written += 1
    return written


if __name__ == "__main__":
    # The script is usually run from the repo root.
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.normpath(os.path.join(here, "..", "images"))
    n = write_all(out)
    print(f"Wrote {n} icons to {out}")

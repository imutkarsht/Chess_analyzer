"""
Compact, factual dossier for the full-game AI summary.

The model writes prose, so every chess fact it may state has to live in this
text first — the same rule as ``tactics.insight`` for a single move, scaled to a
whole game. Two properties matter for accuracy:

* ``summary`` stores evaluations from *each side's* own point of view, while the
  rest of the app is White-perspective. Everything is normalised here, once, so
  the model never has to guess whose sign it is reading.
* Moments are de-duplicated and capped, so a long game cannot bury the decisive
  mistakes under hundreds of equally-worded lines.
"""

from __future__ import annotations

from typing import Any

from src.backend.storage.models import GameAnalysis, GameMetadata

_CLASS_ORDER = (
    "Brilliant",
    "Great",
    "Best",
    "Excellent",
    "Good",
    "Book",
    "Inaccuracy",
    "Mistake",
    "Miss",
    "Blunder",
)
_PHASES = ("opening", "middlegame", "endgame")
_MAX_KEY_MOMENTS = 6
_MAX_BRILLIANCIES = 3

# Stockfish mate scores arrive as ±(100000 − distance) centipawns. Passed through
# raw they read as "±999.99 pawns", which the model then repeats as a real
# material swing, so anything at or beyond a full queen-and-more is reported as
# mate instead.
_MATE_CP_THRESHOLD = 10_000


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _is_mate(cp: int | None) -> bool:
    return cp is not None and abs(cp) >= _MATE_CP_THRESHOLD


def _fmt_cp(cp: int | None) -> str:
    if cp is None:
        return "unknown"
    if _is_mate(cp):
        return "mate for White" if cp > 0 else "mate for Black"
    return f"{cp / 100:+.2f}"


def _eval_for_white(cp: int | None, side: str) -> int | None:
    """``summary`` evals are stored from the side's own view; flip them back."""
    if cp is None:
        return None
    return cp if side == "white" else -cp


def _move_ref(detail: dict[str, Any], side: str) -> str:
    """Chess notation reference for a drill-down detail, e.g. ``14.c3``."""
    san = detail.get("san") or "?"
    move_number = detail.get("move_number")
    if move_number is None:
        return san
    return f"{move_number}{'.' if side == 'white' else '...'}{san}"


def _player(name: str | None, elo: str | None) -> str:
    label = name or "?"
    return f"{label} ({elo})" if elo else label


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def _header_lines(game: GameAnalysis, user_side: str | None) -> list[str]:
    meta: GameMetadata = game.metadata
    ply_count = len(game.moves)

    lines = [
        f"Players: {_player(meta.white, meta.white_elo)} (White) vs "
        f"{_player(meta.black, meta.black_elo)} (Black)",
        f"Result: {meta.result}",
    ]

    details: list[str] = []
    if meta.speed_category:
        details.append(meta.speed_category)
    if ply_count:
        details.append(f"{ply_count} plies ({ply_count // 2 + ply_count % 2} moves)")
    if meta.opening:
        details.append(meta.opening + (f" ({meta.eco})" if meta.eco else ""))
    if meta.termination_description:
        details.append(meta.termination_description)
    if details:
        lines.append("Details: " + " | ".join(details))

    if meta.starting_fen:
        chess960 = "yes" if meta.chess960 else "no"
        lines.append(f"Non-standard start (Chess960: {chess960}): {meta.starting_fen}")

    if user_side in ("white", "black"):
        name = meta.white if user_side == "white" else meta.black
        lines.append(f"The report is for {name}, who played {user_side}: address them as 'you'.")
    return lines


def _phase_line(tactics: dict[str, Any]) -> list[str]:
    accuracies = tactics.get("phase_accuracies") or {}
    counts = tactics.get("phase_move_counts") or {}
    blunders = tactics.get("phase_blunders") or {}

    bits = []
    for phase in _PHASES:
        accuracy, count = accuracies.get(phase), counts.get(phase, 0)
        if accuracy is None or not count:
            continue
        bits.append(
            f"{phase} {accuracy:.1f}% ({count} moves, {blunders.get(phase, 0)} blunder"
            f"{'' if blunders.get(phase, 0) == 1 else 's'})"
        )
    return ["Phase accuracy: " + "; ".join(bits) + "."] if bits else []


def _advantage_line(tactics: dict[str, Any], side: str) -> list[str]:
    advantage = tactics.get("advantage_metrics") or {}
    bits: list[str] = []

    if advantage.get("had_winning_advantage"):
        peak = _eval_for_white(advantage.get("peak_eval_cp"), side)
        bits.append(f"reached a winning position (peak {_fmt_cp(peak)})")
        bits.append(
            "converted it" if advantage.get("converted_advantage") else "did not convert it"
        )
    if advantage.get("had_losing_position"):
        lowest = _eval_for_white(advantage.get("lowest_eval_cp"), side)
        bits.append(f"was lost at its worst ({_fmt_cp(lowest)})")
        bits.append("fought back" if advantage.get("comeback_drawn_or_won") else "never recovered")
    if advantage.get("squandered_draws") and not advantage.get("had_winning_advantage"):
        bits.append("let a drawn position slip")

    return ["Advantage: " + "; ".join(bits) + "."] if bits else []


def _hanging_line(tactics: dict[str, Any]) -> list[str]:
    metrics = tactics.get("hanging_metrics") or {}
    total = metrics.get("total_hung") or 0
    if not total:
        return []

    pieces = ", ".join(
        f"{piece} {count}" for piece, count in (metrics.get("by_piece") or {}).items() if count
    )
    bits = [f"hung {total} piece(s)" + (f" ({pieces})" if pieces else "")]
    in_blunders = metrics.get("hanging_blunders") or 0
    if in_blunders:
        bits.append(f"{in_blunders} of them while blundering")
    won = metrics.get("opponent_hanging_captured") or 0
    if won:
        bits.append(f"won {won} free piece(s) from the opponent")
    missed = metrics.get("opponent_hanging_missed") or 0
    if missed:
        bits.append(f"missed {missed} free piece(s)")
    return ["Hanging pieces: " + "; ".join(bits) + "."]


def _theme_line(tactics: dict[str, Any]) -> list[str]:
    themes = tactics.get("tactical_themes") or {}
    hits = [f"{theme.replace('_', ' ')} {count}" for theme, count in themes.items() if count]
    return ["Tactical motifs: " + ", ".join(hits) + "."] if hits else []


def _brilliancy_line(tactics: dict[str, Any], side: str) -> list[str]:
    brilliancies = tactics.get("brilliancies") or []
    if not brilliancies:
        return []
    bits = [
        f"{_move_ref(item, side)} ({item.get('classification') or 'Brilliant'})"
        for item in brilliancies[:_MAX_BRILLIANCIES]
    ]
    return ["Brilliancies: " + ", ".join(bits) + "."]


def _side_lines(side: str, summary: dict[str, Any], meta: GameMetadata) -> list[str]:
    """Render one player's block; both sides go through the same path."""
    data = summary.get(side) or {}
    player = (meta.white if side == "white" else meta.black) or side.title()
    lines = [f"\n{side.upper()} — {player}"]

    headline = []
    accuracy = data.get("accuracy")
    if accuracy:
        headline.append(f"accuracy {accuracy:.1f}%")
    acpl = data.get("acpl")
    if acpl:
        headline.append(f"average centipawn loss {acpl:.0f}")
    analysed = data.get("move_count")
    if analysed:
        headline.append(f"{analysed} moves analysed")
    if headline:
        lines.append(", ".join(headline) + ".")

    quality = [
        f"{classification} {data[classification]}"
        for classification in _CLASS_ORDER
        if data.get(classification)
    ]
    if quality:
        lines.append("Move quality: " + ", ".join(quality) + ".")

    tactics = data.get("tactics") or {}
    lines.extend(_phase_line(tactics))
    lines.extend(_advantage_line(tactics, side))
    lines.extend(_hanging_line(tactics))
    lines.extend(_theme_line(tactics))
    lines.extend(_brilliancy_line(tactics, side))
    return lines


def _moment_line(detail: dict[str, Any], side: str) -> str:
    before = _eval_for_white(detail.get("eval_before_cp"), side)
    after = _eval_for_white(detail.get("eval_after_cp"), side)
    label = detail.get("classification") or "error"
    drop = detail.get("eval_drop")
    # A "999.83 pawns lost" line is noise once one side has mate.
    swing = (
        f", {drop / 100:.2f} pawns lost"
        if drop and not (_is_mate(before) or _is_mate(after))
        else ""
    )
    return (
        f"{_move_ref(detail, side)} ({side}, {label}): "
        f"{_fmt_cp(before)} -> {_fmt_cp(after)}{swing}."
    )


def _key_moment_lines(summary: dict[str, Any]) -> list[str]:
    moments: list[tuple[int, int, str]] = []
    for side in ("white", "black"):
        tactics = (summary.get(side) or {}).get("tactics") or {}
        for detail in tactics.get("blunders_details") or []:
            moments.append(
                (detail.get("ply") or 0, detail.get("eval_drop") or 0, _moment_line(detail, side))
            )
    if not moments:
        return []

    # Keep the biggest swings — a game can have dozens of small errors, and the
    # summary has room for the ones that decided it. Then restore chronology so
    # the model can tell the story in order.
    biggest = sorted(moments, key=lambda moment: moment[1], reverse=True)[:_MAX_KEY_MOMENTS]
    return [line for _, _, line in sorted(biggest, key=lambda moment: moment[0])]


def _turning_point_lines(summary: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for side in ("white", "black"):
        tactics = (summary.get(side) or {}).get("tactics") or {}
        collapse = tactics.get("lead_collapse_move")
        if collapse:
            lines.append(
                f"{side.title()}'s lead collapsed at {_move_ref(collapse, side)} "
                f"({collapse.get('classification') or 'error'})."
            )
        comeback = tactics.get("comeback_turn_move")
        if comeback:
            lines.append(
                f"{side.title()}'s comeback started at {_move_ref(comeback, side)} "
                f"({comeback.get('classification') or 'move'})."
            )
    return lines


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def build_game_report(game: GameAnalysis, user_side: str | None = None) -> str:
    """
    Render ``game`` as a compact fact sheet for the summary prompt.

    Returns an empty string when the game has no analysis yet, which lets the
    caller fall back to the PGN alone instead of sending an empty dossier.
    """
    summary = game.summary or {}
    if not summary.get("white") and not summary.get("black"):
        return ""

    lines = ["GAME FACTS (deterministic engine analysis; treat as ground truth)"]
    lines.extend(_header_lines(game, user_side))
    for side in ("white", "black"):
        lines.extend(_side_lines(side, summary, game.metadata))

    moments = _key_moment_lines(summary)
    if moments:
        lines.append("\nKEY MOMENTS (chronological; all evaluations are from White's perspective)")
        lines.extend(moments)

    turning_points = _turning_point_lines(summary)
    if turning_points:
        lines.append("\nTURNING POINTS")
        lines.extend(turning_points)

    return "\n".join(lines)

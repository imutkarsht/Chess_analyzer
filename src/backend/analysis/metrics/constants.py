"""
Constants for metrics aggregation, performance tracking, and coach reporting.
"""

from __future__ import annotations

PHASES: tuple[str, ...] = ("opening", "middlegame", "endgame")
COLORS: tuple[str, ...] = ("white", "black")
PIECE_NAMES: tuple[str, ...] = ("pawn", "knight", "bishop", "rook", "queen")

QUALITY_NAMES: tuple[str, ...] = (
    "Brilliant",
    "Great",
    "Best",
    "Excellent",
    "Good",
    "Inaccuracy",
    "Mistake",
    "Blunder",
    "Miss",
    "Book",
)

QUALITY_PACE_KEYS: tuple[str, ...] = ("best", "blunder", "other")

MOTIF_NAMES: tuple[str, ...] = (
    "fork",
    "pin",
    "skewer",
    "discovered_attack",
    "sacrifice",
    "back_rank",
)

ADVANTAGE_KEYS: tuple[str, ...] = (
    "had_winning_advantage",
    "converted_advantage",
    "choked_advantage",
    "thrown_losses",
    "squandered_draws",
    "had_losing_position",
    "comeback_drawn_or_won",
    "comeback_wins",
    "comeback_draws",
)

# (advantage_key, move_key, fallback_san, fallback_classification)
ADVANTAGE_DRILLS: tuple[tuple[str, str, str, str], ...] = (
    ("thrown_losses", "lead_collapse_move", "Lost Lead", "Lost Lead"),
    ("squandered_draws", "lead_collapse_move", "Drawn Lead", "Drawn Lead"),
    ("comeback_wins", "comeback_turn_move", "Comeback", "Comeback Win"),
    ("comeback_draws", "comeback_turn_move", "Comeback", "Comeback Draw"),
)

DRAW_MODE_TO_BUCKET: dict[str, str] = {
    "threefold_repetition": "3-Fold Repetition",
    "repetition": "3-Fold Repetition",
    "agreed_draw": "Agreement",
    "agreement": "Agreement",
    "stalemate": "Stalemate",
    "timeout_insufficient": "Insufficient vs Timeout",
    "insufficient_material": "Insufficient Material",
    "fifty_moves": "50-Move Rule",
    "50_moves": "50-Move Rule",
}

DRAW_BUCKETS: tuple[str, ...] = (
    "3-Fold Repetition",
    "Agreement",
    "Stalemate",
    "Insufficient vs Timeout",
    "Insufficient Material",
    "50-Move Rule",
)

TERM_TYPES: tuple[str, ...] = ("Checkmate", "Resignation", "Time", "Abandon", "Draw")
NON_DRAW_TERM_TYPES: tuple[str, ...] = ("Checkmate", "Resignation", "Time", "Abandon")

VALID_DATE_FILTERS: set[str] = {
    "All Time",
    "Last 24 Hours",
    "Last 7 Days",
    "Last 30 Days",
    "Last 90 Days",
    "This Year",
}


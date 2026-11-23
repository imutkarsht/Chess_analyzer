# SPDX-License-Identifier: GPL-3.0-only
"""Pure chess position helpers shared across backend and GUI layers."""

from __future__ import annotations

import chess


def position_key(fen: str) -> str:
    """Strip halfmove clock and fullmove number, keeping the position key."""
    return " ".join(fen.split()[:4])


def canonical_fen(fen: str, chess960: bool = False) -> str:
    """Normalize a FEN so equivalent positions compare by the same key."""
    return chess.Board(fen, chess960=chess960).fen()


def requires_chess960(fen: str | None) -> bool:
    """True when a FEN uses file-letter castling rights (Chess960 notation)."""
    if not fen:
        return False
    parts = fen.split()
    if len(parts) < 3:
        return False
    return any(piece not in "KQkq-" for piece in parts[2])


def is_chess960_variant(variant: str | None) -> bool:
    """True for the common variant names used by Chess960/Fischer Random."""
    value = (variant or "").casefold()
    return any(token in value for token in ("960", "fischer", "frc", "random"))


def is_chess960_metadata(metadata: object) -> bool:
    """True when a game metadata record is flagged as Chess960."""
    return bool(getattr(metadata, "chess960", False))

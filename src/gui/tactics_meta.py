"""
Display metadata for tactical motifs.

One source of truth for the motif label, icon, tooltip and colour attribute,
shared by the metrics card and the per-game Tactics tab.

Zero business logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.gui.theme.typography import TextTone


@dataclass(frozen=True)
class MotifMeta:
    """Presentation metadata for one motif."""

    label: str
    icon: str
    description: str
    color_attr: str


MOTIF_META: dict[str, MotifMeta] = {
    "hanging_piece": MotifMeta(
        "Hanging Piece",
        "exclamation-triangle",
        "An undefended or insufficiently defended piece that can be captured",
        "COLOR_BLUNDER",
    ),
    "fork": MotifMeta(
        "Fork",
        "code-branch",
        "Double attack against two enemy targets simultaneously",
        "COLOR_BEST",
    ),
    "pin": MotifMeta(
        "Pin",
        "thumbtack",
        "Immobilizing an enemy piece against their King or high-value piece",
        "COLOR_BOOK",
    ),
    "skewer": MotifMeta(
        "Skewer",
        "arrows-alt-v",
        "Attack through a higher-value piece to win material behind it",
        "COLOR_GREAT",
    ),
    "discovered_attack": MotifMeta(
        "Discovered Attack",
        "eye",
        "Moving one piece to unmask a deadly line of attack from another",
        "COLOR_GOOD",
    ),
    "discovered_check": MotifMeta(
        "Discovered Check",
        "bullseye",
        "Moving a piece to reveal a check from a hidden attacker",
        "COLOR_BEST",
    ),
    "double_check": MotifMeta(
        "Double Check",
        "crosshairs",
        "Two pieces give check at once, forcing the King to move",
        "COLOR_BEST",
    ),
    "removal_of_defender": MotifMeta(
        "Removal of Defender",
        "user-slash",
        "Capturing a defender so the piece it guarded becomes loose",
        "COLOR_GREAT",
    ),
    "trapped_piece": MotifMeta(
        "Trapped Piece",
        "lock",
        "A piece with no safe escape that is about to be captured",
        "COLOR_ACCENT",
    ),
    "sacrifice": MotifMeta(
        "Sacrifice",
        "gem",
        "Deliberate material investment for a decisive return",
        "COLOR_ACCENT",
    ),
    "promotion": MotifMeta(
        "Promotion",
        "arrow-up",
        "Promoting a pawn to a Queen or another piece",
        "COLOR_GOOD",
    ),
    "back_rank_mate": MotifMeta(
        "Back-Rank Mate",
        "chess-rook",
        "Mating the trapped enemy King along their baseline",
        "COLOR_TEXT_SECONDARY",
    ),
    "smothered_mate": MotifMeta(
        "Smothered Mate",
        "chess-knight",
        "A Knight mates a King surrounded by its own pieces",
        "COLOR_BOOK",
    ),
    "morphy_mate": MotifMeta(
        "Morphy's Mate",
        "chess-bishop",
        "A Bishop mates while a Rook confines the King",
        "COLOR_TEXT_SECONDARY",
    ),
    "opera_mate": MotifMeta(
        "Opera Mate",
        "chess-rook",
        "A Rook mates while a Bishop defends it",
        "COLOR_TEXT_SECONDARY",
    ),
    "boden_mate": MotifMeta(
        "Boden's Mate",
        "chess-bishop",
        "Two Bishops mate on criss-crossing diagonals",
        "COLOR_TEXT_SECONDARY",
    ),
}

# Hanging pieces have their own piece-safety card and are not tactical patterns.
TACTICAL_MOTIF_KEYS: tuple[str, ...] = tuple(
    key for key in MOTIF_META if key != "hanging_piece"
)

_DEFAULT = MotifMeta(
    "Tactic",
    "chess",
    "Tactical motif",
    "COLOR_ACCENT",
)


def motif_meta(motif: str) -> MotifMeta:
    """Metadata for ``motif`` with a safe fallback."""
    return MOTIF_META.get(motif, _DEFAULT)


def classification_tone(classification: str) -> TextTone:
    """Semantic text tone for a move classification."""
    try:
        return TextTone(classification.lower())
    except ValueError:
        return TextTone.PRIMARY


__all__ = [
    "MOTIF_META",
    "TACTICAL_MOTIF_KEYS",
    "MotifMeta",
    "classification_tone",
    "motif_meta",
]

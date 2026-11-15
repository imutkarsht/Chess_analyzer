"""
The single tactical-fact model shared by detection, validation and stats.

A fact always carries the evidence that produced it, the side it belongs to and
the confidence assigned by validation. Headline statistics consume confirmed
facts only; probable facts remain available in drill-down data.

Zero Qt dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from src.backend.analysis.tactics.constants import Confidence


@dataclass(frozen=True)
class TacticFact:
    """One validated or probable tactical event."""

    motif: str
    role: str
    side: str  # "white" | "black"
    confidence: str = Confidence.PROBABLE.value
    ply: int | None = None
    move_san: str | None = None
    move_uci: str | None = None
    origin_square: str | None = None
    target_square: str | None = None
    target_piece: str | None = None
    targets: tuple[str, ...] = field(default_factory=tuple)
    evidence: str = ""
    line: tuple[str, ...] = field(default_factory=tuple)
    material_gain_cp: int = 0
    mate_in: int | None = None

    @property
    def is_confirmed(self) -> bool:
        return self.confidence == Confidence.CONFIRMED.value

    def with_confidence(self, confidence: str, evidence: str = "") -> TacticFact:
        """Return a copy with updated confidence/evidence."""
        return replace(self, confidence=confidence, evidence=evidence or self.evidence)


def merge_same_motif_facts(facts: list[TacticFact]) -> list[TacticFact]:
    """
    Collapse multiple alignments of the same motif on one move into one fact.

    A queen can pin two pieces at once; that is one tactical occurrence, not
    two, and the drill-down should show it once.
    """
    merged: dict[str, TacticFact] = {}
    for fact in facts:
        existing = merged.get(fact.motif)
        if existing is None:
            merged[fact.motif] = fact
            continue

        targets = tuple(dict.fromkeys((*existing.targets, *fact.targets)))
        evidence = existing.evidence
        if fact.evidence and fact.evidence not in evidence:
            evidence = f"{evidence}; {fact.evidence}" if evidence else fact.evidence

        merged[fact.motif] = replace(
            existing,
            targets=targets,
            evidence=evidence,
            line=existing.line or fact.line,
            material_gain_cp=max(existing.material_gain_cp, fact.material_gain_cp),
            mate_in=existing.mate_in if existing.mate_in is not None else fact.mate_in,
        )

    return list(merged.values())


def fact_to_dict(fact: TacticFact) -> dict[str, Any]:
    """Serialize a fact for JSON summaries and drill-down data."""
    return {
        "motif": fact.motif,
        "role": fact.role,
        "side": fact.side,
        "confidence": fact.confidence,
        "ply": fact.ply,
        "san": fact.move_san,
        "uci": fact.move_uci,
        "origin_square": fact.origin_square,
        "target_square": fact.target_square,
        "target_piece": fact.target_piece,
        "targets": list(fact.targets),
        "evidence": fact.evidence,
        "line": list(fact.line),
        "material_gain_cp": fact.material_gain_cp,
        "mate_in": fact.mate_in,
    }


__all__ = ["TacticFact", "fact_to_dict", "merge_same_motif_facts"]

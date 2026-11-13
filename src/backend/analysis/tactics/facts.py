"""
The single tactical-fact model shared by detection, validation and stats.

A fact always carries the evidence that produced it, the side it belongs to and
the confidence assigned by validation. Headline statistics consume confirmed
facts only; probable facts remain available in drill-down data.

Zero Qt dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.backend.analysis.tactics.constants import Confidence, TacticRole


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
        return TacticFact(
            motif=self.motif,
            role=self.role,
            side=self.side,
            confidence=confidence,
            ply=self.ply,
            move_san=self.move_san,
            move_uci=self.move_uci,
            origin_square=self.origin_square,
            target_square=self.target_square,
            target_piece=self.target_piece,
            targets=self.targets,
            evidence=evidence or self.evidence,
            line=self.line,
            material_gain_cp=self.material_gain_cp,
            mate_in=self.mate_in,
        )


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


def role_count(roles: dict[str, dict[str, int]], motif: str, role: TacticRole) -> int:
    """Small helper used by accumulators and tests."""
    return roles.get(motif, {}).get(role.value, 0)


__all__ = ["TacticFact", "fact_to_dict", "role_count"]

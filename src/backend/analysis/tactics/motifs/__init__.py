"""
Tactical motif detection package.

The public API is intentionally small: ``detect_candidates`` returns structured
facts and ``detect_tactical_motifs`` keeps the historical motif-name façade.
Detector implementations are split by family under this package.

Zero Qt dependencies.
"""

from __future__ import annotations

from src.backend.analysis.tactics.motifs.context import MotifCtx
from src.backend.analysis.tactics.motifs.detection import (
    detect_candidates,
    detect_tactical_motifs,
)

__all__ = ["MotifCtx", "detect_candidates", "detect_tactical_motifs"]

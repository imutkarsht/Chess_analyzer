from dataclasses import dataclass
from typing import Optional


@dataclass
class ClassificationContext:
    san: str
    uci: str
    best_move: Optional[str] = None
    eval_before_cp: Optional[float] = None
    eval_before_mate: Optional[int] = None
    eval_after_cp: Optional[float] = None
    eval_after_mate: Optional[int] = None
    win_chance_before: float = 0.5
    win_chance_after: float = 0.5
    classification: Optional[str] = None
    explanation: Optional[str] = None

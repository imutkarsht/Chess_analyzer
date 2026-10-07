from dataclasses import dataclass


@dataclass
class ClassificationContext:
    san: str
    uci: str
    best_move: str | None = None
    eval_before_cp: float | None = None
    eval_before_mate: int | None = None
    eval_after_cp: float | None = None
    eval_after_mate: int | None = None
    win_chance_before: float = 0.5
    win_chance_after: float = 0.5
    classification: str | None = None
    explanation: str | None = None

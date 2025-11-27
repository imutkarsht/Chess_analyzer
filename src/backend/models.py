from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import chess

@dataclass
class MoveAnalysis:
    move_number: int
    ply: int
    san: str
    uci: str
    fen_before: str
    eval_before_cp: Optional[int] = None
    eval_before_mate: Optional[int] = None
    best_move: Optional[str] = None
    best_eval_cp: Optional[int] = None
    best_eval_mate: Optional[int] = None
    pv: List[str] = field(default_factory=list)
    eval_after_cp: Optional[int] = None
    eval_after_mate: Optional[int] = None
    win_chance_before: float = 0.5
    win_chance_after: float = 0.5
    classification: str = "Book" # Brilliant, Best, Excellent, Good, Inaccuracy, Mistake, Blunder, Miss, Book
    explanation: str = ""

@dataclass
class GameMetadata:
    white: str = "?"
    black: str = "?"
    event: str = "?"
    date: str = "?"
    result: str = "*"
    headers: Dict[str, str] = field(default_factory=dict)

@dataclass
class GameAnalysis:
    game_id: str
    metadata: GameMetadata
    moves: List[MoveAnalysis] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

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
    classification: str = ""  # Set by analyser: Brilliant, Best, Excellent, Good, Inaccuracy, Mistake, Blunder, Miss, Book; empty = unanalysed
    explanation: str = ""
    multi_pvs: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    # Clock information parsed from PGN [%clk] / [%timestamp] comments.
    # time_left   = remaining clock for the side that played this move, in seconds
    # time_spent  = seconds the side spent thinking on this move (None if unknown)
    # raw_clk     = original "0:09:56.1" string for display, if present
    time_left: Optional[float] = None
    time_spent: Optional[float] = None
    raw_clk: Optional[str] = None
    # Opening book fields
    is_book_move: bool = False
    book_move_count: int = 0
    book_exit_move: bool = False
    eco: str = ""
    opening_name: str = ""
    candidate_continuations: List[str] = field(default_factory=list)

@dataclass
class GameMetadata:
    white: str = "?"
    black: str = "?"
    event: str = "?"
    date: str = "?"
    result: str = "*"
    headers: Dict[str, str] = field(default_factory=dict)
    starting_fen: Optional[str] = None
    white_elo: Optional[str] = None
    black_elo: Optional[str] = None
    time_control: Optional[str] = None
    eco: Optional[str] = None
    termination: Optional[str] = None
    opening: Optional[str] = None
    source: str = "file" # file, chesscom, lichess
    chess960: bool = False

@dataclass
class GameAnalysis:
    game_id: str
    metadata: GameMetadata
    moves: List[MoveAnalysis] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    ai_summary: Optional[str] = None
    pgn_content: Optional[str] = None

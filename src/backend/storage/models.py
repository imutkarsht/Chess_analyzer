from dataclasses import dataclass, field
from typing import Any


@dataclass
class MoveAnalysis:
    move_number: int
    ply: int
    san: str
    uci: str
    fen_before: str
    eval_before_cp: int | None = None
    eval_before_mate: int | None = None
    best_move: str | None = None
    best_eval_cp: int | None = None
    best_eval_mate: int | None = None
    pv: list[str] = field(default_factory=list)
    eval_after_cp: int | None = None
    eval_after_mate: int | None = None
    win_chance_before: float = 0.5
    win_chance_after: float = 0.5
    classification: str = ""  # Set by analyser: Brilliant, Best, Excellent, Good, Inaccuracy, Mistake, Blunder, Miss, Book; empty = unanalysed
    explanation: str = ""
    multi_pvs: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    # Clock information parsed from PGN [%clk] / [%timestamp] comments.
    # time_left   = remaining clock for the side that played this move, in seconds
    # time_spent  = seconds the side spent thinking on this move (None if unknown)
    # raw_clk     = original "0:09:56.1" string for display, if present
    time_left: float | None = None
    time_spent: float | None = None
    raw_clk: str | None = None
    # Opening book fields
    is_book_move: bool = False
    book_move_count: int = 0
    book_exit_move: bool = False
    eco: str = ""
    opening_name: str = ""
    candidate_continuations: list[str] = field(default_factory=list)


@dataclass
class GameMetadata:
    white: str = "?"
    black: str = "?"
    event: str = "?"
    date: str = "?"
    result: str = "*"
    headers: dict[str, str] = field(default_factory=dict)
    starting_fen: str | None = None
    white_elo: str | None = None
    black_elo: str | None = None
    time_control: str | None = None
    eco: str | None = None
    termination: str | None = None
    termination_mode: str | None = None
    termination_description: str | None = None
    speed_category: str | None = None
    opening: str | None = None
    source: str = "file"  # file, chesscom, lichess
    chess960: bool = False


@dataclass
class GameAnalysis:
    game_id: str
    metadata: GameMetadata
    moves: list[MoveAnalysis] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    ai_summary: str | None = None
    pgn_content: str | None = None

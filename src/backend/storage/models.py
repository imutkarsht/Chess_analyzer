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

    def to_dict(self) -> dict[str, Any]:
        return {
            "move_number": self.move_number,
            "ply": self.ply,
            "san": self.san,
            "uci": self.uci,
            "fen_before": self.fen_before,
            "eval_before_cp": self.eval_before_cp,
            "eval_before_mate": self.eval_before_mate,
            "best_move": self.best_move,
            "best_eval_cp": self.best_eval_cp,
            "best_eval_mate": self.best_eval_mate,
            "pv": self.pv,
            "eval_after_cp": self.eval_after_cp,
            "eval_after_mate": self.eval_after_mate,
            "win_chance_before": self.win_chance_before,
            "win_chance_after": self.win_chance_after,
            "classification": self.classification,
            "explanation": self.explanation,
            "multi_pvs": self.multi_pvs,
            "is_book_move": self.is_book_move,
            "book_move_count": self.book_move_count,
            "book_exit_move": self.book_exit_move,
            "eco": self.eco,
            "opening_name": self.opening_name,
            "candidate_continuations": self.candidate_continuations,
            "time_left": self.time_left,
            "time_spent": self.time_spent,
            "raw_clk": self.raw_clk,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MoveAnalysis":
        return cls(
            move_number=d.get("move_number", 0),
            ply=d.get("ply", 0),
            san=d.get("san", ""),
            uci=d.get("uci", ""),
            fen_before=d.get("fen_before", ""),
            eval_before_cp=d.get("eval_before_cp"),
            eval_before_mate=d.get("eval_before_mate"),
            best_move=d.get("best_move"),
            best_eval_cp=d.get("best_eval_cp"),
            best_eval_mate=d.get("best_eval_mate"),
            pv=d.get("pv", []),
            eval_after_cp=d.get("eval_after_cp"),
            eval_after_mate=d.get("eval_after_mate"),
            win_chance_before=d.get("win_chance_before", 0.5),
            win_chance_after=d.get("win_chance_after", 0.5),
            classification=d.get("classification", ""),
            explanation=d.get("explanation", ""),
            multi_pvs=d.get("multi_pvs", []),
            is_book_move=d.get("is_book_move", False),
            book_move_count=d.get("book_move_count", 0),
            book_exit_move=d.get("book_exit_move", False),
            eco=d.get("eco", ""),
            opening_name=d.get("opening_name", ""),
            candidate_continuations=d.get("candidate_continuations", []),
            time_left=d.get("time_left"),
            time_spent=d.get("time_spent"),
            raw_clk=d.get("raw_clk"),
        )


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

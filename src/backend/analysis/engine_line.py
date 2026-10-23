"""Engine line model shared by cached analysis and live engine output.

Every score in this module is **White perspective** (positive = White is
better), matching the project-wide convention for ``MoveAnalysis``.  The
side-to-move conversion happens exactly once, when a line is ingested, so
no renderer ever has to flip a score again.

The module is pure Python: no Qt imports, independently testable.
"""

from __future__ import annotations

import chess

# Mate scores are converted to centipawns with this sentinel so a numeric
# score is always comparable.  It only matters for sorting/display of
# non-mate alternatives.
MATE_SCORE_CP = 100_000

# Placeholder shown when a line has no usable score yet.
UNKNOWN_SCORE = "—"


def _as_depth(value) -> int | None:
    """Normalise an engine/cached depth value; ``None`` means "unknown"."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        return int(value) if value > 0 else None
    return None


def _parse_score_text(text) -> tuple[int | None, int | None]:
    """Parse ``"M3"``/``"-M3"``/``"+0.54"`` into ``(cp, mate)``.

    Older cached records only stored the rendered ``score_value`` string, so
    the model has to be able to recover the numbers from it.
    """
    if not isinstance(text, str):
        return None, None
    value = text.strip()
    if not value or value in {UNKNOWN_SCORE, "?", "--"}:
        return None, None
    if value.startswith("M") or value.startswith("-M") or value.startswith("+M"):
        try:
            return None, int(value.replace("M", "").replace("+", ""))
        except ValueError:
            return None, None
    try:
        return round(float(value) * 100), None
    except ValueError:
        return None, None


def _variation_san(board: chess.Board | None, pv_moves) -> str:
    """SAN for a PV, degrading gracefully when the tail is not playable."""
    if not pv_moves:
        return ""
    if board is not None:
        try:
            return board.variation_san(pv_moves)
        except (AssertionError, ValueError):
            pass
    probe = board.copy() if board is not None else None
    parts: list[str] = []
    for move in pv_moves:
        if probe is None:
            parts.append(move.uci() if hasattr(move, "uci") else str(move))
            continue
        try:
            parts.append(probe.san(move))
            probe.push(move)
        except (AssertionError, ValueError):
            break
    return " ".join(parts)


class EngineLine:
    """One candidate line, already normalised to White perspective."""

    __slots__ = ("rank", "depth", "cp", "mate", "pv_uci", "pv_san")

    def __init__(
        self,
        rank: int = 1,
        depth: int | None = None,
        cp: int | None = None,
        mate: int | None = None,
        pv_uci: tuple[str, ...] = (),
        pv_san: str = "",
    ):
        self.rank = rank
        self.depth = depth
        self.cp = cp
        self.mate = mate
        self.pv_uci = pv_uci
        self.pv_san = pv_san

    # -- convenience -------------------------------------------------
    @property
    def first_move(self) -> str | None:
        return self.pv_uci[0] if self.pv_uci else None

    @property
    def score_text(self) -> str:
        if self.mate is not None:
            return f"M{self.mate}" if self.mate > 0 else f"-M{abs(self.mate)}"
        if self.cp is not None:
            return f"{self.cp / 100:+.2f}"
        return UNKNOWN_SCORE

    @property
    def score_tone(self) -> int:
        """1 = White better, -1 = Black better, 0 = level/unknown."""
        value = self.mate if self.mate is not None else self.cp
        if value is None or value == 0:
            return 0
        return 1 if value > 0 else -1

    @property
    def sort_key(self) -> tuple[int, int]:
        return self.rank, self.depth or 0

    def with_longer_pv(self, previous: EngineLine) -> EngineLine:
        """Keep ``previous``'s continuation when the engine re-emits a prefix.

        Stockfish sometimes reports a root line with a truncated PV (a
        transposition-table cut-off).  The shorter list is still the start of
        the same line, so replacing the panel with it is what made the top row
        collapse to two plies while the others stayed complete.
        """
        if (
            previous
            and self.pv_uci
            and previous.pv_uci
            and len(self.pv_uci) < len(previous.pv_uci)
            and previous.pv_uci[: len(self.pv_uci)] == self.pv_uci
        ):
            return EngineLine(
                rank=self.rank,
                depth=self.depth,
                cp=self.cp,
                mate=self.mate,
                pv_uci=previous.pv_uci,
                pv_san=previous.pv_san,
            )
        return self

    def __eq__(self, other) -> bool:
        if not isinstance(other, EngineLine):
            return NotImplemented
        return (
            self.rank,
            self.depth,
            self.cp,
            self.mate,
            self.pv_uci,
            self.pv_san,
        ) == (
            other.rank,
            other.depth,
            other.cp,
            other.mate,
            other.pv_uci,
            other.pv_san,
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"EngineLine(rank={self.rank}, depth={self.depth}, "
            f"cp={self.cp}, mate={self.mate}, pv={self.pv_uci[:3]})"
        )


def line_from_engine_info(info: dict, board: chess.Board) -> EngineLine:
    """Convert one python-chess ``analysis()`` info dict to an ``EngineLine``.

    ``PovScore.white()`` does the side-to-move conversion, so both cp and mate
    end up White-perspective even when Black is to move.
    """
    cp: int | None = None
    mate: int | None = None
    score = info.get("score")
    if score is not None:
        white = score.white()
        mate = white.mate()
        if mate is None:
            cp = white.score(mate_score=MATE_SCORE_CP)

    pv_moves = list(info.get("pv") or [])
    rank = info.get("multipv", 1)
    return EngineLine(
        rank=int(rank) if isinstance(rank, int) and rank > 0 else 1,
        depth=_as_depth(info.get("depth")),
        cp=cp,
        mate=mate,
        pv_uci=tuple(move.uci() for move in pv_moves),
        pv_san=_variation_san(board, pv_moves),
    )


def line_from_cached(
    pv_data: dict,
    turn: chess.Color,
    rank: int = 1,
    board: chess.Board | None = None,
) -> EngineLine:
    """Convert a stored MultiPV dict (side-to-move scores) to White perspective."""
    cp = pv_data.get("cp")
    mate = pv_data.get("mate")
    if cp is None and mate is None:
        cp, mate = _parse_score_text(pv_data.get("score_value"))

    cp = int(cp) if isinstance(cp, (int, float)) else None
    mate = int(mate) if isinstance(mate, (int, float)) else None
    if turn == chess.BLACK:
        cp = -cp if cp is not None else None
        mate = -mate if mate is not None else None

    raw_pv = pv_data.get("pv_uci") or pv_data.get("pv") or []
    pv_uci = tuple(
        move if isinstance(move, str) else move.uci() for move in raw_pv
    )

    pv_san = pv_data.get("pv_san") or ""
    if not pv_san and board is not None:
        pv_san = _variation_san(
            board, [chess.Move.from_uci(uci) for uci in pv_uci if uci]
        )

    return EngineLine(
        rank=rank,
        depth=_as_depth(pv_data.get("depth")),
        cp=cp,
        mate=mate,
        pv_uci=pv_uci,
        pv_san=pv_san,
    )


def position_after(move, chess960: bool = False) -> str:
    """FEN of the board *after* ``move``; falls back to ``fen_before``."""
    try:
        board = chess.Board(move.fen_before, chess960=chess960)
        board.push_uci(move.uci)
        return board.fen()
    except (AssertionError, ValueError):
        return move.fen_before

"""
Grounded move-insight builder for the Coach ("why was this a blunder?") feature.

This module turns facts that already exist after analysis into a single
structured ``MoveInsight``:

- the Stockfish evaluations / best line / multi-PV stored on ``MoveAnalysis``
- tactical primitives from this package (hanging pieces, motifs, SEE, phase)

It never calls the network and never runs an engine. The LLM (Phase 2) is only a
translator of ``format_move_insight_for_llm``; the deterministic
``format_move_insight_offline`` text must stand on its own with 0 connectivity.

Zero Qt dependencies — headless and independently testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import chess

from src.backend.analysis.tactics.board_utils import to_user_wp
from src.backend.analysis.tactics.hanging import get_hanging_pieces
from src.backend.analysis.tactics.motifs import detect_tactical_motifs
from src.backend.analysis.tactics.phase import classify_game_phase
from src.backend.analysis.tactics.see import static_exchange_evaluation
from src.backend.storage.models import GameMetadata, MoveAnalysis
from src.constants import (
    SACRIFICIAL_CLASSIFICATIONS,
    SOUND_CLASSIFICATIONS,
)
from src.utils.logger import logger

# How many plies of the opponent's best line to quote (kept short so the LLM
# cannot mis-number a long forcing sequence).
REFUTATION_MAX_PLIES = 4

# Destination square of a SAN move ("exd5" -> "d5", "Nbd7" -> "d7", "O-O" -> None).
_SAN_SQUARE_RE = re.compile(r"([a-h][1-8])")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MoveInsight:
    """Structured, hallucination-proof facts about a single played move."""

    # identity
    ply: int
    move_number: int
    san: str
    uci: str
    fen_before: str
    classification: str
    side: str  # "white" | "black"
    phase: str  # opening | middlegame | endgame

    # Evaluations use the app's canonical White-perspective sign (the same one
    # as the eval bar, move list and game report) so every surface agrees.
    eval_before: str
    eval_after: str
    # Mate scores stay player-signed: they drive the coach's "you" language
    # (forced mate for you / mate against you), not the displayed eval.
    player_mate_before: int | None
    player_mate_after: int | None
    # Win chances are from the player's perspective: 87% always means the
    # player who made the move wins 87% of the time, regardless of colour.
    wp_before: float
    wp_after: float

    # alternatives & punishment
    best_move_san: str | None
    best_move_uci: str | None
    best_eval: str | None
    refutation_san: list[str] = field(default_factory=list)
    actual_reply_san: str | None = None

    # tactics
    hung_pieces: list[dict[str, Any]] = field(default_factory=list)
    allowed_motifs: list[str] = field(default_factory=list)
    material_loss_cp: int | None = None
    missed_mate: bool = False

    # context
    opening_name: str = ""
    eco: str = ""
    player_elo: str | None = None
    time_spent: float | None = None

    # ---- derived helpers -------------------------------------------------

    @property
    def is_sound(self) -> bool:
        return self.classification in SOUND_CLASSIFICATIONS

    @property
    def is_sacrificial(self) -> bool:
        return self.classification in SACRIFICIAL_CLASSIFICATIONS

    @property
    def forced_mate(self) -> bool:
        """The player has a forced mate *after* the played move."""
        return self.player_mate_after is not None and self.player_mate_after > 0

    @property
    def mate_threat_in(self) -> int | None:
        """Mate the opponent now forces against the player, if any."""
        if self.player_mate_after is not None and self.player_mate_after < 0:
            return abs(self.player_mate_after)
        return None

    @property
    def numbered_san(self) -> str:
        return f"{move_prefix(self.move_number, self.side)}{self.san}"

    @property
    def refutation_prefix(self) -> str:
        """
        Move-number prefix for the opponent's reply.

        The reply is the opponent's move: it shares the played move's number when
        the player just moved as White (5.Nxe5 -> 5...Bxd1), and takes the next
        one when the player moved as Black (5...Bxd1 -> 6.Bxf7+).
        """
        opponent_side = "black" if self.side == "white" else "white"
        opponent_move_number = self.move_number + (1 if self.side == "black" else 0)
        return move_prefix(opponent_move_number, opponent_side)

    @property
    def refutation_text(self) -> str:
        """Opponent's best line with a correct leading move number."""
        if not self.refutation_san:
            return ""
        return f"{self.refutation_prefix}{' '.join(self.refutation_san)}"


def move_prefix(move_number: int, side: str) -> str:
    """Chess notation prefix for a move, e.g. ``'23.'`` or ``'23...'``."""
    return f"{move_number}{'.' if side == 'white' else '...'}"


# ---------------------------------------------------------------------------
# Small formatting helpers
# ---------------------------------------------------------------------------


def _fmt_eval(cp: int | None, mate: int | None) -> str:
    if mate is not None:
        return f"M{mate}" if mate > 0 else f"-M{abs(mate)}"
    if cp is None:
        return "?"
    return f"{cp / 100:+.2f}"


def _fmt_wp(wp: float | None) -> str:
    return "?" if wp is None else f"{wp * 100:.0f}%"


def _side_of_ply(ply: int) -> str:
    """
    Map a ply to the side that played it.

    ``MoveAnalysis.ply`` is ``chess.Board.ply()`` read *before* the push in
    ``PGNParser``, i.e. 0-based: 1.e4 is ply 0. Getting this wrong inverts the
    side (and with it every score, prefix and "you" in the explanation).
    """
    return "white" if ply % 2 == 0 else "black"


def _user_signed(value: int | None, is_user_white: bool) -> int | None:
    """Flip a White-perspective integer (cp or mate) to the player's view."""
    if value is None:
        return None
    return value if is_user_white else -value


def _san_square(san: str) -> str | None:
    """Best-effort destination square of a SAN token; None for castling."""
    if san.startswith("O-O"):
        return None
    found = _SAN_SQUARE_RE.findall(san)
    return found[-1] if found else None


def _biggest_hung(insight: MoveInsight) -> dict[str, Any] | None:
    """The hung piece the opponent profits from most (deterministic order)."""
    if not insight.hung_pieces:
        return None
    return max(insight.hung_pieces, key=lambda h: h.get("enemy_see_gain", 0))


# ---------------------------------------------------------------------------
# Phase 0 — fact builder
# ---------------------------------------------------------------------------


def build_move_insight(
    moves: list[MoveAnalysis],
    index: int,
    *,
    metadata: GameMetadata | None = None,
    chess960: bool = False,
) -> MoveInsight | None:
    """
    Build the grounded fact set for ``moves[index]``.

    Degrades to ``None`` (never raises) on malformed FEN/UCI, an illegal move,
    or an out-of-range index. Refutation facts are omitted gracefully when the
    next move is missing or not analysed yet.
    """
    if not (0 <= index < len(moves)):
        return None

    move = moves[index]
    if not move.fen_before or not move.uci:
        return None

    try:
        board_before = chess.Board(move.fen_before, chess960=chess960)
        move_obj = chess.Move.from_uci(move.uci)
        if move_obj not in board_before.legal_moves:
            logger.debug("Insight skipped: illegal move %s at index %d", move.uci, index)
            return None
        board_after = board_before.copy()
        board_after.push(move_obj)
    except Exception as exc:  # noqa: BLE001 - malformed PGN must never crash the UI
        logger.debug("Insight skipped: bad position at index %d (%s)", index, exc)
        return None

    side = _side_of_ply(move.ply)
    is_user_white = side == "white"

    # --- evaluations ------------------------------------------------------
    # Display strings stay White-perspective: the Coach card must agree with
    # the eval bar, move list and game report (positive = White is better).
    # Win chances are converted once, here, to the player's own view.
    eval_before = _fmt_eval(move.eval_before_cp, move.eval_before_mate)
    eval_after = _fmt_eval(move.eval_after_cp, move.eval_after_mate)
    player_mate_before = _user_signed(move.eval_before_mate, is_user_white)
    player_mate_after = _user_signed(move.eval_after_mate, is_user_white)
    wp_before = to_user_wp(move.win_chance_before, is_user_white)
    wp_after = to_user_wp(move.win_chance_after, is_user_white)

    # --- best alternative (from fen_before) ------------------------------
    best_move_uci = move.best_move
    if not best_move_uci and move.multi_pvs:
        pv = move.multi_pvs[0].get("pv") or []
        best_move_uci = pv[0] if pv else None
    best_move_san = _uci_to_san(board_before, best_move_uci)

    # --- refutation = opponent's best line AFTER the played move ---------
    refutation_san: list[str] = []
    actual_reply_san: str | None = None
    material_loss_cp: int | None = None
    allowed_motifs: list[str] = []
    next_move = moves[index + 1] if index + 1 < len(moves) else None

    # The PV is only trustworthy if it was analysed from the position the
    # played move actually reached.
    if next_move is not None and next_move.multi_pvs and next_move.fen_before == board_after.fen():
        pv_uci = list(next_move.multi_pvs[0].get("pv") or [])
        refutation_san = _pv_to_san(board_after, pv_uci)
        actual_reply_san = next_move.san or None
        if pv_uci:
            first = _safe_move(pv_uci[0])
            if first is not None and first in board_after.legal_moves:
                if board_after.is_capture(first):
                    gain = static_exchange_evaluation(
                        board_after, first.to_square, board_after.turn
                    )
                    material_loss_cp = gain or None
                ref_after = board_after.copy()
                ref_after.push(first)
                allowed_motifs = detect_tactical_motifs(
                    board_after, ref_after, first, board_after.turn
                )

    # --- tactics on the played move --------------------------------------
    # Hung pieces are the *player's* own pieces left loose, so query the
    # player's colour (the side to move before the played move).
    player_color = board_before.turn
    hung_pieces = get_hanging_pieces(
        board_after, player_color, last_move=move_obj, board_before=board_before
    )
    if material_loss_cp is None and hung_pieces:
        material_loss_cp = max(h.get("enemy_see_gain", 0) for h in hung_pieces) or None

    mate_before = player_mate_before is not None and player_mate_before > 0
    mate_after = player_mate_after is not None and player_mate_after > 0

    eco = (getattr(metadata, "eco", None) or move.eco or "") if metadata else (move.eco or "")
    opening = (
        (getattr(metadata, "opening", None) or move.opening_name or "")
        if metadata
        else (move.opening_name or "")
    )
    player_elo = None
    if metadata is not None:
        player_elo = metadata.white_elo if is_user_white else metadata.black_elo

    return MoveInsight(
        ply=move.ply,
        move_number=move.move_number or (move.ply // 2 + 1),
        san=move.san,
        uci=move.uci,
        fen_before=move.fen_before,
        classification=move.classification,
        side=side,
        phase=classify_game_phase(board_before, move.ply, is_book_move=move.is_book_move),
        eval_before=eval_before,
        eval_after=eval_after,
        player_mate_before=player_mate_before,
        player_mate_after=player_mate_after,
        wp_before=wp_before,
        wp_after=wp_after,
        best_move_san=best_move_san,
        best_move_uci=best_move_uci,
        best_eval=eval_before,
        refutation_san=refutation_san,
        actual_reply_san=actual_reply_san,
        hung_pieces=hung_pieces,
        allowed_motifs=allowed_motifs,
        material_loss_cp=material_loss_cp,
        missed_mate=mate_before and not mate_after,
        opening_name=opening,
        eco=eco,
        player_elo=player_elo,
        time_spent=move.time_spent,
    )


def _safe_move(uci: str) -> chess.Move | None:
    try:
        return chess.Move.from_uci(uci)
    except Exception:  # noqa: BLE001
        return None


def _uci_to_san(board: chess.Board, uci: str | None) -> str | None:
    """Convert a UCI move to SAN on ``board``; None when unavailable/illegal."""
    if not uci:
        return None
    move = _safe_move(uci)
    if move is None or move not in board.legal_moves:
        return None
    try:
        return board.san(move)
    except Exception:  # noqa: BLE001
        return None


def _pv_to_san(
    board: chess.Board, pv_uci: list[str], limit: int = REFUTATION_MAX_PLIES
) -> list[str]:
    """Replay a UCI principal variation into a short list of SAN moves."""
    sans: list[str] = []
    work = board.copy()
    for uci in pv_uci[:limit]:
        move = _safe_move(uci)
        if move is None or move not in work.legal_moves:
            break
        sans.append(work.san(move))
        work.push(move)
    return sans


# ---------------------------------------------------------------------------
# Allowed-token sets (single source for the mandatory reply validation)
# ---------------------------------------------------------------------------


def insight_allowed_tokens(insight: MoveInsight) -> tuple[set[str], set[str]]:
    """
    Return ``(allowed_san, allowed_squares)`` for validating an LLM reply.

    Anything the model may legitimately name is derived from the insight, so the
    validator can never accept an invented move/square.
    """
    allowed_san: set[str] = {insight.san}
    for san in (
        insight.best_move_san,
        insight.actual_reply_san,
        *insight.refutation_san,
    ):
        if san:
            allowed_san.add(san)

    allowed_squares: set[str] = {h["square"] for h in insight.hung_pieces}
    for san in allowed_san:
        destination = _san_square(san)
        if destination:
            allowed_squares.add(destination)
    return allowed_san, allowed_squares


# ---------------------------------------------------------------------------
# Phase 0 — text renderers
# ---------------------------------------------------------------------------


def format_move_insight_for_llm(insight: MoveInsight) -> str:
    """
    The fact dossier handed to the LLM.

    Deliberately neutral wording: it never says "engine"/"stockfish", because
    models echo meta-words from the facts into their answer.
    """
    lines = [
        "FACT SHEET - single move",
        "",
        f"- Played: {insight.numbered_san} ({insight.side})",
        f"- Classification: {insight.classification}",
        f"- Phase: {insight.phase}",
        f"- Player: {insight.side.capitalize()}"
        + (f", rating {insight.player_elo}" if insight.player_elo else ""),
    ]
    if insight.eco or insight.opening_name:
        lines.append(f"- Opening: {insight.eco} {insight.opening_name}".rstrip())

    lines += [
        "",
        "Evaluations (White's perspective; positive = White is better)",
        f"- Before the move: {insight.eval_before}",
        f"- After the move:  {insight.eval_after}",
        f"Win chances (from {insight.side}'s perspective; higher = better for "
        f"{insight.side})",
        f"- Before the move: {_fmt_wp(insight.wp_before)}",
        f"- After the move:  {_fmt_wp(insight.wp_after)}",
        "",
        "Deterministic findings",
    ]
    lines.extend(f"- {finding}" for finding in _finding_lines(insight))

    lines += ["", "Opponent's refutation (best line)"]
    if insight.refutation_text:
        lines.append(f"- {insight.refutation_text}")
    else:
        lines.append("- (none available)")
    if (
        insight.actual_reply_san
        and insight.refutation_san
        and insight.actual_reply_san != insight.refutation_san[0]
    ):
        lines.append(
            f"- In the actual game the opponent replied {insight.actual_reply_san}, "
            "which is NOT the best line above (it is a separate branch)."
        )

    if insight.best_move_san and insight.best_move_uci == insight.uci:
        lines += ["", "Assessment", "- This is the strongest move available in the position.", ""]
    elif insight.best_move_san:
        lines += [
            "",
            "Better move",
            f"- {move_prefix(insight.move_number, insight.side)}"
            f"{insight.best_move_san} (keeps {insight.best_eval})",
            "",
        ]
    else:
        lines.append("")

    lines.append(
        f"Write 2-3 sentences explaining {insight.san} to the {insight.side} player. "
        "Quote the evaluations exactly as given (White's perspective) and the win chances "
        "exactly as given (the player's perspective). Never flip a sign, convert between "
        "perspectives, or calculate a win chance from an evaluation."
    )
    return "\n".join(lines)


def _finding_lines(insight: MoveInsight) -> list[str]:
    """Deterministic findings shared by the dossier and the offline text."""
    findings: list[str] = []
    if insight.missed_mate:
        findings.append(f"You had a forced mate before this move ({insight.eval_before}).")
    mate_in = insight.mate_threat_in
    if mate_in is not None:
        findings.append(f"The opponent now forces mate in {mate_in}.")

    # A mate against the player is the whole story: loose-piece arithmetic is
    # noise next to it. A mate *for* the player is the sacrifice's payoff, so
    # the sacrificed piece stays in the facts.
    if insight.mate_threat_in is None:
        hung = _biggest_hung(insight)
        if hung is not None:
            if hung.get("is_undefended"):
                state = "undefended"
            else:
                state = (
                    f"under-defended (attackers {hung.get('attacker_count', 0)}, "
                    f"defenders {hung.get('defender_count', 0)})"
                )
            see = hung.get("enemy_see_gain", 0)
            findings.append(
                f"Your {hung.get('piece_name', 'piece')} on {hung.get('square', '?')} is left "
                f"{state} (material at risk about {see / 100:.1f} pawns)."
            )
        if insight.allowed_motifs:
            findings.append(
                "This move permits the opponent to execute: "
                + ", ".join(insight.allowed_motifs)
                + "."
            )
    if not findings:
        findings.append("No immediate material or tactical concession detected.")
    return findings


def format_move_insight_offline(insight: MoveInsight) -> str:
    """
    Deterministic plain-English explanation. Always available, 0 network.

    Wording is priority-ordered to mirror ``classify_move()`` and must never
    contradict the classification badge (see the coherence test):
    sound moves are never framed negatively, sacrificial moves are framed as
    gains, and a "missed mate" is only ever claimed when one was really lost.
    """
    if insight.is_sound:
        return _offline_sound(insight)
    if insight.is_sacrificial:
        return _offline_sacrificial(insight)
    return _offline_problem(insight)


def _offline_sound(insight: MoveInsight) -> str:
    if insight.best_move_uci and insight.best_move_uci == insight.uci:
        lead = (
            f"{insight.numbered_san} is the strongest move in the position ({insight.eval_after})."
        )
    else:
        lead = f"{insight.numbered_san} is a sound move ({insight.eval_after})."
    if insight.best_move_san and insight.best_move_uci != insight.uci:
        return f"{lead} The top choice was {insight.best_move_san}, keeping {insight.best_eval}."
    return lead


def _offline_sacrificial(insight: MoveInsight) -> str:
    lead = f"{insight.numbered_san} is a strong move ({insight.eval_after})."
    hung = _biggest_hung(insight)
    if hung is not None:
        lead += (
            f" It gives up your {hung.get('piece_name', 'piece')} on "
            f"{hung.get('square', '?')} to keep the initiative."
        )
    if insight.forced_mate:
        lead += " The follow-up is a forced mate."
    if insight.refutation_text:
        lead += f" The main line runs {insight.refutation_text}."
    return lead


def _offline_problem(insight: MoveInsight) -> str:
    parts: list[str] = []
    if insight.missed_mate and insight.best_move_san:
        parts.append(
            f"You had a forced mate: {insight.best_move_san} kept the win, "
            f"instead of {insight.san} ({insight.eval_before} to {insight.eval_after})."
        )
    mate_in = insight.mate_threat_in
    if mate_in is not None:
        parts.append(f"The opponent now forces mate in {mate_in}.")

    # When a forced mate is coming, material/loose-piece detail is noise — the
    # mate is the whole story.
    if mate_in is None:
        hung = _biggest_hung(insight)
        if hung is not None:
            state = "undefended" if hung.get("is_undefended") else "under-defended"
            sentence = (
                f"This leaves your {hung.get('piece_name', 'piece')} on "
                f"{hung.get('square', '?')} {state}"
            )
            if insight.refutation_san:
                sentence += (
                    f"; after {insight.refutation_prefix}{insight.refutation_san[0]} "
                    "you are losing material"
                )
            if insight.material_loss_cp:
                sentence += f" (about {insight.material_loss_cp / 100:.1f} pawns)"
            parts.append(sentence + ".")

        if insight.allowed_motifs and insight.refutation_san:
            parts.append(
                f"It allows {insight.refutation_prefix}{insight.refutation_san[0]}, "
                f"creating a {', '.join(insight.allowed_motifs)}."
            )

    parts.append(
        f"Your winning chances fell from {_fmt_wp(insight.wp_before)} "
        f"to {_fmt_wp(insight.wp_after)}."
    )
    if insight.best_move_san:
        parts.append(
            f"Best was {move_prefix(insight.move_number, insight.side)}"
            f"{insight.best_move_san}, keeping {insight.best_eval}."
        )
    return " ".join(parts)

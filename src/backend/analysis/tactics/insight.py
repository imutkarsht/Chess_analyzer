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

from src.backend.analysis.math_utils import get_win_probability
from src.backend.analysis.tactics.board_utils import to_user_wp
from src.backend.analysis.tactics.constants import PIECE_NAMES, PIECE_VALUES
from src.backend.analysis.tactics.explanation import (
    build_explanation_plan,
    format_plan_for_llm,
    format_plan_offline,
)
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

# The explanation needs enough of the main line to show the idea (a sacrifice,
# a queen entry, a knight coming to the attack), but not so much that the model
# drowns in a 20-ply engine PV.
LINE_MAX_PLIES = 10
# The card quotes a short preview; replay still uses the full stored line.
LINE_TEXT_PLIES = 6

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

    # Move mechanics -----------------------------------------------------
    is_capture: bool = False
    captured_piece_name: str | None = None
    gives_check: bool = False
    is_double_check: bool = False
    is_checkmate: bool = False
    is_promotion: bool = False
    is_castle: bool = False
    moved_piece_name: str = ""
    from_square: str = ""
    to_square: str = ""

    # Concrete tactics and threats ---------------------------------------
    played_motifs: list[str] = field(default_factory=list)
    # Only pieces that became loose because of this move. ``hung_pieces`` is
    # retained for compatibility, but explanations must not blame a move for a
    # piece that was already hanging before it was played.
    new_hung_pieces: list[dict[str, Any]] = field(default_factory=list)
    created_threats: list[dict[str, Any]] = field(default_factory=list)
    offered_piece: dict[str, Any] | None = None

    # Concrete lines ------------------------------------------------------
    main_line_uci: list[str] = field(default_factory=list)
    main_line_san: list[str] = field(default_factory=list)
    main_line_text: str = ""
    main_line_captures: list[dict[str, Any]] = field(default_factory=list)
    line_material_delta_cp: int | None = None
    line_ends_in_mate: bool = False
    follow_up_san: str | None = None
    best_line_uci: list[str] = field(default_factory=list)
    best_line_san: list[str] = field(default_factory=list)
    best_line_text: str = ""
    second_best_move_san: str | None = None
    second_best_eval: str | None = None
    second_best_line_san: list[str] = field(default_factory=list)
    second_best_line_text: str = ""
    alternative_gap_wp: float | None = None
    is_only_move: bool = False
    already_winning: bool = False

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
    def is_actual_sacrifice(self) -> bool:
        """True only when the move itself was detected as a sacrifice."""
        return "sacrifice" in self.played_motifs

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

    # --- tactics and move mechanics on the played move --------------------
    player_color = board_before.turn
    moved_piece = board_before.piece_at(move_obj.from_square)
    captured_piece = _captured_piece(board_before, move_obj)
    played_motifs = detect_tactical_motifs(
        board_before, board_after, move_obj, player_color, move.classification
    )

    hung_before = get_hanging_pieces(board_before, player_color)
    hung_pieces = get_hanging_pieces(
        board_after, player_color, last_move=move_obj, board_before=board_before
    )
    hung_before_squares = {piece["square"] for piece in hung_before}
    new_hung_pieces = [
        piece for piece in hung_pieces if piece["square"] not in hung_before_squares
    ]

    enemy_color = not player_color
    enemy_hung_before = {
        piece["square"] for piece in get_hanging_pieces(board_before, enemy_color)
    }
    created_threats = [
        piece
        for piece in get_hanging_pieces(board_after, enemy_color)
        if piece["square"] not in enemy_hung_before
    ]

    offered_piece = None
    if "sacrifice" in played_motifs:
        destination = chess.square_name(move_obj.to_square)
        offered_piece = next(
            (piece for piece in new_hung_pieces if piece["square"] == destination),
            None,
        )
        if offered_piece is None and new_hung_pieces:
            offered_piece = max(
                new_hung_pieces, key=lambda piece: piece.get("enemy_see_gain", 0)
            )

    if material_loss_cp is None and new_hung_pieces:
        material_loss_cp = (
            max(piece.get("enemy_see_gain", 0) for piece in new_hung_pieces) or None
        )

    # --- concrete lines ---------------------------------------------------
    top_pv_uci = []
    if move.multi_pvs:
        top_pv_uci = list(move.multi_pvs[0].get("pv") or [])
    if not top_pv_uci and move.pv:
        top_pv_uci = list(move.pv)

    if top_pv_uci and top_pv_uci[0] == move.uci:
        main_line_uci = top_pv_uci[:LINE_MAX_PLIES]
    elif (
        next_move is not None
        and next_move.multi_pvs
        and next_move.fen_before == board_after.fen()
    ):
        main_line_uci = [
            move.uci,
            *list(next_move.multi_pvs[0].get("pv") or [])[: LINE_MAX_PLIES - 1],
        ]
    else:
        main_line_uci = [move.uci]

    main_line_san, line_captures, line_ends_in_mate, line_material_delta_cp = _scan_line(
        board_before, main_line_uci
    )
    main_line_text = _format_line(board_before, main_line_uci, limit=LINE_TEXT_PLIES)

    best_line_uci = (
        top_pv_uci[:LINE_MAX_PLIES]
        if top_pv_uci and (not best_move_uci or top_pv_uci[0] == best_move_uci)
        else []
    )
    best_line_san, _, _, _ = _scan_line(board_before, best_line_uci)
    best_line_text = _format_line(board_before, best_line_uci)

    second_pv = move.multi_pvs[1] if len(move.multi_pvs) > 1 else None
    second_pv_uci = list(second_pv.get("pv") or []) if second_pv else []
    second_best_move_san = _uci_to_san(
        board_before, second_pv_uci[0] if second_pv_uci else None
    )
    second_best_eval = _pv_eval_white(second_pv, is_user_white)
    second_best_line_san, _, _, _ = _scan_line(board_before, second_pv_uci)
    second_best_line_text = _format_line(board_before, second_pv_uci)

    best_wp = _pv_player_wp(_pv_data(move)) or wp_before
    second_wp = _pv_player_wp(second_pv)
    alternative_gap_wp = best_wp - second_wp if second_wp is not None else None
    is_only_move = alternative_gap_wp is not None and alternative_gap_wp >= 0.15

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
        is_capture=board_before.is_capture(move_obj),
        captured_piece_name=(
            PIECE_NAMES.get(captured_piece.piece_type) if captured_piece else None
        ),
        gives_check=board_after.is_check(),
        is_double_check=board_after.is_check() and len(board_after.checkers()) > 1,
        is_checkmate=board_after.is_checkmate(),
        is_promotion=move_obj.promotion is not None,
        is_castle=board_before.is_castling(move_obj),
        moved_piece_name=(
            PIECE_NAMES.get(moved_piece.piece_type) if moved_piece else "piece"
        ),
        from_square=chess.square_name(move_obj.from_square),
        to_square=chess.square_name(move_obj.to_square),
        played_motifs=played_motifs,
        new_hung_pieces=new_hung_pieces,
        created_threats=created_threats,
        offered_piece=offered_piece,
        main_line_uci=main_line_uci,
        main_line_san=main_line_san,
        main_line_text=main_line_text,
        main_line_captures=line_captures,
        line_material_delta_cp=line_material_delta_cp,
        line_ends_in_mate=line_ends_in_mate or mate_after,
        follow_up_san=main_line_san[2] if len(main_line_san) >= 3 else None,
        best_line_uci=best_line_uci,
        best_line_san=best_line_san,
        best_line_text=best_line_text,
        second_best_move_san=second_best_move_san,
        second_best_eval=second_best_eval,
        second_best_line_san=second_best_line_san,
        second_best_line_text=second_best_line_text,
        alternative_gap_wp=alternative_gap_wp,
        is_only_move=is_only_move,
        already_winning=wp_before >= 0.95,
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


def _captured_piece(board: chess.Board, move: chess.Move) -> chess.Piece | None:
    """Piece removed by ``move`` (handles en passant)."""
    if board.is_en_passant(move):
        ep_square = chess.square(
            chess.square_file(move.to_square),
            chess.square_rank(move.from_square),
        )
        return board.piece_at(ep_square)
    return board.piece_at(move.to_square)


def _material_cp(board: chess.Board, color: chess.Color) -> int:
    return sum(
        PIECE_VALUES.get(piece.piece_type, 0) * 100
        for piece in board.piece_map().values()
        if piece.color == color
    )


def _scan_line(
    board: chess.Board, uci_moves: list[str], limit: int = LINE_MAX_PLIES
) -> tuple[list[str], list[dict[str, Any]], bool, int | None]:
    """Replay a UCI line and extract the concrete events an explanation cites."""
    sans: list[str] = []
    captures: list[dict[str, Any]] = []
    ends_in_mate = False
    work = board.copy()
    player_color = board.turn

    for ply, uci in enumerate(uci_moves[:limit], start=1):
        move = _safe_move(uci)
        if move is None or move not in work.legal_moves:
            break
        sans.append(work.san(move))
        captured = _captured_piece(work, move) if work.is_capture(move) else None
        if captured is not None:
            captures.append(
                {
                    "san": sans[-1],
                    "piece_name": PIECE_NAMES.get(captured.piece_type, "piece"),
                    "value_cp": PIECE_VALUES.get(captured.piece_type, 0) * 100,
                    "by": "white" if work.turn == chess.WHITE else "black",
                    "ply": ply,
                }
            )
        if sans[-1].endswith("#"):
            ends_in_mate = True
        work.push(move)

    enemy_color = not player_color
    before_balance = _material_cp(board, player_color) - _material_cp(board, enemy_color)
    after_balance = _material_cp(work, player_color) - _material_cp(work, enemy_color)
    material_delta = after_balance - before_balance
    return sans, captures, ends_in_mate, material_delta


def _format_line(
    board: chess.Board, uci_moves: list[str], limit: int = LINE_MAX_PLIES
) -> str:
    """Format a UCI line as correctly numbered SAN, or '' when unusable."""
    moves: list[chess.Move] = []
    work = board.copy()
    for uci in uci_moves[:limit]:
        move = _safe_move(uci)
        if move is None or move not in work.legal_moves:
            break
        moves.append(move)
        work.push(move)
    if not moves:
        return ""
    try:
        return board.variation_san(moves)
    except Exception:  # noqa: BLE001 - malformed PVs must not break the insight
        return ""


def _pv_data(move: MoveAnalysis) -> dict[str, Any] | None:
    return move.multi_pvs[0] if move.multi_pvs else None


def _pv_player_wp(pv: dict[str, Any] | None) -> float | None:
    if not pv:
        return None
    return get_win_probability(pv.get("cp"), pv.get("mate"))


def _pv_eval_white(pv: dict[str, Any] | None, white_to_move: bool) -> str | None:
    if not pv:
        return None
    cp = pv.get("cp")
    mate = pv.get("mate")
    if not white_to_move:
        cp = -cp if cp is not None else None
        mate = -mate if mate is not None else None
    return _fmt_eval(cp, mate)


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
        *insight.main_line_san,
        *insight.best_line_san,
        *insight.second_best_line_san,
        *insight.refutation_san,
    ):
        if san:
            allowed_san.add(san)

    allowed_squares: set[str] = {
        piece["square"]
        for group in (
            insight.hung_pieces,
            insight.new_hung_pieces,
            insight.created_threats,
        )
        for piece in group
    }
    if insight.offered_piece:
        allowed_squares.add(insight.offered_piece["square"])
    for san in allowed_san:
        destination = _san_square(san)
        if destination:
            allowed_squares.add(destination)
    return allowed_san, allowed_squares


def insight_required_anchors(insight: MoveInsight) -> set[str]:
    """Concrete moves the explanation should cite when a line exists.

    The played move itself is deliberately excluded: merely repeating
    ``5.Nxe5`` is not an explanation. A punishment move, continuation or better
    alternative is the minimum useful anchor.
    """
    anchors: set[str] = set()
    for san in (
        *insight.main_line_san,
        *insight.refutation_san,
        insight.actual_reply_san,
        insight.best_move_san,
        insight.second_best_move_san,
    ):
        if san:
            anchors.add(san)
    anchors.discard(insight.san)
    return anchors


# ---------------------------------------------------------------------------
# Phase 0 — text renderers
# ---------------------------------------------------------------------------


def format_move_insight_for_llm(insight: MoveInsight) -> str:
    """Claim sheet handed to the LLM; the model only rewrites these claims."""
    return format_plan_for_llm(build_explanation_plan(insight))


def format_move_insight_offline(insight: MoveInsight) -> str:
    """
    Deterministic plain-English explanation. Always available, 0 network.

    The claim selector decides what is worth saying; this renderer only joins
    those claims. The same claims feed the LLM, so the fallback and the model
    cannot tell different stories.
    """
    return format_plan_offline(build_explanation_plan(insight))

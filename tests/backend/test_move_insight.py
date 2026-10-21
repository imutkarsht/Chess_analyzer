"""
Tests for the grounded move-insight builder (Coach feature, Phase 0).

Only the facts that the offline text, the LLM dossier and the reply validator
depend on are pinned here: the ply convention, what may be claimed as a
refutation, the mate reading, and the tone of the offline wording. Facts are
injected as the analyzer would have stored them, so no engine is needed.
"""

from __future__ import annotations

import chess
import pytest

from src.backend.analysis.tactics.insight import (
    build_move_insight,
    format_move_insight_for_llm,
    format_move_insight_offline,
    insight_allowed_tokens,
)
from src.backend.storage.models import GameMetadata, MoveAnalysis
from src.backend.storage.pgn_parser import PGNParser

METADATA = GameMetadata(
    white="White Player",
    black="Black Player",
    white_elo="1500",
    black_elo="1400",
    eco="C50",
    opening="Italian Game",
)
LEGAL = ["e4", "e5", "Nf3", "Nc6", "Bc4", "d6", "Nc3", "Bg4", "Nxe5"]
SCHOLARS = ["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6"]


def _replay(san_moves: list[str], upto: int) -> tuple[str, str]:
    """Return (fen_before, uci) of the move at index ``upto``."""
    board = chess.Board()
    for san in san_moves[:upto]:
        board.push_san(san)
    fen_before = board.fen()
    return fen_before, board.parse_san(san_moves[upto]).uci()


def _next_after(fen: str, san: str, pv: list[str], ply: int) -> MoveAnalysis:
    board = chess.Board(fen)
    return MoveAnalysis(
        move_number=ply // 2 + 1,
        ply=ply,
        san=san,
        uci=board.parse_san(san).uci(),
        fen_before=fen,
        classification="Best",
        multi_pvs=[{"pv": pv, "cp": 150, "mate": None}],
    )


@pytest.mark.parametrize(
    ("san_moves", "index", "square", "piece_name", "undefended", "numbered_san"),
    [
        (LEGAL, 8, "e5", "knight", True, "5.Nxe5"),  # 5.Nxe5 leaves the knight loose
        (SCHOLARS, 5, "f7", "pawn", False, "3...Nf6"),  # 3...Nf6 under-defends f7
    ],
)
def test_hanging_pieces(san_moves, index, square, piece_name, undefended, numbered_san):
    fen, uci = _replay(san_moves, index)
    played = MoveAnalysis(
        index // 2 + 1, index, san_moves[index], uci, fen, classification="Blunder"
    )
    insight = build_move_insight([played], 0, metadata=METADATA)

    hung = next(h for h in insight.hung_pieces if h["square"] == square)
    assert hung["piece_name"] == piece_name
    assert hung["is_undefended"] is undefended
    assert insight.numbered_san == numbered_san
    assert insight.fen_before == fen  # the explanation cache key is built on this


def test_refutation_and_motif_come_from_the_analysed_reply():
    """
    White plays a quiet h3; the analysed best reply Nf3+ forks king and queen.
    The refutation and the motif must come from moves[i+1], never from the
    played move's own PV.
    """
    fen = "4k3/8/8/4n3/8/8/3Q3P/6K1 w - - 0 1"
    board = chess.Board(fen)
    board.push_san("h3")

    played = MoveAnalysis(1, 0, "h3", "h2h3", fen, classification="Inaccuracy", best_move="d2d1")
    reply = _next_after(board.fen(), "Nf3+", ["e5f3", "g1h1"], ply=1)

    insight = build_move_insight([played, reply], 0, metadata=METADATA)
    assert insight.best_move_san == "Qd1"  # the missed alternative, from moves[i]
    assert insight.refutation_san[0] == "Nf3+"
    assert "fork" in insight.allowed_motifs
    assert insight.refutation_text == "1...Nf3+ Kh1"


@pytest.mark.parametrize(
    ("san_moves", "index", "reply_san", "reply_pv", "prefix"),
    [
        (LEGAL, 8, "Nxe5", ["c6e5"], "5..."),  # reply to White's 5th is Black's 5th
        (SCHOLARS, 5, "Qxf7#", ["h5f7"], "4."),  # reply to Black's 3rd is White's 4th
    ],
)
def test_refutation_prefix_follows_the_reply_move_number(
    san_moves, index, reply_san, reply_pv, prefix
):
    """
    5.Nxe5 is answered by 5...Bxd1, not 5.Bxd1: the reply is one ply later, so
    its move number must follow the reply, not the played move.
    """
    fen, uci = _replay(san_moves, index)
    played = MoveAnalysis(
        index // 2 + 1, index, san_moves[index], uci, fen, classification="Blunder"
    )
    board = chess.Board(fen)
    board.push_san(san_moves[index])
    reply = _next_after(board.fen(), reply_san, reply_pv, ply=index + 1)

    insight = build_move_insight([played, reply], 0, metadata=METADATA)
    assert insight.refutation_prefix == prefix
    assert insight.refutation_text == f"{prefix}{reply_san}"


def test_material_loss_via_see():
    """Black wins the queen with Rxd2; SEE reports the 9-pawn loss."""
    fen = "3r2k1/8/8/8/8/8/3Q4/6K1 w - - 0 1"
    board = chess.Board(fen)
    board.push_san("Kh1")

    played = MoveAnalysis(1, 0, "Kh1", "g1h1", fen, classification="Blunder")
    reply = _next_after(board.fen(), "Rxd2", ["d8d2"], ply=1)

    insight = build_move_insight([played, reply], 0, metadata=METADATA)
    assert insight.material_loss_cp == 900
    assert any(h["square"] == "d2" and h["piece_name"] == "queen" for h in insight.hung_pieces)


@pytest.mark.parametrize(
    ("fen", "san", "ply", "mate_before", "best_san"),
    [
        ("7k/6pp/8/8/8/8/8/R6K w - - 0 1", "Ra2", 0, 1, "Ra8#"),
        ("r6k/7p/8/8/8/8/6PP/7K b - - 0 1", "Ra2", 1, -1, "Ra1#"),
    ],
)
def test_missed_mate_is_reported_with_the_best_move(fen, san, ply, mate_before, best_san):
    """A missed mate must be named as such, for either colour."""
    board = chess.Board(fen)
    played = MoveAnalysis(
        ply // 2 + 1,
        ply,
        san,
        board.parse_san(san).uci(),
        fen,
        classification="Blunder",
        eval_before_mate=mate_before,
        win_chance_before=1.0,
        win_chance_after=0.5,
        best_move="a1a8" if ply == 0 else "a8a1",
    )
    insight = build_move_insight([played], 0, metadata=METADATA)

    assert insight.missed_mate is True
    assert insight.best_move_san == best_san
    text = format_move_insight_offline(insight)
    assert "forced mate" in text
    assert best_san[:3] in text


def test_last_ply_has_no_refutation():
    fen, uci = _replay(LEGAL, 8)
    played = MoveAnalysis(5, 8, "Nxe5", uci, fen, classification="Blunder")
    insight = build_move_insight([played], 0, metadata=METADATA)

    assert insight.refutation_san == []
    assert insight.actual_reply_san is None
    assert "opponent's refutation" in format_move_insight_for_llm(insight).lower()


@pytest.mark.parametrize("unreliable", ["not_analysed", "wrong_position"])
def test_the_reply_is_not_trusted_without_analysis(unreliable):
    """No multi-PV, or a reply stored for another position, is not a refutation."""
    fen, uci = _replay(LEGAL, 8)
    played = MoveAnalysis(5, 8, "Nxe5", uci, fen, classification="Blunder")
    board = chess.Board(fen)
    board.push_san("Nxe5")
    reply = MoveAnalysis(
        5,
        9,
        "Bxd1",
        "g4d1",
        chess.Board().fen() if unreliable == "wrong_position" else board.fen(),
        classification="Blunder",
        multi_pvs=None if unreliable == "not_analysed" else [{"pv": ["g4d1"], "cp": 0}],
    )

    insight = build_move_insight([played, reply], 0, metadata=METADATA)
    assert insight.refutation_san == []
    assert insight.allowed_motifs == []


@pytest.mark.parametrize(
    ("fen", "uci", "index"),
    [
        (chess.STARTING_FEN, "e2e4", 99),  # index past the analysed moves
        ("not-a-fen", "e2e4", 0),
        ("", "e2e4", 0),
        ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1 extra", "e2e4", 0),
        (chess.STARTING_FEN, "d1h5", 0),  # illegal in the stored position
    ],
)
def test_bad_ingestion_input_returns_none(fen, uci, index):
    played = MoveAnalysis(1, 0, "e4", uci, fen, classification="Blunder")
    assert build_move_insight([played], index, metadata=METADATA) is None


def test_chess960_position_parses():
    board = chess.Board.from_chess960_pos(518)
    fen = board.fen()
    uci = sorted(m.uci() for m in board.legal_moves)[0]

    played = MoveAnalysis(
        1, 0, board.san(chess.Move.from_uci(uci)), uci, fen, classification="Good"
    )
    insight = build_move_insight([played], 0, metadata=METADATA, chess960=True)
    assert insight.uci == uci


NEGATIVE_WORDS = ("blunder", "mistake", "undefended", "you had a mate", "lose", "fell")


def _sound_insight(classification: str):
    fen = "3r2k1/8/8/8/8/8/3Q4/6K1 w - - 0 1"
    played = MoveAnalysis(
        1,
        0,
        "Qd1",
        "d2d1",
        fen,
        classification=classification,
        best_move="d2d1",
        eval_after_cp=30,
        win_chance_after=0.55,
    )
    return build_move_insight([played], 0, metadata=METADATA)


@pytest.mark.parametrize("classification", ["Best", "Excellent", "Good", "Book"])
def test_sound_moves_are_never_framed_negatively(classification):
    """The wording must agree with the classification badge (D12)."""
    text = format_move_insight_offline(_sound_insight(classification)).lower()
    assert not any(word in text for word in NEGATIVE_WORDS)


def test_a_sacrifice_is_framed_positively():
    fen, uci = _replay(LEGAL, 8)
    played = MoveAnalysis(
        5, 8, "Nxe5", uci, fen, classification="Brilliant", eval_after_cp=50, win_chance_after=0.6
    )
    insight = build_move_insight([played], 0, metadata=METADATA)
    text = format_move_insight_offline(insight)

    assert "strong move" in text
    assert "losing material" not in text
    assert "winning chances fell" not in text


@pytest.mark.parametrize("classification", ["Inaccuracy", "Mistake", "Miss", "Blunder"])
def test_problem_moves_state_a_concrete_reason(classification):
    fen, uci = _replay(LEGAL, 8)
    played = MoveAnalysis(5, 8, "Nxe5", uci, fen, classification=classification)
    text = format_move_insight_offline(build_move_insight([played], 0, metadata=METADATA))

    # must quantify the damage (win-chance drop) and name what was left loose
    assert "winning chances fell" in text
    assert "defended" in text  # "undefended" or "under-defended"


def test_allowed_tokens_cover_the_facts_only():
    """The reply validator is fed from these tokens, so invented ones must not leak in."""
    fen = "3r2k1/8/8/8/8/8/3Q4/6K1 w - - 0 1"
    board = chess.Board(fen)
    board.push_san("Kh1")
    played = MoveAnalysis(1, 0, "Kh1", "g1h1", fen, classification="Blunder", best_move="d2d4")
    reply = _next_after(board.fen(), "Rxd2", ["d8d2"], ply=1)

    allowed_san, allowed_squares = insight_allowed_tokens(
        build_move_insight([played, reply], 0, metadata=METADATA)
    )

    assert {"Kh1", "Qd4", "Rxd2"} <= allowed_san
    assert {"d2", "h1", "d4"} <= allowed_squares
    assert "Qh5" not in allowed_san
    assert "e5" not in allowed_squares


def test_dossier_is_grounded_and_has_no_meta_words():
    fen, uci = _replay(LEGAL, 8)
    played = MoveAnalysis(5, 8, "Nxe5", uci, fen, classification="Blunder")
    dossier = format_move_insight_for_llm(build_move_insight([played], 0, metadata=METADATA))
    lowered = dossier.lower()

    assert "stockfish" not in lowered and "engine" not in lowered
    assert "5.Nxe5" in dossier
    assert "1500" in dossier  # player Elo from the metadata (D10)
    assert "Write 2-3 sentences explaining Nxe5 to the white player." in dossier


@pytest.mark.parametrize(
    ("move_number", "expected"),
    [(0, "5.Nxe5"), (5, "5.Nxe5")],  # missing/incoherent numbers derive from the ply
)
def test_move_number_fallback_uses_the_ply(move_number, expected):
    fen, uci = _replay(LEGAL, 8)
    played = MoveAnalysis(move_number, 8, "Nxe5", uci, fen, classification="Blunder")
    insight = build_move_insight([played], 0, metadata=METADATA)

    assert insight.numbered_san == expected


def test_ply_convention_matches_the_pgn_parser():
    """
    ``MoveAnalysis.ply`` is the 0-based ``chess.Board.ply()`` read *before* the
    push, so it also indexes ``moves``. Every side, score sign and notation
    prefix in the insight hangs off that convention, so pin it to the parser
    rather than to a hand-built fixture that could encode the wrong guess.
    """
    pgn = (
        '[Event "t"]\n[White "A"]\n[Black "B"]\n[Result "1-0"]\n\n'
        "1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. O-O Nf6 1-0\n"
    )
    game = PGNParser.parse_pgn_text(pgn)[0]

    for index, move in enumerate(game.moves):
        assert move.ply == index  # ply == the index into ``moves``

        insight = build_move_insight(game.moves, index, metadata=METADATA)

        # The side to move in the stored position is the move's author.
        turn = chess.Board(move.fen_before).turn
        expected_side = "white" if turn == chess.WHITE else "black"
        assert insight.side == expected_side

        separator = "." if expected_side == "white" else "..."
        assert insight.numbered_san == f"{move.move_number}{separator}{move.san}"

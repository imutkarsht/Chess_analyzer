import chess

from src.backend.storage.historic_games import (
    HISTORIC_POSITIONS,
    HistoricPosition,
    get_historic_position_by_id,
    get_random_historic_position,
)


def test_historic_positions_count_and_uniqueness():
    """Verify that there are at least 20 historic games and each has a unique ID."""
    assert len(HISTORIC_POSITIONS) >= 20
    ids = [p.id for p in HISTORIC_POSITIONS]
    assert len(ids) == len(set(ids)), "All historic positions must have unique IDs"


def test_historic_position_validity_and_move_legality():
    """Every historic position has a legal FEN, matching turn, and legal famous move."""
    for pos in HISTORIC_POSITIONS:
        board = chess.Board(pos.fen)
        assert board.is_valid(), f"Position {pos.id} has an invalid chess board state"

        expected_turn = "White" if board.turn == chess.WHITE else "Black"
        assert pos.turn == expected_turn, f"Turn mismatch for {pos.id}"
        assert pos.flipped == (board.turn == chess.BLACK), f"Flipped mismatch for {pos.id}"

        legal_sans = [board.san(m) for m in board.legal_moves]
        assert pos.famous_move in legal_sans, (
            f"Move {pos.famous_move} is not legal in {pos.id}. Legal moves: {legal_sans[:5]}"
        )

        assert pos.title and len(pos.title) > 0
        assert pos.white and len(pos.white) > 0
        assert pos.black and len(pos.black) > 0
        assert pos.year > 0
        assert pos.blurb and len(pos.blurb) > 10


def test_get_random_historic_position():
    """Verify random retrieval returns a valid position from the collection."""
    pos = get_random_historic_position()
    assert isinstance(pos, HistoricPosition)
    assert pos in HISTORIC_POSITIONS


def test_get_historic_position_by_id():
    """Verify lookup by ID returns the correct position or None for unknown ID."""
    pos = get_historic_position_by_id("opera_1858")
    assert pos is not None
    assert pos.title == "The Opera Game"

    non_existent = get_historic_position_by_id("unknown_game_9999")
    assert non_existent is None

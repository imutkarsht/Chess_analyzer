import pytest

from src.backend.storage.game_history import GameHistoryManager
from src.backend.storage.models import GameAnalysis, GameMetadata


@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test_history.db"
    return str(db_path)


def test_save_and_get_game(temp_db):
    """Test saving and retrieving a game."""
    manager = GameHistoryManager(temp_db)

    metadata = GameMetadata(
        white="Player1", black="Player2", result="1-0", date="2023.10.01", event="Test", headers={}
    )
    game = GameAnalysis(game_id="test_id", metadata=metadata, moves=[], pgn_content="pgn")

    manager.save_game(game, "pgn")

    saved_game = manager.get_game("test_id")
    assert saved_game is not None
    assert saved_game["white"] == "Player1"

    all_games = manager.get_all_games()
    assert len(all_games) == 1


def test_delete_game(temp_db):
    """Test deleting a game."""
    manager = GameHistoryManager(temp_db)
    # ... setup game ...
    metadata = GameMetadata(
        white="Player1", black="Player2", result="1-0", date="2023.10.01", event="Test", headers={}
    )
    game = GameAnalysis(game_id="test_id", metadata=metadata, moves=[], pgn_content="pgn")
    manager.save_game(game, "pgn")

    manager.delete_game("test_id")
    assert manager.get_game("test_id") is None


def test_get_game_analysis(temp_db):
    """Test retrieving a game as a fully-hydrated GameAnalysis object."""
    from src.backend.storage.models import MoveAnalysis

    manager = GameHistoryManager(temp_db)
    metadata = GameMetadata(
        white="Carlsen",
        black="Nakamura",
        result="1-0",
        date="2024.01.01",
        event="World Blitz",
        headers={},
    )
    moves = [
        MoveAnalysis(
            move_number=1,
            ply=1,
            san="e4",
            uci="e2e4",
            fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            classification="Best",
        ),
        MoveAnalysis(
            move_number=1,
            ply=2,
            san="e5",
            uci="e7e5",
            fen_before="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            classification="Good",
        ),
    ]
    game = GameAnalysis(
        game_id="game_full_123",
        metadata=metadata,
        moves=moves,
        pgn_content="1. e4 e5 1-0",
    )
    manager.save_game(game, "1. e4 e5 1-0")

    retrieved = manager.get_game_analysis("game_full_123")
    assert retrieved is not None
    assert isinstance(retrieved, GameAnalysis)
    assert retrieved.metadata.white == "Carlsen"
    assert retrieved.metadata.black == "Nakamura"
    assert len(retrieved.moves) == 2
    assert retrieved.moves[0].san == "e4"
    assert retrieved.moves[0].classification == "Best"

    assert manager.get_game_analysis("non_existent_id") is None

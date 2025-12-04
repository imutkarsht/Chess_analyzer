import pytest
import os
from src.backend.game_history import GameHistoryManager
from src.backend.models import GameAnalysis, GameMetadata

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test_history.db"
    return str(db_path)

def test_save_and_get_game(temp_db):
    """Test saving and retrieving a game."""
    manager = GameHistoryManager(temp_db)
    
    metadata = GameMetadata(white="Player1", black="Player2", result="1-0", date="2023.10.01", event="Test", headers={})
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
    metadata = GameMetadata(white="Player1", black="Player2", result="1-0", date="2023.10.01", event="Test", headers={})
    game = GameAnalysis(game_id="test_id", metadata=metadata, moves=[], pgn_content="pgn")
    manager.save_game(game, "pgn")
    
    manager.delete_game("test_id")
    assert manager.get_game("test_id") is None

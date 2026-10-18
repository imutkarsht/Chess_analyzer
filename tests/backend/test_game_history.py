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


def test_get_games_for_users_and_stats(temp_db):
    """Test get_games_for_users and get_games_for_stats projection and limits."""
    manager = GameHistoryManager(temp_db)

    # Insert 3 games for Player1
    for i in range(3):
        meta = GameMetadata(
            white="Player1",
            black=f"Opponent{i}",
            result="1-0",
            date=f"2024.01.0{i + 1}",
            event="Tournament",
            headers={},
        )
        game = GameAnalysis(
            game_id=f"game_{i}",
            metadata=meta,
            moves=[],
            pgn_content="1. e4 1-0",
        )
        manager.save_game(game, "1. e4 1-0")

    # 1. Test get_games_for_users
    games = manager.get_games_for_users(["player1"])
    assert len(games) == 3

    limited_games = manager.get_games_for_users(["player1"], limit=2)
    assert len(limited_games) == 2

    # 2. Test get_games_for_stats returns full payload for backward-compatible statistics
    stats_games = manager.get_games_for_stats(["player1"])
    assert len(stats_games) == 3
    for g in stats_games:
        assert "summary_json" in g
        assert "moves_json" in g
        assert g["white"] == "Player1"

    # Empty usernames returns empty list
    assert manager.get_games_for_users([]) == []
    assert manager.get_games_for_stats([]) == []


def test_database_indexes_created(temp_db):
    """Verify that expected performance indexes exist."""
    import sqlite3

    GameHistoryManager(temp_db)
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}

    expected = {
        "idx_games_white_lower",
        "idx_games_black_lower",
        "idx_games_timestamp",
        "idx_games_speed",
        "idx_games_date",
        "idx_games_opening",
        "idx_games_source",
    }
    assert expected.issubset(indexes)


def test_legacy_tactics_backfill(temp_db):
    """Test that legacy games lacking hung_pieces_details in summary_json are backfilled automatically."""
    import json
    import sqlite3

    # Initialize DB first
    GameHistoryManager(temp_db)

    # Insert a legacy game row with moves_json and legacy summary_json (lacking hung_pieces_details)
    moves = [
        {"move_number": 1, "ply": 1, "san": "e4", "uci": "e2e4", "fen_before": ""},
        {"move_number": 1, "ply": 2, "san": "e5", "uci": "e7e5", "fen_before": ""},
    ]
    legacy_summary = {"white": {"accuracy": 80.0}, "black": {"accuracy": 75.0}}

    with sqlite3.connect(temp_db) as conn:
        conn.execute(
            """
            INSERT INTO games (id, white, black, result, moves_json, summary_json, speed_category)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy_game_1",
                "Hero",
                "Opponent",
                "1-0",
                json.dumps(moves),
                json.dumps(legacy_summary),
                "Blitz",
            ),
        )
        conn.commit()

    # Re-initialize GameHistoryManager to trigger _init_db and _backfill_legacy_tactics
    manager2 = GameHistoryManager(temp_db)
    saved = manager2.get_game("legacy_game_1")
    assert saved is not None
    summary = json.loads(saved["summary_json"])
    assert "tactics" in summary["white"]
    assert "hung_pieces_details" in summary["white"]["tactics"]

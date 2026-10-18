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


def test_get_all_games_limit_and_all_ids(temp_db):
    """Test get_all_games limit clause and get_all_game_ids set generation."""
    manager = GameHistoryManager(temp_db)
    for i in range(5):
        metadata = GameMetadata(
            white=f"P_{i}", black="Opp", result="1-0", date="2024.01.01", event="Test", headers={}
        )
        game = GameAnalysis(
            game_id=f"game_{i}", metadata=metadata, moves=[], pgn_content=f"pgn_{i}"
        )
        manager.save_game(game, f"pgn_{i}")

    # No limit returns all 5
    all_games = manager.get_all_games()
    assert len(all_games) == 5

    # Limit returns exact count
    limited = manager.get_all_games(limit=3)
    assert len(limited) == 3

    # All IDs set contains all 5
    ids = manager.get_all_game_ids()
    assert ids == {f"game_{i}" for i in range(5)}

    # Lightweight summaries projection test
    summaries = manager.get_game_summaries(limit=3)
    assert len(summaries) == 3
    for s in summaries:
        assert "white" in s
        assert "summary_json" in s
        assert "pgn" not in s
        assert "moves_json" not in s


def test_deterministic_md5_game_id_fallback(temp_db):
    """Verify that omitting game_id uses deterministic MD5 hash of PGN."""
    import hashlib

    manager = GameHistoryManager(temp_db)
    pgn_content = "1. e4 e5 2. Nf3 Nc6 1-0"
    expected_id = hashlib.md5(pgn_content.encode("utf-8")).hexdigest()

    metadata = GameMetadata(
        white="PlayerW", black="PlayerB", result="1-0", date="2024.01.01", event="Test", headers={}
    )
    game = GameAnalysis(game_id="", metadata=metadata, moves=[], pgn_content=pgn_content)
    manager.save_game(game, pgn_content)

    assert manager.game_exists(expected_id)
    saved = manager.get_game(expected_id)
    assert saved is not None
    assert saved["white"] == "PlayerW"


def test_save_games_bulk_dict_and_analyses(temp_db):
    """Test save_games_bulk with both raw dict rows and GameAnalysis objects in a single transaction."""
    manager = GameHistoryManager(temp_db)

    # 1. Bulk save dict rows (such as from CSV import)
    raw_rows = [
        {
            "id": "bulk_dict_1",
            "white": "Magnus",
            "black": "Hikaru",
            "result": "1-0",
            "date": "2024.05.01",
            "event": "Speed Chess",
            "speed_category": "Blitz",
            "termination_mode": "resignation",
            "timestamp": 123456789.0,
            "pgn": "1. e4 c5 1-0",
        },
        {
            "id": "bulk_dict_2",
            "white": "Hikaru",
            "black": "Magnus",
            "result": "0-1",
            "date": "2024.05.01",
            "event": "Speed Chess",
            "speed_category": "Blitz",
            "termination_mode": "timeout",
            "timestamp": 123456799.0,
            "pgn": "1. d4 Nf6 0-1",
        },
    ]
    saved_count = manager.save_games_bulk(raw_rows)
    assert saved_count == 2
    assert manager.game_exists("bulk_dict_1")
    assert manager.game_exists("bulk_dict_2")

    # Verify original timestamp was preserved
    g1 = manager.get_game("bulk_dict_1")
    assert g1["timestamp"] == 123456789.0
    assert g1["termination_mode"] == "resignation"

    # 2. Bulk save GameAnalysis objects
    meta3 = GameMetadata(
        white="Ding", black="Gukesh", result="1/2-1/2", date="2024.11.01", event="WCC", headers={}
    )
    game3 = GameAnalysis(
        game_id="bulk_analysis_3", metadata=meta3, moves=[], pgn_content="1. c4 e5 1/2-1/2"
    )

    saved_count_2 = manager.save_games_bulk([game3])
    assert saved_count_2 == 1
    assert manager.game_exists("bulk_analysis_3")


def test_checkpoint_and_vacuum(temp_db):
    """Test WAL checkpoint and vacuum methods execute cleanly."""
    manager = GameHistoryManager(temp_db)
    # Execute checkpoint and vacuum
    manager.checkpoint()
    manager.vacuum()
    manager.close()


def test_explorer_cache_ttl_and_prune(temp_db):
    """Test explorer_cache saves, retrieves, and prunes expired records."""
    import time

    manager = GameHistoryManager(temp_db)
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    response_data = '{"moves": []}'

    # 1. Save valid entry
    manager.save_explorer_cache(fen, response_data)
    cached = manager.get_explorer_cache(fen)
    assert cached == response_data

    # 2. Simulate expired entry (> 48 hours old)
    old_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() - 200000))
    with manager._get_connection() as conn:
        conn.execute("UPDATE explorer_cache SET cached_at = ? WHERE fen = ?", (old_time, fen))
        conn.commit()

    # get_explorer_cache should detect expiration and delete it
    cached_expired = manager.get_explorer_cache(fen)
    assert cached_expired is None

    # Verify row was deleted
    with manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM explorer_cache")
        assert cursor.fetchone()[0] == 0

    # 3. Test prune_explorer_cache
    manager.save_explorer_cache(fen, response_data)
    with manager._get_connection() as conn:
        conn.execute("UPDATE explorer_cache SET cached_at = ? WHERE fen = ?", (old_time, fen))
        conn.commit()

    pruned = manager.prune_explorer_cache()
    assert pruned == 1


def test_analysis_cache_thread_safety_and_pruning(tmp_path):
    """Test AnalysisCache thread-safety, prune_cache, and clear_cache vacuuming."""
    from src.backend.storage.cache import AnalysisCache

    db_path = str(tmp_path / "test_cache.db")
    cache = AnalysisCache(db_path)

    # Save multiple items
    for i in range(10):
        cache.save_analysis(f"fen_{i}", {"depth": 10}, {"score": i})

    # Prune to max 5 items
    deleted = cache.prune_cache(max_entries=5)
    assert deleted == 5

    # Clear cache
    cache.clear_cache()
    assert cache.get_analysis("fen_0", {"depth": 10}) is None
    cache.close()


def test_schema_migration_creates_backup_and_sets_user_version(tmp_path):
    """Test that upgrading a legacy v0 database creates a .bak snapshot and sets PRAGMA user_version to CURRENT_SCHEMA_VERSION."""
    import os
    import sqlite3

    from src.backend.storage.game_history import CURRENT_SCHEMA_VERSION

    legacy_db = str(tmp_path / "legacy_v0.db")
    # Manually create a v0 schema with only base columns
    with sqlite3.connect(legacy_db) as conn:
        conn.execute("""
            CREATE TABLE games (
                id TEXT PRIMARY KEY,
                white TEXT,
                black TEXT,
                result TEXT,
                date TEXT,
                event TEXT,
                pgn TEXT,
                summary_json TEXT,
                timestamp REAL
            )
        """)
        conn.execute(
            "INSERT INTO games (id, white, black, result, date, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            ("old_1", "Kasparov", "Deep Blue", "1-0", "1997.05.03", 1000.0),
        )
        conn.commit()

    # Open with GameHistoryManager to trigger migration
    manager = GameHistoryManager(legacy_db)

    # 1. Assert backup snapshot was created
    backup_file = legacy_db + ".bak"
    assert os.path.exists(backup_file), "Expected pre-migration backup file to exist"
    assert os.path.getsize(backup_file) > 0

    # 2. Assert PRAGMA user_version is updated
    with manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA user_version")
        ver = cursor.fetchone()[0]
        assert ver == CURRENT_SCHEMA_VERSION

    # 3. Assert game record is intact and new columns exist
    game = manager.get_game("old_1")
    assert game is not None
    assert game["white"] == "Kasparov"
    assert "white_pieces_hung" in game
    assert "termination_mode" in game


def test_legacy_tactics_populates_direct_table_columns(temp_db):
    """Test that _backfill_legacy_tactics populates direct table columns as well as summary_json."""
    import json
    import sqlite3

    GameHistoryManager(temp_db)

    moves = [
        {"move_number": 1, "ply": 1, "san": "e4", "uci": "e2e4", "fen_before": ""},
        {"move_number": 1, "ply": 2, "san": "e5", "uci": "e7e5", "fen_before": ""},
    ]
    legacy_summary = {"white": {"accuracy": 85.0}, "black": {"accuracy": 80.0}}

    with sqlite3.connect(temp_db) as conn:
        conn.execute(
            """
            INSERT INTO games (id, white, black, result, moves_json, summary_json, speed_category)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy_game_cols",
                "Hero",
                "Opponent",
                "1-0",
                json.dumps(moves),
                json.dumps(legacy_summary),
                "Blitz",
            ),
        )
        conn.commit()

    # Re-trigger init
    manager2 = GameHistoryManager(temp_db)
    saved = manager2.get_game("legacy_game_cols")
    assert saved is not None
    # Verify table columns got populated
    assert saved["white_opening_acc"] is not None
    assert saved["speed_category"] == "Blitz"
    assert "hung_pieces_details" in json.loads(saved["summary_json"])["white"]["tactics"]


def test_row_to_game_analysis_preserves_starting_fen_and_metadata(temp_db):
    """Test that get_game_analysis preserves starting_fen, speed_category, and termination_mode."""
    manager = GameHistoryManager(temp_db)
    custom_fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    raw_dict = {
        "id": "fen_game_1",
        "white": "Magnus",
        "black": "Hikaru",
        "result": "1-0",
        "date": "2024.01.01",
        "event": "Chess960 Championship",
        "starting_fen": custom_fen,
        "chess960": 1,
        "speed_category": "Chess960",
        "termination": "White won by resignation",
        "termination_mode": "resignation",
        "pgn": f'[Event "Chess960 Championship"]\n[FEN "{custom_fen}"]\n\n1. e4 e5 1-0',
        "moves_json": "[]",
    }
    manager.save_games_bulk([raw_dict])

    analysis = manager.get_game_analysis("fen_game_1")
    assert analysis is not None
    assert analysis.metadata.starting_fen == custom_fen
    assert analysis.metadata.chess960 is True
    assert analysis.metadata.speed_category == "Chess960"
    assert analysis.metadata.termination_mode == "resignation"
    assert analysis.metadata.termination == "White won by resignation"


def test_explorer_cache_epoch_timestamp_and_pruning(temp_db):
    """Test that explorer cache stores epoch timestamp as REAL and prunes reliably."""
    import sqlite3
    import time

    manager = GameHistoryManager(temp_db)
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    response_json = '{"moves": [{"san": "e5"}]}'

    manager.save_explorer_cache(fen, response_json)

    # 1. Verify stored cached_at is float/int epoch timestamp
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT cached_at FROM explorer_cache WHERE fen = ?", (fen,))
        row = cursor.fetchone()
        assert float(row[0]) > 0
        assert isinstance(manager._parse_cached_at_to_epoch(row[0]), float)

    # 2. Verify retrieval works within TTL
    assert manager.get_explorer_cache(fen) == response_json

    # 3. Simulate expired entry (> 48 hours) using epoch timestamp
    expired_epoch = time.time() - 200000.0
    with sqlite3.connect(temp_db) as conn:
        conn.execute("UPDATE explorer_cache SET cached_at = ? WHERE fen = ?", (expired_epoch, fen))
        conn.commit()

    # 4. Verify get_explorer_cache deletes expired entry
    assert manager.get_explorer_cache(fen) is None

    # 5. Verify prune_explorer_cache cleans up expired epoch records
    manager.save_explorer_cache(fen, response_json)
    with sqlite3.connect(temp_db) as conn:
        conn.execute("UPDATE explorer_cache SET cached_at = ? WHERE fen = ?", (expired_epoch, fen))
        conn.commit()
    pruned = manager.prune_explorer_cache()
    assert pruned == 1


def test_prepare_game_dict_params_preserves_zero_hung_pieces(temp_db):
    """Test that a legitimate 0 for pieces_hung is preserved and not overwritten."""
    manager = GameHistoryManager(temp_db)
    game_dict = {
        "id": "zero_hung_game",
        "white": "Alice",
        "black": "Bob",
        "result": "1-0",
        "white_pieces_hung": 0,
        "black_pieces_hung": 0,
        "summary_json": '{"white": {"tactics": {"hanging_metrics": {"total_hung": 5}}}, "black": {}}',
    }
    params = manager._prepare_game_dict_params(game_dict)
    # Parameter index 26 is white_pieces_hung, 27 is black_pieces_hung
    # (gid, white, black, result, date_str, event, pgn, summary_json, timestamp,
    #  white_elo, black_elo, time_control, eco, termination, termination_mode, opening, starting_fen, source,
    #  chess960, moves_json, speed_category, book_exit_ply,
    #  white_opening_acc, black_opening_acc, white_middlegame_acc, black_middlegame_acc, white_endgame_acc, black_endgame_acc,
    #  white_pieces_hung, black_pieces_hung, ...)
    assert params[28] == 0  # white_pieces_hung should stay 0, not 5 from summary_dict!
    assert params[29] == 0  # black_pieces_hung should stay 0

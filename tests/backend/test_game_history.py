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


def test_lichess_site_url_variants_update_one_history_row(temp_db):
    """Both Lichess Site spellings must resolve to the same stored game."""
    from src.backend.storage.pgn_parser import PGNParser

    manager = GameHistoryManager(temp_db)
    template = (
        '[Event "Rated Bullet game"]\n[Site "{site}"]\n'
        '[Date "2026.07.30"]\n[White "ImutKarsht"]\n[Black "sg-88"]\n'
        '[Result "1-0"]\n\n1. e4 e5 2. Nf3 Nc6 1-0'
    )
    for site in ("https://lichess.org/game/tr0UaqOe", "https://lichess.org/tr0UaqOe"):
        game = PGNParser.parse_pgn_text(template.format(site=site))[0]
        manager.save_game(game, game.pgn_content)

    games = manager.get_all_games()
    assert len(games) == 1
    assert games[0]["white"] == "ImutKarsht"


def test_schema_migration_merges_duplicate_lichess_rows(tmp_path):
    """Existing URL-spelling duplicates collapse into the analysed row."""
    import hashlib
    import json
    import sqlite3

    from src.backend.storage.pgn_parser import normalize_lichess_site_for_id

    db_path = str(tmp_path / "duplicates.db")
    GameHistoryManager(db_path).close()

    old_pgn = (
        '[Event "Rated Bullet game"]\n[Site "https://lichess.org/game/tr0UaqOe"]\n'
        '[Date "2026.07.30"]\n[White "ImutKarsht"]\n[Black "sg-88"]\n'
        '[Result "1-0"]\n\n1. e4 e5 2. Nf3 Nc6 1-0'
    )
    new_pgn = old_pgn.replace("/game/tr0UaqOe", "/tr0UaqOe")
    old_id = hashlib.md5(old_pgn.encode()).hexdigest()
    new_id = hashlib.md5(new_pgn.encode()).hexdigest()
    expected_id = hashlib.md5(normalize_lichess_site_for_id(new_pgn).encode()).hexdigest()

    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            "INSERT INTO games "
            "(id, white, black, result, date, pgn, summary_json, timestamp, ai_summary) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    old_id,
                    "ImutKarsht",
                    "sg-88",
                    "1-0",
                    "2026.07.30",
                    old_pgn,
                    json.dumps({"analysis_status": "completed", "analyzed_moves": 42}),
                    100.0,
                    None,
                ),
                (
                    new_id,
                    "ImutKarsht",
                    "sg-88",
                    "1-0",
                    "2026.07.30",
                    new_pgn,
                    json.dumps({"analysis_status": "not_started", "analyzed_moves": 0}),
                    200.0,
                    "Game report",
                ),
            ],
        )
        conn.execute("PRAGMA user_version = 3")
        conn.commit()

    manager = GameHistoryManager(db_path)

    games = manager.get_all_games()
    assert [game["id"] for game in games] == [expected_id]
    saved = manager.get_game(expected_id)
    assert json.loads(saved["summary_json"])["analyzed_moves"] == 42
    assert saved["ai_summary"] == "Game report"


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


def test_explorer_cache_ttl_epoch_storage_and_prune(temp_db):
    """Explorer cache round-trips, stores epoch timestamps, and prunes expired rows."""
    import sqlite3
    import time

    manager = GameHistoryManager(temp_db)
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    response_data = '{"moves": [{"san": "e5"}]}'

    manager.save_explorer_cache(fen, response_data)
    assert manager.get_explorer_cache(fen) == response_data

    # cached_at is stored as a numeric epoch, not a formatted string.
    with sqlite3.connect(temp_db) as conn:
        row = conn.execute(
            "SELECT cached_at FROM explorer_cache WHERE fen = ?", (fen,)
        ).fetchone()
    assert float(row[0]) > 0
    assert isinstance(manager._parse_cached_at_to_epoch(row[0]), float)

    # Expiry is detected and the row removed, whatever the stored representation.
    old_epoch = time.time() - 200_000.0
    with sqlite3.connect(temp_db) as conn:
        conn.execute("UPDATE explorer_cache SET cached_at = ? WHERE fen = ?", (old_epoch, fen))
        conn.commit()
    assert manager.get_explorer_cache(fen) is None
    with sqlite3.connect(temp_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM explorer_cache").fetchone()[0] == 0

    # Legacy formatted timestamps are still parsed and pruned by prune_explorer_cache.
    legacy = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(old_epoch))
    manager.save_explorer_cache(fen, response_data)
    with sqlite3.connect(temp_db) as conn:
        conn.execute("UPDATE explorer_cache SET cached_at = ? WHERE fen = ?", (legacy, fen))
        conn.commit()
    assert manager.prune_explorer_cache() == 1


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


def test_ai_summary_is_stored_on_the_game_and_survives_resaving(temp_db):
    """The generated report is a game attribute: reloading the game (or
    re-saving a resumed analysis) must not lose it."""
    manager = GameHistoryManager(temp_db)
    game = GameAnalysis(
        game_id="summary_game",
        metadata=GameMetadata(white="Alice", black="Bob", result="1-0"),
        pgn_content="1. e4 e5",
    )
    manager.save_game(game, game.pgn_content)
    assert manager.get_game_analysis("summary_game").ai_summary is None

    report = "Game Comment: Sharp\n\nSummary:\nA clean conversion."
    manager.save_ai_summary("summary_game", report)
    assert manager.get_game_analysis("summary_game").ai_summary == report

    reloaded = manager.get_game_analysis("summary_game")
    reloaded.summary = {"white": {"accuracy": 80.0}}
    manager.save_game(reloaded, reloaded.pgn_content, force_overwrite=True)
    assert manager.get_game_analysis("summary_game").ai_summary == report


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


def test_game_analysis_status_and_progress_properties():
    """Verify GameAnalysis status transitions, move counts, and unanalyzed index."""
    from src.backend.storage.models import MoveAnalysis

    # 1. Not started
    m1 = MoveAnalysis(move_number=1, ply=1, san="e4", uci="e2e4", fen_before="fen1")
    m2 = MoveAnalysis(move_number=1, ply=2, san="e5", uci="e7e5", fen_before="fen2")
    m3 = MoveAnalysis(move_number=2, ply=3, san="Nf3", uci="g1f3", fen_before="fen3")
    game = GameAnalysis(
        game_id="g1",
        metadata=GameMetadata(white="W", black="B", result="*"),
        moves=[m1, m2, m3],
    )
    assert game.status == "not_started"
    assert game.analyzed_moves_count == 0
    assert game.total_moves_count == 3
    assert game.first_unanalyzed_index == 0

    # 2. Paused (partial analysis)
    m1.eval_before_cp = 25
    m1.eval_after_cp = 30
    m1.classification = "Good"
    assert game.status == "paused"
    assert game.analyzed_moves_count == 1
    assert game.first_unanalyzed_index == 1

    # 3. Completed
    m2.eval_before_cp = 30
    m2.eval_after_cp = 15
    m2.classification = "Inaccuracy"
    m3.eval_before_cp = 15
    m3.eval_after_cp = 40
    m3.classification = "Best"
    game.summary = {"white": {"accuracy": 88.0}, "black": {"accuracy": 82.0}}
    assert game.status == "completed"
    assert game.analyzed_moves_count == 3
    assert game.first_unanalyzed_index == 3


def test_save_game_preserves_analyzed_progress_when_unanalyzed_loaded(temp_db):
    """Verify save_game preserves existing analyzed/paused games when unanalyzed copy is saved."""
    import json

    from src.backend.storage.models import MoveAnalysis

    manager = GameHistoryManager(temp_db)
    m1 = MoveAnalysis(
        move_number=1,
        ply=1,
        san="e4",
        uci="e2e4",
        fen_before="fen1",
        eval_before_cp=20,
        eval_after_cp=25,
        classification="Best",
    )
    m2 = MoveAnalysis(move_number=1, ply=2, san="e5", uci="e7e5", fen_before="fen2")
    game = GameAnalysis(
        game_id="game_preserve",
        metadata=GameMetadata(white="W", black="B", result="*"),
        moves=[m1, m2],
        summary={"analysis_status": "paused", "analyzed_moves": 1, "total_moves": 2},
    )

    # 1. Save paused analysis
    manager.save_game(game, "1. e4 e5 *", force_overwrite=True)
    saved = manager.get_game("game_preserve")
    saved_summary = json.loads(saved["summary_json"])
    assert saved_summary["analysis_status"] == "paused"
    assert saved_summary["analyzed_moves"] == 1

    # 2. Simulate loading raw unanalyzed PGN for the same game
    raw_m1 = MoveAnalysis(move_number=1, ply=1, san="e4", uci="e2e4", fen_before="fen1")
    raw_m2 = MoveAnalysis(move_number=1, ply=2, san="e5", uci="e7e5", fen_before="fen2")
    unanalyzed_game = GameAnalysis(
        game_id="game_preserve",
        metadata=GameMetadata(white="W", black="B", result="*"),
        moves=[raw_m1, raw_m2],
    )
    assert unanalyzed_game.status == "not_started"

    # Default save_game (force_overwrite=False) must NOT wipe the paused analysis
    manager.save_game(unanalyzed_game, "1. e4 e5 *", force_overwrite=False)
    persisted = manager.get_game("game_preserve")
    persisted_summary = json.loads(persisted["summary_json"])
    assert persisted_summary["analysis_status"] == "paused"
    assert persisted_summary["analyzed_moves"] == 1

    # 3. Explicit force_overwrite=True (e.g. reanalyze) CAN overwrite
    manager.save_game(unanalyzed_game, "1. e4 e5 *", force_overwrite=True)
    overwritten = manager.get_game("game_preserve")
    overwritten_summary = json.loads(overwritten["summary_json"])
    assert overwritten_summary["analysis_status"] == "not_started"
    assert overwritten_summary["analyzed_moves"] == 0


def test_clear_all_data_wipes_games_and_every_cache_table(temp_db):
    """Reset must not leave cached evaluations or explanations behind."""
    from src.backend.storage.cache import AnalysisCache
    from src.backend.storage.schema_constants import DATA_TABLES

    manager = GameHistoryManager(temp_db)
    manager.save_game(
        GameAnalysis(
            game_id="keep_me",
            metadata=GameMetadata(white="A", black="B", result="1-0"),
            pgn_content="1. e4 e5 1-0",
        ),
        "1. e4 e5 1-0",
    )
    manager.save_explorer_cache("fen_a", '{"moves": []}')
    manager.save_cached_profile("chesscom", "Hikaru", {"username": "Hikaru"})

    cache = AnalysisCache(temp_db)
    cache.save_analysis("fen_a", {"depth": 10, "multi_pv": 2}, {"score": 5})
    cache.set_explanation(
        explanation="Good move.",
        fen="fen_a",
        uci="e2e4",
        model="openai/gpt-oss-120b",
        lang_code="en",
        prompt_version=1,
    )
    cache.close()

    manager.clear_all_data()

    with manager._get_connection() as conn:
        for table in DATA_TABLES:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert count == 0, f"{table} still holds rows after a reset"


def test_explorer_cache_ttl_is_configurable_and_can_never_expire(temp_db):
    """The TTL override drives both lookup and pruning; ``None`` disables expiry."""
    import sqlite3
    import time

    from src.backend.storage.explorer_cache_repo import ExplorerCacheRepo

    GameHistoryManager(temp_db)  # create the schema the repo reads
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    payload = '{"moves": []}'

    def _age(row_fen: str, seconds: float) -> None:
        with sqlite3.connect(temp_db) as conn:
            conn.execute(
                "UPDATE explorer_cache SET cached_at = ? WHERE fen = ?",
                (time.time() - seconds, row_fen),
            )
            conn.commit()

    expiring = ExplorerCacheRepo(temp_db, ttl_seconds=3600)
    expiring.save_explorer_cache(fen, payload)
    _age(fen, 7200)
    assert expiring.get_explorer_cache(fen) is None

    never = ExplorerCacheRepo(temp_db, ttl_seconds=None)
    never.save_explorer_cache(fen, payload)
    _age(fen, 60 * 60 * 24 * 365)
    assert never.get_explorer_cache(fen) == payload
    assert never.prune_explorer_cache() == 0

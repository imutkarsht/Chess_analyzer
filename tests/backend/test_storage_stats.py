"""Storage usage report used by the Data & Storage page."""

from src.backend.models.game_info import GameInfo
from src.backend.storage.cache import AnalysisCache
from src.backend.storage.game_history import GameHistoryManager
from src.backend.storage.models import GameAnalysis, GameMetadata
from src.backend.storage.stats import StorageStats, collect_storage_stats

FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"


def _game(game_id: str = "game_1") -> GameAnalysis:
    return GameAnalysis(
        game_id=game_id,
        metadata=GameMetadata(white="White", black="Black", result="1-0"),
        pgn_content="1. e4 e5 1-0",
    )


def test_missing_database_reports_zero_without_creating_it(tmp_path):
    db_path = tmp_path / "analysis_cache.db"

    stats = collect_storage_stats(str(db_path), str(tmp_path / "openings.db"))

    assert stats == StorageStats(0, 0, 0, 0, 0, 0, 0, 0)
    assert db_path.exists() is False, "a report must never create an empty database"


def test_report_counts_every_store_and_its_file_sizes(tmp_path):
    db_path = str(tmp_path / "cache.db")
    openings_path = tmp_path / "openings.db"
    openings_path.write_bytes(b"x" * 32)

    history = GameHistoryManager(db_path)
    history.save_game(_game(), "1. e4 e5 1-0")
    history.save_explorer_cache(FEN, '{"moves": []}')
    history.save_cached_game(
        GameInfo(
            game_id="remote_1",
            source="lichess",
            white="A",
            black="B",
            result="1-0",
            date="2024-01-01",
            pgn="1. e4 1-0",
        )
    )

    cache = AnalysisCache(db_path)
    cache.save_analysis(FEN, {"depth": 10, "multi_pv": 2}, {"score": 12})
    cache.set_explanation(
        explanation="A good move.",
        fen=FEN,
        uci="e7e5",
        model="openai/gpt-oss-120b",
        lang_code="en",
        prompt_version=1,
    )
    cache.close()

    stats = collect_storage_stats(db_path, str(openings_path))

    assert stats.games == 1
    assert stats.analyses == 1
    assert stats.explanations == 1
    assert stats.api_cached_games == 1
    assert stats.explorer_positions == 1
    assert stats.openings_bytes == 32
    assert stats.db_bytes == (tmp_path / "cache.db").stat().st_size
    assert stats.db_bytes > 0

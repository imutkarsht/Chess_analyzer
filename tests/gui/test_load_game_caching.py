import datetime
import pytest
from src.backend.models.game_info import GameInfo
from src.backend.storage.game_history import GameHistoryManager
from src.backend.cache.api_cache import ApiGameCache

def test_game_info_to_from_dict():
    info = GameInfo(
        game_id="123",
        source="lichess",
        white="Magnus",
        black="Hikaru",
        result="1-0",
        date="2026-07-25",
        pgn="1. e4 e5 2. Nf3",
        white_elo="2850",
        black_elo="2820",
        time_class="blitz",
        move_count=2,
        opening="King's Pawn Game"
    )
    d = info.to_dict()
    assert d["game_id"] == "123"
    assert d["white"] == "Magnus"
    
    info2 = GameInfo.from_dict(d)
    assert info2.game_id == "123"
    assert info2.white == "Magnus"
    assert info2.move_count == 2

def test_cache_hits_and_misses(tmp_path):
    db_file = tmp_path / "test_cache.db"
    manager = GameHistoryManager(db_path=str(db_file))
    cache = ApiGameCache(manager)
    
    # Check cache miss and fetch trigger
    called = False
    def mock_fetch():
        nonlocal called
        called = True
        return {
            "pgn": "1. e4 e5 *",
            "white": "WhitePlayer",
            "black": "BlackPlayer"
        }
        
    res = cache.get_by_id("lichess", "game1", mock_fetch)
    assert called is True
    assert res.game_id == "game1"
    assert res.white == "WhitePlayer"
    
    # Check cache hit (does not trigger fetch)
    called_again = False
    def mock_fetch_again():
        nonlocal called_again
        called_again = True
        return {}
        
    res_hit = cache.get_by_id("lichess", "game1", mock_fetch_again)
    assert called_again is False
    assert res_hit.white == "WhitePlayer"

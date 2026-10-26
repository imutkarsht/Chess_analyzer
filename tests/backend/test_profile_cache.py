from src.backend.storage.game_history import GameHistoryManager
from src.backend.storage.profile_cache_repo import ProfileCacheRepo


def test_profile_cache_round_trip_ttl_and_avatar_preservation(tmp_path):
    manager = GameHistoryManager(str(tmp_path / "history.db"))
    repo = ProfileCacheRepo(manager.db_path, ttl_seconds=3600)
    profile = {
        "platform": "chesscom",
        "username": "Hikaru",
        "total_games": 10,
        "avatar": "https://images.chesscomfiles.com/avatar.png",
    }

    repo.save_profile(
        "chesscom",
        "Hikaru",
        profile,
        avatar_bytes=b"image-bytes",
        avatar_mime="image/png",
        avatar_url=profile["avatar"],
    )

    cached = repo.get_profile("chesscom", "hikaru")
    assert cached is not None
    assert cached.profile == profile
    assert cached.is_stale is False
    assert cached.avatar_bytes == b"image-bytes"
    assert cached.avatar_mime == "image/png"

    # A refresh that fails to download an avatar must keep the cached image.
    repo.save_profile("chesscom", "hikaru", {**profile, "total_games": 11})
    refreshed = repo.get_profile("chesscom", "HIKARU")
    assert refreshed.profile["total_games"] == 11
    assert refreshed.avatar_bytes == b"image-bytes"

    expired = ProfileCacheRepo(manager.db_path, ttl_seconds=0)
    assert expired.get_profile("chesscom", "hikaru").is_stale is True

    never = ProfileCacheRepo(manager.db_path, ttl_seconds=None)
    assert never.get_profile("chesscom", "hikaru").is_stale is False


def test_profile_cache_prune_and_clear(tmp_path):
    manager = GameHistoryManager(str(tmp_path / "history.db"))
    repo = ProfileCacheRepo(manager.db_path, ttl_seconds=None)
    repo.save_profile("lichess", "Magnus", {"username": "Magnus"})

    # max_age_days=0 puts the cutoff at "now", so the row is expired and the
    # cache stays bounded even if a user tries many usernames.
    assert repo.prune_profile_cache(max_age_days=0) == 1
    assert repo.get_profile("lichess", "Magnus") is None

    repo.save_profile("lichess", "Magnus", {"username": "Magnus"})
    assert repo.clear_profile_cache() == 1
    assert repo.get_profile("lichess", "Magnus") is None

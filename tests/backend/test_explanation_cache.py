"""
Tests for the Coach explanation cache (Phase 1).

The cache decides whether a position is ever sent to a provider twice, so the
key axes and the TTL are the only behaviour worth pinning here (D7).
"""

from __future__ import annotations

import pytest

from src.backend.storage.cache import AnalysisCache

FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
UCI = "e2e4"
KEY = {"fen": FEN, "uci": UCI, "model": "openai/gpt-oss-120b", "lang_code": "en", "prompt_version": 1}


@pytest.fixture
def cache(tmp_path):
    instance = AnalysisCache(str(tmp_path / "cache.db"))
    yield instance
    instance.close()


def _store(cache: AnalysisCache, text: str = "You lost the queen.", **overrides) -> None:
    cache.set_explanation(explanation=text, **(KEY | overrides))


def _read(cache: AnalysisCache, **overrides) -> str | None:
    return cache.get_explanation(**(KEY | overrides))


def test_round_trip_hit_and_miss(cache):
    assert _read(cache) is None
    _store(cache, "You lost the queen: 6...Qxd1 wins the rook.")
    assert _read(cache) == "You lost the queen: 6...Qxd1 wins the rook."


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("model", "openai/gpt-oss-20b"),
        ("lang_code", "fr"),
        ("prompt_version", 2),
        ("fen", "8/8/8/8/8/8/8/K6k w - - 0 1"),
        ("uci", "d2d4"),
    ],
)
def test_key_uniqueness_across_axes(cache, field, value):
    """A different model / language / prompt version / position is a separate entry."""
    _store(cache, "english gpt-oss-120b v1")
    assert _read(cache, **{field: value}) is None

    _store(cache, "variant", **{field: value})
    assert _read(cache, **{field: value}) == "variant"
    assert _read(cache) == "english gpt-oss-120b v1"  # the original entry is intact


def test_expired_entry_is_a_miss_and_removed(cache):
    _store(cache, "stale")
    # age the row instead of sleeping
    cache.conn.execute("UPDATE move_explanations SET created_at = 0")
    cache.conn.commit()

    assert _read(cache, max_age_days=30) is None
    assert cache.conn.execute("SELECT COUNT(*) FROM move_explanations").fetchone()[0] == 0


def test_prune_removes_only_expired_rows(cache):
    _store(cache, "fresh")
    _store(cache, "expired", uci="d2d4")
    cache.conn.execute("UPDATE move_explanations SET created_at = 0 WHERE move_uci = 'd2d4'")
    cache.conn.commit()

    assert cache.prune_explanations(max_age_days=30) == 1
    assert _read(cache) == "fresh"
    assert _read(cache, uci="d2d4") is None


def test_clear_cache_and_explanations_are_independent(cache):
    """Engine evaluations and LLM explanations have separate lifetimes."""
    _store(cache, "text")

    # Clearing evaluations must not throw away paid-for explanations.
    assert cache.clear_cache() == 0
    assert _read(cache) == "text"

    assert cache.clear_explanations() == 1
    assert _read(cache) is None

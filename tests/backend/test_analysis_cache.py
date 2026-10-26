"""Tests for depth-aware engine caching and cache maintenance."""

import sqlite3

import pytest

from src.backend.storage.cache import AnalysisCache
from src.constants import DEFAULT_ANALYSIS_CACHE_MAX_ENTRIES

FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
EXPLANATION = {
    "fen": FEN,
    "uci": "e2e4",
    "model": "openai/gpt-oss-120b",
    "lang_code": "en",
    "prompt_version": 1,
}


@pytest.fixture
def cache(tmp_path):
    instance = AnalysisCache(str(tmp_path / "cache.db"))
    yield instance
    instance.close()


def test_deeper_analysis_is_never_downgraded(cache):
    cache.save_analysis(FEN, {"depth": 10, "multi_pv": 2}, {"depth": 10})
    cache.save_analysis(FEN, {"depth": 8, "multi_pv": 2}, {"depth": 8})

    assert cache.get_analysis(FEN, {"depth": 8, "multi_pv": 2}) == {"depth": 10}
    assert cache.get_analysis(FEN, {"depth": 10, "multi_pv": 2}) == {"depth": 10}
    # Requesting more depth than cached must force a fresh engine search.
    assert cache.get_analysis(FEN, {"depth": 12, "multi_pv": 2}) is None

    cache.save_analysis(FEN, {"depth": 12, "multi_pv": 2}, {"depth": 12})
    assert cache.get_analysis(FEN, {"depth": 12, "multi_pv": 2}) == {"depth": 12}


def test_multi_pv_is_part_of_the_cache_key(cache):
    cache.save_analysis(FEN, {"depth": 10, "multi_pv": 1}, {"pv": 1})
    cache.save_analysis(FEN, {"depth": 10, "multi_pv": 3}, {"pv": 3})

    assert cache.get_analysis(FEN, {"depth": 10, "multi_pv": 1}) == {"pv": 1}
    assert cache.get_analysis(FEN, {"depth": 10, "multi_pv": 3}) == {"pv": 3}
    assert cache.get_analysis(FEN, {"depth": 10, "multi_pv": 2}) is None


def test_missing_depth_is_treated_as_zero(cache):
    cache.save_analysis(FEN, {"multi_pv": 2}, {"value": 1})

    assert cache.get_analysis(FEN, {"multi_pv": 2}) == {"value": 1}


def test_pruning_is_amortised_across_saves(cache, mocker):
    cache._PRUNE_INTERVAL = 2
    prune = mocker.patch.object(cache, "prune_cache")

    cache.save_analysis(FEN, {"depth": 1}, {})
    prune.assert_not_called()

    cache.save_analysis(FEN, {"depth": 2}, {})
    prune.assert_called_once_with(cache._configured_max_entries())


def test_configured_max_entries_clamps_and_falls_back(mocker):
    config_get = mocker.patch("src.utils.config.ConfigManager.get")
    config_get.return_value = "500"
    assert AnalysisCache._configured_max_entries() == 1_000

    config_get.return_value = 5_000
    assert AnalysisCache._configured_max_entries() == 5_000

    config_get.return_value = "not-a-number"
    assert AnalysisCache._configured_max_entries() == DEFAULT_ANALYSIS_CACHE_MAX_ENTRIES


def test_explanation_feedback_round_trip(cache):
    assert cache.set_explanation_feedback(**EXPLANATION, value=1) is False

    cache.set_explanation(**EXPLANATION, explanation="Play Nf3.")
    assert cache.get_explanation_feedback(**EXPLANATION) is None

    assert cache.set_explanation_feedback(**EXPLANATION, value=1) is True
    assert cache.get_explanation_feedback(**EXPLANATION) == 1

    assert cache.set_explanation_feedback(**EXPLANATION, value=None) is True
    assert cache.get_explanation_feedback(**EXPLANATION) is None


def test_blank_explanation_is_not_cached(cache):
    cache.set_explanation(**EXPLANATION, explanation="")

    assert cache.get_explanation(**EXPLANATION) is None
    assert cache.prune_explanations(max_age_days=None) == 0


def test_database_failures_degrade_to_cache_misses(cache, mocker):
    cache.conn.close()
    broken = mocker.Mock()
    broken.cursor.side_effect = sqlite3.OperationalError("disk I/O error")
    cache.conn = broken

    assert cache.get_explanation(**EXPLANATION) is None
    cache.set_explanation(**EXPLANATION, explanation="text")
    assert cache.get_explanation_feedback(**EXPLANATION) is None
    assert cache.set_explanation_feedback(**EXPLANATION, value=1) is False
    assert cache.prune_explanations(max_age_days=30) == 0
    assert cache.prune_cache() == 0
    assert cache.clear_cache() == 0
    assert cache.clear_explanations() == 0

"""
Unit tests for StatsWorker filtering and statistical aggregation.
"""

import time

from src.gui.metrics.workers import StatsWorker


def make_dummy_game(
    game_id="1",
    white="PlayerA",
    black="PlayerB",
    result="1-0",
    speed="Blitz",
    chess960=0,
    source="chess.com",
    ts=None,
    summary=None,
    termination=None,
    termination_mode=None,
):
    return {
        "id": game_id,
        "white": white,
        "black": black,
        "result": result,
        "speed_category": speed,
        "chess960": chess960,
        "source": source,
        "timestamp": ts or time.time(),
        "summary_json": summary,
        "termination": termination,
        "termination_mode": termination_mode,
    }


def test_stats_worker_color_filter():
    """Test filtering games by user color."""
    games = [
        make_dummy_game(
            "g1", white="PlayerA", black="Opponent1", result="1-0"
        ),  # user is white, won
        make_dummy_game(
            "g2", white="Opponent2", black="PlayerA", result="1-0"
        ),  # user is black, lost
        make_dummy_game(
            "g3", white="PlayerA", black="Opponent3", result="0-1"
        ),  # user is white, lost
    ]
    usernames = ["PlayerA"]

    # All Colors
    w_all = StatsWorker(games, usernames, color_filter="All Colors")
    stats_all = w_all._calculate_stats()
    assert stats_all["total"] == 3
    assert stats_all["wins"] == 1
    assert stats_all["losses"] == 2

    # White only
    w_white = StatsWorker(games, usernames, color_filter="White")
    stats_white = w_white._calculate_stats()
    assert stats_white["total"] == 2
    assert stats_white["wins"] == 1
    assert stats_white["losses"] == 1

    # Black only
    w_black = StatsWorker(games, usernames, color_filter="Black")
    stats_black = w_black._calculate_stats()
    assert stats_black["total"] == 1
    assert stats_black["wins"] == 0
    assert stats_black["losses"] == 1


def test_stats_worker_format_filter():
    """Test filtering by speed category and Chess960."""
    games = [
        make_dummy_game("g1", speed="Blitz", chess960=0),
        make_dummy_game("g2", speed="Rapid", chess960=0),
        make_dummy_game("g3", speed="Blitz", chess960=1),  # Freestyle
    ]
    usernames = ["PlayerA"]

    # Blitz filter (should only match standard Blitz, not 960)
    w_blitz = StatsWorker(games, usernames, format_filter="Blitz")
    s_blitz = w_blitz._calculate_stats()
    assert s_blitz["total"] == 1
    assert s_blitz["term_counts"] is not None

    # Rapid filter
    w_rapid = StatsWorker(games, usernames, format_filter="Rapid")
    assert w_rapid._calculate_stats()["total"] == 1

    # Freestyle (Chess960) filter
    w_960 = StatsWorker(games, usernames, format_filter="Freestyle (Chess960)")
    assert w_960._calculate_stats()["total"] == 1


def test_stats_worker_source_filter():
    """Test filtering by game source platform."""
    games = [
        make_dummy_game("g1", source="chesscom"),
        make_dummy_game("g2", source="lichess"),
        make_dummy_game("g3", source="file"),
    ]
    usernames = ["PlayerA"]

    w_cc = StatsWorker(games, usernames, source_filter="Chess.com")
    assert w_cc._calculate_stats()["total"] == 1

    w_li = StatsWorker(games, usernames, source_filter="Lichess")
    assert w_li._calculate_stats()["total"] == 1

    w_file = StatsWorker(games, usernames, source_filter="File")
    assert w_file._calculate_stats()["total"] == 1


def test_stats_worker_draw_term_counts():
    """Test draw terminations aggregation into draw_term_counts buckets."""
    games = [
        make_dummy_game("g1", result="1/2-1/2", termination_mode="threefold_repetition"),
        make_dummy_game("g2", result="1/2-1/2", termination_mode="stalemate"),
        make_dummy_game("g3", result="1/2-1/2", termination_mode="agreed_draw"),
        make_dummy_game("g4", result="1/2-1/2", termination_mode="timeout_insufficient"),
        make_dummy_game("g5", result="1/2-1/2", termination_mode="insufficient_material"),
        make_dummy_game("g6", result="1/2-1/2", termination_mode="fifty_moves"),
    ]
    worker = StatsWorker(games, ["PlayerA"])
    stats = worker._calculate_stats()
    assert stats["draws"] == 6
    draws = stats["draw_term_counts"]
    assert draws["3-Fold Repetition"] == 1
    assert draws["Stalemate"] == 1
    assert draws["Agreement"] == 1
    assert draws["Insufficient vs Timeout"] == 1
    assert draws["Insufficient Material"] == 1
    assert draws["50-Move Rule"] == 1


def test_stats_worker_time_stats():
    """Test format breakdown and time trouble aggregation in time_stats."""
    import json

    moves_bullet = json.dumps(
        [
            {
                "ply": 0,
                "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                "time_spent": 1.2,
                "time_left": 55.0,
                "classification": "Best",
                "is_book_move": True,
            },
            {
                "ply": 2,
                "fen_before": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
                "time_spent": 14.0,
                "time_left": 10.0,  # <= 15s in Bullet -> time trouble
                "classification": "Blunder",
                "is_book_move": False,
            },
        ]
    )

    games = [
        make_dummy_game("g1", white="PlayerA", speed="Bullet", result="1-0"),
        make_dummy_game(
            "g2", white="PlayerA", speed="Blitz", result="0-1", termination_mode="timeout"
        ),
    ]
    games[0]["moves_json"] = moves_bullet

    worker = StatsWorker(games, ["PlayerA"])
    stats = worker._calculate_stats()

    assert "time_stats" in stats
    ts = stats["time_stats"]
    assert ts["has_clock_data"] is True
    assert ts["total_timed_moves"] == 2
    assert "Bullet" in ts["formats"]
    assert "Blitz" in ts["formats"]

    bullet_fmt = ts["formats"]["Bullet"]
    assert bullet_fmt["games"] == 1
    assert bullet_fmt["wins"] == 1
    assert bullet_fmt["losses"] == 0

    blitz_fmt = ts["formats"]["Blitz"]
    assert blitz_fmt["games"] == 1
    assert blitz_fmt["wins"] == 0
    assert blitz_fmt["losses"] == 1
    assert blitz_fmt["time_losses"] == 1

    trouble = ts["time_trouble"]
    assert trouble["normal_moves"] == 1
    assert trouble["normal_blunders"] == 0
    assert trouble["trouble_moves"] == 1
    assert trouble["trouble_blunders"] == 1
    assert trouble["total_time_losses"] == 1

"""
Unit tests for StatsWorker filtering and statistical aggregation.
"""

import json
import time

import chess

from src.backend.analysis.metrics_aggregator import MetricsAggregator
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


def test_stats_worker_advantage_conversion_and_rates():
    """Test aggregation of advantage conversion, throws, comebacks, and calculated rates."""
    import json

    # Game 1: Converted advantage (White had +350 cp, won 1-0)
    g1_moves = json.dumps(
        [
            {
                "ply": 0,
                "san": "e4",
                "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                "eval_before_cp": 350,
                "win_chance_before": 0.85,
                "win_chance_after": 0.85,
                "classification": "Best",
                "is_book_move": False,
            }
        ]
    )

    # Game 2: Thrown lead (White had +400 cp, lost 0-1)
    g2_moves = json.dumps(
        [
            {
                "ply": 0,
                "san": "d4",
                "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                "eval_before_cp": 400,
                "win_chance_before": 0.90,
                "win_chance_after": 0.90,
                "classification": "Best",
                "is_book_move": False,
            }
        ]
    )

    # Game 3: Comeback win (White was at -350 cp, won 1-0)
    g3_moves = json.dumps(
        [
            {
                "ply": 0,
                "san": "Nf3",
                "fen_before": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                "eval_before_cp": -350,
                "win_chance_before": 0.10,
                "win_chance_after": 0.10,
                "classification": "Best",
                "is_book_move": False,
            }
        ]
    )

    games = [
        make_dummy_game("g1", white="PlayerA", result="1-0"),
        make_dummy_game("g2", white="PlayerA", result="0-1"),
        make_dummy_game("g3", white="PlayerA", result="1-0"),
    ]
    games[0]["moves_json"] = g1_moves
    games[1]["moves_json"] = g2_moves
    games[2]["moves_json"] = g3_moves

    worker = StatsWorker(games, ["PlayerA"])
    stats = worker._calculate_stats()

    assert "advantage_stats" in stats
    adv = stats["advantage_stats"]
    assert adv["had_winning_advantage"] == 2  # g1 and g2
    assert adv["converted_advantage"] == 1  # g1
    assert adv["thrown_losses"] == 1  # g2
    assert adv["conversion_rate"] == 50.0  # 1 of 2
    assert adv["throw_rate"] == 50.0  # 1 of 2

    assert adv["had_losing_position"] == 1  # g3
    assert adv["comeback_drawn_or_won"] == 1  # g3
    assert adv["comeback_wins"] == 1  # g3
    assert adv["comeback_rate"] == 100.0  # 1 of 1


def test_metrics_aggregator_build_coach_dossier():
    """Test generating a structured coaching dossier from aggregated stats."""
    from src.backend.analysis.metrics_aggregator import MetricsAggregator

    # 1. Empty stats
    empty_dossier = MetricsAggregator.build_coach_dossier({"total": 0})
    assert "No analyzed games available" in empty_dossier

    # 2. Populated stats
    sample_stats = {
        "total": 10,
        "wins": 6,
        "draws": 1,
        "losses": 3,
        "win_rate": 60.0,
        "avg_accuracy": 82.5,
        "clean_games": 3,
        "clean_games_pct": 30.0,
        "phase_stats": {
            "accuracies": {"opening": 88.0, "middlegame": 80.0, "endgame": 75.0},
            "blunders": {"opening": 1, "middlegame": 4, "endgame": 2},
        },
        "advantage_stats": {
            "had_winning_advantage": 5,
            "converted_advantage": 4,
            "thrown_losses": 1,
            "squandered_draws": 0,
            "conversion_rate": 80.0,
            "had_losing_position": 3,
            "comeback_drawn_or_won": 1,
            "comeback_wins": 1,
            "comeback_draws": 0,
            "comeback_rate": 33.3,
        },
        "hanging_stats": {
            "total_hung": 2,
            "by_piece": {"pawn": 1, "knight": 0, "bishop": 0, "rook": 1, "queen": 0},
            "opponent_hanging_captured": 4,
            "opponent_hanging_missed": 1,
        },
        "tactical_themes": {"fork": 5, "pin": 3, "skewer": 1},
        "brilliancies": [{"san": "Qh5"}],
        "time_stats": {
            "has_clock_data": True,
            "overall_avg_time": 12.4,
            "phase_pace": {
                "opening": {"avg_time": 4.5},
                "middlegame": {"avg_time": 16.2},
                "endgame": {"avg_time": 11.0},
            },
            "time_trouble": {"panic_multiplier": 2.5, "total_time_losses": 1},
        },
        "detailed_openings": {
            "Sicilian Defense": {
                "name": "Sicilian Defense",
                "eco": "B20",
                "total": 4,
                "win_rate": 75.0,
                "avg_acc": 85.0,
            }
        },
    }

    dossier = MetricsAggregator.build_coach_dossier(sample_stats)
    assert "STUDENT CHESS PERFORMANCE DOSSIER" in dossier
    assert "Overall Win Rate: 60.0%" in dossier
    assert "Average Accuracy: 82.5%" in dossier
    assert "Conversion: 80.0%" in dossier
    assert "Comeback Rate: 33.3%" in dossier
    assert "Sicilian Defense (ECO B20)" in dossier
    assert "Undefended Pieces Dropped: 2" in dossier


def test_metrics_aggregator_drill_down():
    """Test that MetricsAggregator indexes occurrences for drill-down exploration."""
    moves = [
        {
            "ply": 1,
            "move_number": 1,
            "san": "Ba6",
            "uci": "f1a6",
            "fen_before": chess.STARTING_FEN,
            "eval_before_cp": 50,
            "eval_after_cp": -200,
            "win_chance_before": 0.55,
            "win_chance_after": 0.30,
            "classification": "Blunder",
            "is_book_move": False,
        },
        {
            "ply": 2,
            "move_number": 1,
            "san": "e5",
            "uci": "e7e5",
            "fen_before": "rnbqkbnr/pppppppp/B7/8/8/8/PPPPPPPP/RNBQK1NR b KQkq - 1 1",
            "eval_before_cp": -200,
            "win_chance_before": 0.30,
            "win_chance_after": 0.30,
            "classification": "Best",
            "is_book_move": False,
        },
    ]

    game = {
        "id": "drill_game_1",
        "white": "Hero",
        "black": "Rival",
        "black_elo": "1850",
        "result": "0-1",
        "date": "2026.10.18",
        "speed_category": "Blitz",
        "opening": "Van't Kruijs Opening",
        "moves_json": json.dumps(moves),
    }

    stats = MetricsAggregator.calculate_stats([game], ["Hero"])
    assert "drill_down" in stats

    # Blunders drill-down
    blunders = MetricsAggregator.get_drill_down_items(stats, "blunders")
    assert len(blunders) == 1
    b = blunders[0]
    assert b["game_id"] == "drill_game_1"
    assert b["opponent"] == "Rival"
    assert b["opponent_elo"] == "1850"
    assert b["san"] == "Ba6"
    assert b["classification"] == "Blunder"
    assert b["eval_drop"] == 250

    # Hung piece drill-down
    hung_all = MetricsAggregator.get_drill_down_items(stats, "hung_pieces")
    assert len(hung_all) == 1
    hung_bishops = MetricsAggregator.get_drill_down_items(stats, "hung_pieces", "bishop")
    assert len(hung_bishops) == 1
    hb = hung_bishops[0]
    assert hb["piece_name"] == "bishop"
    assert hb["square"] == "a6"
    assert hb["game_id"] == "drill_game_1"

    # Openings drill-down for Game 1
    vant_games = MetricsAggregator.get_drill_down_items(stats, "openings", "Van't Kruijs Opening")
    assert len(vant_games) == 1
    assert vant_games[0]["game_id"] == "drill_game_1"
    assert vant_games[0]["is_game"] is True

    # Test clean_games drill-down with a 0-blunder game
    clean_game = {
        "id": "drill_game_2",
        "white": "Hero",
        "black": "Opponent",
        "result": "1-0",
        "date": "2026.10.18",
        "speed_category": "Rapid",
        "opening": "Sicilian Defense",
        "summary_json": json.dumps({"white": {"accuracy": 92.0, "Blunder": 0}}),
    }
    stats2 = MetricsAggregator.calculate_stats([game, clean_game], ["Hero"])
    clean_list = MetricsAggregator.get_drill_down_items(stats2, "clean_games")
    assert len(clean_list) == 1
    assert clean_list[0]["game_id"] == "drill_game_2"
    assert clean_list[0]["classification"] == "Clean Game"
    assert clean_list[0]["is_game"] is True

    # Case-insensitive opening lookup
    sicilian_games = MetricsAggregator.get_drill_down_items(stats2, "openings", "sicilian defense")
    assert len(sicilian_games) == 1
    assert sicilian_games[0]["game_id"] == "drill_game_2"


def test_drill_down_items_capping():
    """Verify that drill-down item collections are capped at MAX_DRILL_DOWN_ITEMS for scale."""
    from src.backend.analysis.metrics.constants import MAX_DRILL_DOWN_ITEMS

    # Create 600 clean games
    many_games = []
    for i in range(MAX_DRILL_DOWN_ITEMS + 100):
        many_games.append(
            {
                "id": f"clean_game_{i}",
                "white": "Hero",
                "black": "Opponent",
                "result": "1-0",
                "date": "2026.10.18",
                "speed_category": "Rapid",
                "opening": "Italian Game",
                "summary_json": json.dumps({"white": {"accuracy": 95.0, "Blunder": 0}}),
            }
        )

    stats = MetricsAggregator.calculate_stats(many_games, ["Hero"])
    clean_list = MetricsAggregator.get_drill_down_items(stats, "clean_games")
    # Clean games drill-down list should be capped at MAX_DRILL_DOWN_ITEMS
    assert len(clean_list) == MAX_DRILL_DOWN_ITEMS
    # But clean games summary counter aggregates all games
    assert stats["clean_games"] == MAX_DRILL_DOWN_ITEMS + 100
    italian_games = MetricsAggregator.get_drill_down_items(stats, "openings", "italian game")
    assert len(italian_games) == MAX_DRILL_DOWN_ITEMS

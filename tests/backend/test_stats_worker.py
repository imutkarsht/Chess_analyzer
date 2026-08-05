import json
import pytest
from src.gui.metrics.workers import StatsWorker


def make_summary(accuracy, acpl, white=None, black=None):
    """Builds a summary_json string matching the analyzer's per-side structure."""
    def side(overrides):
        data = {
            "Brilliant": 0, "Great": 0, "Best": 0, "Excellent": 0, "Good": 0,
            "Inaccuracy": 0, "Mistake": 0, "Blunder": 0, "Miss": 0, "Book": 0,
            "accuracy": accuracy, "acpl": acpl, "move_count": 10,
        }
        data.update(overrides or {})
        return data

    return json.dumps({
        "white": side(white),
        "black": side(black),
    })


def make_game(user="WhiteUser", opp="Opponent", result="1-0", timestamp=1,
              white_elo=None, black_elo=None, time_control=None,
              accuracy=None, acpl=None, moves_json=None, termination=None,
              opening=None, starting_fen=None, chess960=0, white=..., black=...,
              quality=None):
    """Builds a single game dict shaped like a games-table row."""
    if white is ...:
        white = user
    if black is ...:
        black = opp
    summary = None
    if accuracy is not None:
        summary = make_summary(accuracy, acpl or 0, white=quality, black=quality)
    return {
        "id": f"g{timestamp}",
        "white": white,
        "black": black,
        "result": result,
        "date": "2023.10.01",
        "event": "Test",
        "pgn": "",
        "summary_json": summary,
        "timestamp": timestamp,
        "white_elo": str(white_elo) if white_elo is not None else None,
        "black_elo": str(black_elo) if black_elo is not None else None,
        "time_control": time_control,
        "eco": "",
        "termination": termination,
        "opening": opening,
        "starting_fen": starting_fen,
        "source": "test",
        "chess960": chess960,
        "moves_json": json.dumps(moves_json) if moves_json is not None else None,
    }


def make_move(ply, uci, time_spent=None, time_left=None):
    return {"move_number": (ply + 1) // 2, "ply": ply, "san": "", "uci": uci,
            "fen_before": "", "time_spent": time_spent, "time_left": time_left}


def calculate(games, usernames=None):
    worker = StatsWorker(games, usernames or ["WhiteUser"])
    return worker._calculate_stats()


# ─────────────────────────────────────────────────────────────────────────
# ACPL
# ─────────────────────────────────────────────────────────────────────────
def test_avg_acpl():
    stats = calculate([
        make_game(accuracy=80, acpl=40, timestamp=1),
        make_game(accuracy=90, acpl=60, timestamp=2),
    ])
    assert stats["has_acpl"] is True
    assert stats["avg_acpl"] == 50


def test_acpl_missing_data():
    stats = calculate([make_game(accuracy=None, timestamp=1)])
    assert stats["has_acpl"] is False
    assert stats["avg_acpl"] == 0


# ─────────────────────────────────────────────────────────────────────────
# Opponent strength
# ─────────────────────────────────────────────────────────────────────────
def test_opponent_elo_aggregates():
    games = [
        make_game(white_elo=1500, black_elo=1420, timestamp=3),
        make_game(white_elo=1500, black_elo=1580, timestamp=2),
        make_game(white_elo=1500, black_elo=1490, timestamp=1),
    ]
    stats = calculate(games)
    assert stats["has_opponent_elo"] is True
    assert stats["avg_opponent_elo"] == pytest.approx(1496.666, abs=0.01)
    assert stats["max_opponent_elo"] == 1580


def test_opponent_elo_no_data():
    stats = calculate([make_game(timestamp=1)])
    assert stats["has_opponent_elo"] is False
    assert stats["avg_opponent_elo"] == 0
    assert stats["max_opponent_elo"] == 0


def test_best_win_tracks_strongest_defeated():
    games = [
        make_game(result="1-0", black_elo=1600, timestamp=1),   # win
        make_game(result="0-1", black_elo=1700, timestamp=2),   # loss (not counted)
        make_game(result="1-0", black_elo=1550, timestamp=3),   # win
    ]
    stats = calculate(games)
    assert stats["best_win"] == "1600"


# ─────────────────────────────────────────────────────────────────────────
# Streaks
# ─────────────────────────────────────────────────────────────────────────
def test_streaks():
    # Newest first: W, L, W, W  -> chronological: W, W, L, W
    games = [
        make_game(result="1-0", timestamp=4),
        make_game(result="0-1", timestamp=3),
        make_game(result="1-0", timestamp=2),
        make_game(result="1-0", timestamp=1),
    ]
    stats = calculate(games)
    assert stats["best_streak"] == 2
    assert stats["current_streak"] == 1


def test_streak_all_wins():
    games = [
        make_game(result="1-0", timestamp=3),
        make_game(result="1-0", timestamp=2),
        make_game(result="1-0", timestamp=1),
    ]
    stats = calculate(games)
    assert stats["best_streak"] == 3
    assert stats["current_streak"] == 3


# ─────────────────────────────────────────────────────────────────────────
# Time control buckets
# ─────────────────────────────────────────────────────────────────────────
def test_time_control_buckets():
    games = [
        make_game(time_control="60", timestamp=1),    # Bullet
        make_game(time_control="300", timestamp=2),   # Blitz
        make_game(time_control="600+3", timestamp=3), # Rapid
        make_game(time_control="1800", timestamp=4),  # Classical
    ]
    stats = calculate(games)
    assert stats["has_time_control"] is True
    buckets = stats["time_control_stats"]
    assert buckets["Bullet"]["total"] == 1
    assert buckets["Blitz"]["total"] == 1
    assert buckets["Rapid"]["total"] == 1
    assert buckets["Classical"]["total"] == 1


def test_time_control_ignores_missing():
    stats = calculate([make_game(time_control=None, timestamp=1)])
    assert stats["has_time_control"] is False


# ─────────────────────────────────────────────────────────────────────────
# Win/Loss termination modes
# ─────────────────────────────────────────────────────────────────────────
SCHOLARS_MATE = ["e2e4", "e7e5", "d1h5", "b8c6", "f1c4", "g8f6", "h5f7"]
FOOLS_MATE = ["f2f3", "e7e5", "g2g4", "d8h4"]


def test_win_by_checkmate_detected():
    games = [
        make_game(user="WhiteUser", black="Opp", result="1-0", timestamp=1,
                  moves_json=[make_move(i + 1, u) for i, u in enumerate(SCHOLARS_MATE)]),
    ]
    stats = calculate(games)
    assert stats["win_modes"]["Checkmate"] == 1
    assert stats["win_modes"]["Resignation"] == 0


def test_win_by_resignation_detected():
    games = [
        make_game(user="WhiteUser", result="1-0", timestamp=1,
                  termination="Black won by resignation"),
    ]
    stats = calculate(games)
    assert stats["win_modes"]["Resignation"] == 1
    assert stats["win_modes"]["Checkmate"] == 0


def test_loss_mode_recorded():
    # White user loses the fool's mate (black checkmates) -> loss by checkmate.
    games = [
        make_game(user="WhiteUser", black="Opp", result="0-1", timestamp=1,
                  moves_json=[make_move(i + 1, u) for i, u in enumerate(FOOLS_MATE)]),
    ]
    stats = calculate(games)
    assert stats["loss_modes"]["Checkmate"] == 1
    assert stats["loss_modes"]["Resignation"] == 0


# ─────────────────────────────────────────────────────────────────────────
# Move quality split
# ─────────────────────────────────────────────────────────────────────────
def test_quality_split_aggregates_good():
    quality = {"Brilliant": 1, "Great": 2, "Best": 3, "Inaccuracy": 1,
               "Mistake": 1, "Blunder": 1, "Miss": 1, "Book": 1}
    stats = calculate([
        make_game(accuracy=80, acpl=40, timestamp=1, quality=quality),
        make_game(accuracy=85, acpl=30, timestamp=2, quality=quality),
    ])
    q = stats["quality_counts"]
    assert q["Good"] == 12          # (1+2+3) * 2 games
    assert q["Inaccuracy"] == 2
    assert q["Mistake"] == 2
    assert q["Blunder"] == 2
    assert q["Miss"] == 2
    assert q["Book"] == 2


# ─────────────────────────────────────────────────────────────────────────
# Accuracy history ordering
# ─────────────────────────────────────────────────────────────────────────
def test_accuracy_history_sorted_by_timestamp():
    games = [
        make_game(accuracy=90, acpl=30, timestamp=5),  # newer
        make_game(accuracy=70, acpl=50, timestamp=1),  # older
    ]
    stats = calculate(games)
    assert stats["accuracy_history"] == [(1, 70.0), (5, 90.0)]


# ─────────────────────────────────────────────────────────────────────────
# Time management
# ─────────────────────────────────────────────────────────────────────────
def test_time_pressure_and_think_time():
    # White user: ply 1,3,5 are user moves.
    moves = [
        make_move(1, "e2e4", time_spent=20, time_left=270),
        make_move(2, "e7e5"),
        make_move(3, "g1f3", time_spent=30, time_left=15),  # pressured
        make_move(4, "b8c6"),
        make_move(5, "f1c4", time_spent=10, time_left=100),
    ]
    stats = calculate([
        make_game(accuracy=80, acpl=40, timestamp=1, moves_json=moves),
    ])
    assert stats["has_clock"] is True
    assert stats["avg_think_time"] == 20.0          # (20 + 30 + 10) / 3
    assert stats["time_pressure_pct"] == 33.33333333333333  # 1 of 3 with <30s

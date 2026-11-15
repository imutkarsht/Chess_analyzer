from types import SimpleNamespace

import pytest

from src.backend.analysis.metrics.game_time_management import (
    has_clock_data,
    is_disproportionate,
    is_time_trouble,
    starting_clock_seconds,
    summarize_game_time,
)


def _move(*, time_left=None, time_spent=None, classification="", raw_clk=""):
    return SimpleNamespace(
        time_left=time_left,
        time_spent=time_spent,
        classification=classification,
        raw_clk=raw_clk,
    )


@pytest.mark.parametrize(
    ("time_control", "expected"),
    [
        ("40/7200:1800+30", 7200),
        ("600+5", 600),
        ("?", None),
        ("0+5", None),
    ],
)
def test_starting_clock_seconds(time_control, expected):
    assert starting_clock_seconds(time_control) == expected


def test_clock_detection_thresholds_and_summary():
    ordinary = _move(time_left=30, time_spent=180, classification="Best")
    trouble = _move(time_left=29.9, time_spent=181, classification="Blunder")

    assert is_time_trouble(ordinary) is False
    assert is_time_trouble(trouble) is True
    assert is_disproportionate(ordinary, 600) is False
    assert is_disproportionate(trouble, 600) is True
    assert has_clock_data([ordinary, trouble]) is True
    assert has_clock_data([_move()]) is False
    assert has_clock_data([_move(raw_clk="00:00:29")]) is True

    summary = summarize_game_time([ordinary, trouble])
    assert summary.average_think_time == 180.5
    assert summary.blunder_think_time == 181
    assert summary.best_think_time == 180
    assert summary.time_trouble_blunders == 1
    assert summarize_game_time([_move()]).average_think_time is None


def test_summary_uses_existing_metrics_clock_data():
    summary = summarize_game_time(
        [_move(time_spent=999, classification="Blunder")],
        [
            {
                "total_timed_moves": 1,
                "total_time_spent": 400,
                "quality_time_spent": {"blunder": 40, "best": 0},
                "quality_timed_moves": {"blunder": 1, "best": 0},
                "trouble_blunders": 1,
            },
            {
                "total_timed_moves": 1,
                "total_time_spent": 200,
                "quality_time_spent": {"blunder": 0, "best": 80},
                "quality_timed_moves": {"blunder": 0, "best": 1},
                "trouble_blunders": 0,
            },
        ],
    )

    assert summary.average_think_time == 300
    assert summary.blunder_think_time == 40
    assert summary.best_think_time == 80
    assert summary.time_trouble_blunders == 1

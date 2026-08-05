import json
import pytest
from PyQt6.QtWidgets import QApplication

from src.gui.views.metrics import (
    ResultDistributionCard,
    EndingDistributionCard,
    MoveQualityCard,
    AccuracyTrendCard,
    WinLossModeCard,
    OpponentStrengthCard,
    TimeControlCard,
    TimeManagementCard,
)


def make_stats(overrides=None):
    stats = {
        'total': 10, 'wins': 6, 'losses': 3, 'draws': 1, 'win_rate': 60.0,
        'avg_accuracy': 78.5, 'best_win': "1500", 'best_streak': 3,
        'current_streak': 1, 'avg_acpl': 55.0, 'has_acpl': True,
        'term_counts': {"Checkmate": 4, "Resignation": 3, "Time": 2,
                        "Abandonment": 0, "Draw": 1, "Other": 0},
        'quality_counts': {"Good": 40, "Inaccuracy": 8, "Mistake": 4,
                           "Blunder": 2, "Miss": 1, "Book": 5},
        'accuracy_history': [(1.0, 70.0), (2.0, 80.0), (3.0, 85.0)],
        'avg_opponent_elo': 1480,
        'max_opponent_elo': 1650,
        'has_opponent_elo': True,
        'best_win': "1650",
        'time_control_stats': {
            "Bullet": {'wins': 1, 'draws': 0, 'losses': 1, 'total': 2},
            "Blitz": {'wins': 4, 'draws': 1, 'losses': 2, 'total': 7},
            "Rapid": {'wins': 1, 'draws': 0, 'losses': 0, 'total': 1},
            "Classical": {'wins': 0, 'draws': 0, 'losses': 0, 'total': 0},
        },
        'has_time_control': True,
        'win_modes': {"Checkmate": 3, "Resignation": 2, "Time": 1,
                      "Abandonment": 0, "Other": 0},
        'loss_modes': {"Checkmate": 1, "Resignation": 0, "Time": 2,
                       "Abandonment": 0, "Other": 0},
        'has_termination': True,
        'avg_think_time': 22.0,
        'time_pressure_pct': 35.0,
        'has_clock': True,
        'openings': {"Sicilian Defense": 4, "Italian Game": 3},
        'opening_wins': {"Sicilian Defense": 3, "Italian Game": 2},
        'color_stats': {
            'white': {'wins': 4, 'draws': 1, 'losses': 1, 'total': 6},
            'black': {'wins': 2, 'draws': 0, 'losses': 2, 'total': 4},
        },
    }
    if overrides:
        stats.update(overrides)
    return stats


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def build_all(app, stats):
    cards = [
        ResultDistributionCard(),
        EndingDistributionCard(),
        MoveQualityCard(),
        AccuracyTrendCard(),
        WinLossModeCard(),
        OpponentStrengthCard(),
        TimeControlCard(),
        TimeManagementCard(),
    ]
    for card in cards:
        card.set_stats(stats)
        card.show()
        app.processEvents()
        card.hide()
    return cards


def test_cards_build_with_full_stats(app):
    build_all(app, make_stats())


def test_cards_build_with_minimal_stats(app):
    stats = make_stats({
        'has_opponent_elo': False,
        'avg_opponent_elo': 0,
        'max_opponent_elo': 0,
        'best_win': "N/A",
        'has_time_control': False,
        'time_control_stats': {k: {'wins': 0, 'draws': 0, 'losses': 0, 'total': 0}
                               for k in ["Bullet", "Blitz", "Rapid", "Classical"]},
        'has_clock': False,
        'avg_think_time': 0,
        'time_pressure_pct': 0,
        'accuracy_history': [],
        'quality_counts': {"Good": 0, "Inaccuracy": 0, "Mistake": 0,
                           "Blunder": 0, "Miss": 0, "Book": 0},
    })
    build_all(app, stats)


def test_cards_can_be_refreshed_with_new_stats(app):
    cards = build_all(app, make_stats())
    for card in cards:
        card.set_stats(make_stats({'avg_acpl': 95.0, 'has_opponent_elo': True}))
        app.processEvents()

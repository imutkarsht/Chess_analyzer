"""
GUI tests for MetricsWidget and the filter toolbar.
"""

from unittest.mock import MagicMock

from src.gui.views.metrics_view import MetricsWidget


def test_metrics_view_setup_required(qapp, qtbot):
    """Test setup required view is shown when no usernames are configured."""
    mock_config = MagicMock()
    mock_config.get.return_value = ""

    mock_history = MagicMock()
    mock_history.get_games_for_users.return_value = []

    widget = MetricsWidget(mock_config, mock_history)
    qtbot.addWidget(widget)

    assert widget.filter_bar.isHidden()


def test_metrics_view_filter_toolbar(qapp, qtbot):
    """Test filter toolbar controls and reset functionality."""
    mock_config = MagicMock()
    mock_config.get.side_effect = lambda key, default="": "UserA" if "username" in key else default

    mock_history = MagicMock()
    mock_history.get_games_for_users.return_value = [
        {"id": "1", "white": "UserA", "black": "UserB", "result": "1-0", "speed_category": "Blitz"}
    ]

    widget = MetricsWidget(mock_config, mock_history)
    qtbot.addWidget(widget)
    widget.show()

    assert not widget.filter_bar.isHidden()
    assert widget.combo_color.count() == 3
    assert widget.combo_format.count() == 6

    # Change comboboxes
    widget.combo_color.setCurrentText("White")
    widget.combo_format.setCurrentText("Blitz")
    assert widget.combo_color.currentText() == "White"

    # Reset
    widget.reset_filters()
    assert widget.combo_color.currentText() == "All Colors"
    assert widget.combo_format.currentText() == "All Formats"

    widget.stop_worker()


def test_accuracy_trend_figure_generation():
    """Test create_accuracy_trend_figure with various data shapes."""
    from src.gui.metrics.charts import create_accuracy_trend_figure

    # 1. Empty data
    fig_empty = create_accuracy_trend_figure([])
    assert fig_empty is not None

    # 2. Single item
    fig_one = create_accuracy_trend_figure([82.5])
    assert fig_one is not None

    # 3. Small list with baseline
    fig_small = create_accuracy_trend_figure([70.0, 85.0, 92.0, 78.0, 88.0], baseline_acc=80.0)
    assert fig_small is not None

    # 4. Long list (e.g. 25 games)
    fig_long = create_accuracy_trend_figure([75.0 + (i % 15) for i in range(25)])
    assert fig_long is not None


def test_accuracy_trend_card_widget(qapp, qtbot):
    """Test AccuracyTrendCard rendering and segmented window switching."""
    from src.gui.views.metrics.accuracy_trend_card import AccuracyTrendCard

    card = AccuracyTrendCard()
    qtbot.addWidget(card)

    stats = {
        "avg_accuracy": 82.5,
        "accuracy_history": [88.0, 91.0, 75.0, 84.0, 79.0, 85.0, 94.0, 72.0, 80.0, 86.0, 83.0],
    }

    card.set_stats(stats)
    assert card.current_window == "20"
    assert card.content_widget is not None

    # Switch to 10G
    card.btn_10.click()
    assert card.current_window == "10"

    # Switch to All
    card.btn_all.click()
    assert card.current_window == "all"

    # Refresh styles
    card.refresh_styles()


def test_phase_performance_card_widget(qapp, qtbot):
    """Test PhasePerformanceCard rendering and empty state."""
    from src.gui.views.metrics.phase_performance_card import PhasePerformanceCard

    card = PhasePerformanceCard()
    qtbot.addWidget(card)

    # 1. Empty stats
    card.set_stats({})
    assert card.content_widget is not None

    # 2. Rich phase stats
    stats = {
        "total": 10,
        "phase_stats": {
            "accuracies": {
                "opening": 86.5,
                "middlegame": 74.2,
                "endgame": 68.0,
            },
            "blunders": {
                "opening": 0,
                "middlegame": 4,
                "endgame": 2,
            },
        },
    }
    card.set_stats(stats)
    assert card.content_widget is not None

    # Refresh styles
    card.refresh_styles()


def test_openings_list_card_widget(qapp, qtbot):
    """Test OpeningsListCard rendering, repertoire filtering, and sorting."""
    from src.gui.views.metrics.openings_list_card import OpeningsListCard

    card = OpeningsListCard()
    qtbot.addWidget(card)

    # 1. Empty stats
    card.set_stats({})
    assert card.content_widget is not None

    # 2. Rich detailed openings stats
    stats = {
        "detailed_openings": {
            "Vienna Game": {
                "name": "Vienna Game",
                "eco": "C25",
                "total": 4,
                "wins": 2,
                "draws": 1,
                "losses": 1,
                "as_white": 4,
                "as_black": 0,
                "white_wins": 2,
                "black_wins": 0,
                "win_rate": 50.0,
                "avg_acc": 75.0,
                "variations": ["Omaha Gambit", "Zhuravlev Countergambit"],
            },
            "Scotch Game": {
                "name": "Scotch Game",
                "eco": "C45",
                "total": 1,
                "wins": 1,
                "draws": 0,
                "losses": 0,
                "as_white": 0,
                "as_black": 1,
                "white_wins": 0,
                "black_wins": 1,
                "win_rate": 100.0,
                "avg_acc": 68.3,
                "variations": ["Alekhine Gambit"],
            },
        }
    }
    card.set_stats(stats)
    assert card.content_widget is not None
    # Switch sorting to Win Rate
    card.btn_sort_winrate.click()
    assert card.current_sort == "winrate"

    # Switch sorting to Most Played
    card.btn_sort_played.click()
    assert card.current_sort == "played"

    # Test dynamic title based on color filter
    card.set_stats({**stats, "filter_applied": {"color": "White"}})
    assert card.lbl_title.text() == "White Repertoire"

    card.set_stats({**stats, "filter_applied": {"color": "Black"}})
    assert card.lbl_title.text() == "Black Defenses"

    card.set_stats({**stats, "filter_applied": {"color": "All Colors"}})
    assert card.lbl_title.text() == "Opening Repertoire"

    # Refresh styles
    card.refresh_styles()

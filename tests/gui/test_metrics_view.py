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


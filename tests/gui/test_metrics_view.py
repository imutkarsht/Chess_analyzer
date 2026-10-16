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


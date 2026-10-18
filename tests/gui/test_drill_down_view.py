"""
GUI tests for DrillDownView, DrillDownItemWidget, and MetricsWidget integration.
"""

from unittest.mock import MagicMock

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton

from src.gui.metrics.drill_down_item import DrillDownItemWidget
from src.gui.metrics.drill_down_view import DrillDownView
from src.gui.views.metrics_view import MetricsWidget


def _create_sample_item(idx: int = 1) -> dict:
    return {
        "game_id": f"game_{idx}",
        "ply": 18,
        "move_number": 9,
        "san": "Qxd4??",
        "uci": "d8d4",
        "fen_before": "r1bqk2r/pppp1ppp/2n5/4p3/2B1n3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 5",
        "fen_after": "r1bqk2r/pppp1ppp/2n5/4p3/2B5/5N2/PPPP1PPP/RNBQK2R b KQkq - 0 5",
        "classification": "Blunder",
        "eval_before_cp": 120,
        "eval_after_cp": -350,
        "eval_drop": 470,
        "wp_drop": 45.2,
        "opponent": f"Grandmaster_{idx}",
        "opponent_elo": "2100",
        "result": "0-1",
        "user_color": "white",
        "speed_category": "Blitz",
        "opening": "Italian Game",
        "date": "2026.04.10",
    }


def test_drill_down_item_widget_rendering_and_click(qapp, qtbot):
    """Test DrillDownItemWidget properly displays position details and emits position_selected."""
    item = _create_sample_item(1)
    widget = DrillDownItemWidget(item)
    qtbot.addWidget(widget)

    assert widget.game_id == "game_1"
    # ply 18 -> move_index 17
    assert widget.move_index == 17

    # Test clicking the action button emits position_selected
    with qtbot.waitSignal(widget.position_selected) as blocker:
        btn_analyze = widget.findChild(QPushButton)
        assert btn_analyze is not None
        qtbot.mouseClick(btn_analyze, Qt.MouseButton.LeftButton)

    assert blocker.args == ["game_1", 17]

    # Test clicking anywhere on the card emits position_selected
    with qtbot.waitSignal(widget.position_selected) as blocker:
        qtbot.mouseClick(widget, Qt.MouseButton.LeftButton)

    assert blocker.args == ["game_1", 17]


def test_drill_down_item_widget_fallbacks(qapp, qtbot):
    """Test DrillDownItemWidget handles minimal/missing fields gracefully without crashing."""
    minimal_item = {
        "game_id": "game_min",
        "ply": 1,
        "san": "e4",
    }
    widget = DrillDownItemWidget(minimal_item)
    qtbot.addWidget(widget)

    assert widget.game_id == "game_min"
    assert widget.move_index == 0


def test_drill_down_view_empty_state(qapp, qtbot):
    """Test DrillDownView displays empty state when no items are provided."""
    view = DrillDownView()
    qtbot.addWidget(view)

    view.set_data("Dropped Queens", "Positions where a Queen was lost", [])

    assert view.lbl_title.text() == "Dropped Queens"
    assert view.lbl_subtitle.text() == "Positions where a Queen was lost"
    assert view.badge_count.text() == "0 Occurrences"
    assert view.pagination_bar.isHidden()

    # Test back button emits back_requested
    with qtbot.waitSignal(view.back_requested):
        qtbot.mouseClick(view.btn_back, Qt.MouseButton.LeftButton)


def test_drill_down_view_pagination(qapp, qtbot):
    """Test DrillDownView paginates occurrences and handles next/prev page buttons."""
    view = DrillDownView()
    qtbot.addWidget(view)

    # 25 items -> 3 pages with PAGE_SIZE = 10
    items = [_create_sample_item(i) for i in range(1, 26)]
    view.set_data("Blunders", "All blunders across games", items)

    assert view.badge_count.text() == "25 Occurrences"
    assert not view.pagination_bar.isHidden()
    assert view.current_page == 0
    assert not view.btn_prev.isEnabled()
    assert view.btn_next.isEnabled()
    assert "Page 1 of 3" in view.lbl_page.text()

    # Next page -> Page 2
    view.btn_next.click()
    assert view.current_page == 1
    assert view.btn_prev.isEnabled()
    assert view.btn_next.isEnabled()
    assert "Page 2 of 3" in view.lbl_page.text()

    # Next page -> Page 3
    view.btn_next.click()
    assert view.current_page == 2
    assert view.btn_prev.isEnabled()
    assert not view.btn_next.isEnabled()
    assert "Page 3 of 3" in view.lbl_page.text()

    # Prev page -> Page 2
    view.btn_prev.click()
    assert view.current_page == 1
    assert "Page 2 of 3" in view.lbl_page.text()

    # Theme refresh
    view.refresh_styles()


def test_drill_down_view_selection_forwarding(qapp, qtbot):
    """Test DrillDownView forwards position_selected from child items."""
    view = DrillDownView()
    qtbot.addWidget(view)

    items = [_create_sample_item(1)]
    view.set_data("Tactics", "Forks", items)

    child_item = view.findChild(DrillDownItemWidget)
    assert child_item is not None

    with qtbot.waitSignal(view.position_selected) as blocker:
        qtbot.mouseClick(child_item, Qt.MouseButton.LeftButton)

    assert blocker.args == ["game_1", 17]


def test_metrics_widget_drill_down_stacked_navigation(qapp, qtbot):
    """Test MetricsWidget switches cleanly between Dashboard and DrillDownView."""
    mock_config = MagicMock()
    mock_config.get.side_effect = lambda key, default="": "UserA" if "username" in key else default

    sample_item = _create_sample_item(1)
    mock_history = MagicMock()
    mock_history.get_games_for_users.return_value = [{"id": "game_1", "pgn": "1. e4 e5"}]
    mock_history.get_game_analysis.return_value = {"id": "game_1", "pgn": "1. e4 e5"}

    widget = MetricsWidget(mock_config, mock_history)
    qtbot.addWidget(widget)

    stats = {
        "total": 1,
        "win_rate": 100.0,
        "avg_accuracy": 85.0,
        "drill_down": {
            "blunders": [sample_item],
            "hung_pieces": {"queen": [sample_item], "all": [sample_item]},
            "opp_captured": {},
            "tactical_themes": {},
            "advantage": {},
        },
    }

    widget.show_dashboard(stats)

    # Initial state: on Dashboard (index 0), filter bar visible
    assert widget.stacked_widget.currentIndex() == 0
    assert not widget.filter_bar.isHidden()

    # Trigger drill-down for blunders
    widget._trigger_drill_down("blunders")

    assert widget.stacked_widget.currentIndex() == 1
    assert widget.header_bar.isHidden()
    assert widget.filter_bar.isHidden()
    assert "Blunders" in widget.drill_down_view.lbl_title.text()
    assert widget.drill_down_view.badge_count.text() == "1 Occurrence"

    # Click Back to Dashboard
    widget.drill_down_view.btn_back.click()

    assert widget.stacked_widget.currentIndex() == 0
    assert not widget.header_bar.isHidden()
    assert not widget.filter_bar.isHidden()

    # Trigger drill-down for specific piece
    widget._trigger_drill_down("hung_pieces", "queen")
    assert widget.stacked_widget.currentIndex() == 1
    assert "Queens" in widget.drill_down_view.lbl_title.text()

    # Test position selection emits game_selected with the loaded game object
    with qtbot.waitSignal(widget.game_selected) as blocker:
        widget.drill_down_view.position_selected.emit("game_1", 17)

    assert blocker.args[0] == {"id": "game_1", "pgn": "1. e4 e5"}
    assert blocker.args[1] == 17

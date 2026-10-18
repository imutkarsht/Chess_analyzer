"""
GUI tests for MetricsWidget and the filter toolbar.
"""

from unittest.mock import MagicMock

from PyQt6.QtWidgets import QFrame, QPushButton, QWidget

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

    # Test pagination with > 4 openings
    many_openings = {
        "detailed_openings": {
            f"Opening {i}": {
                "name": f"Opening {i}",
                "eco": f"A0{i}",
                "total": 10 - i,
                "wins": 5,
                "draws": 2,
                "losses": 3,
                "win_rate": 50.0,
                "avg_acc": 70.0,
            }
            for i in range(1, 8)
        }
    }
    card.set_stats(many_openings)
    assert hasattr(card, "lbl_page_info")
    assert card.lbl_page_info.text() == "Page 1 of 2"
    assert card.btn_next_page.isEnabled()
    assert not card.btn_prev_page.isEnabled()

    card.btn_next_page.click()
    assert card.current_page == 1
    assert card.lbl_page_info.text() == "Page 2 of 2"
    assert not card.btn_next_page.isEnabled()
    assert card.btn_prev_page.isEnabled()

    card.btn_prev_page.click()
    assert card.current_page == 0
    assert card.lbl_page_info.text() == "Page 1 of 2"

    # Refresh styles
    card.refresh_styles()


def test_time_management_card_widget(qapp, qtbot):
    """Test TimeManagementCard rendering, mode toggles, and fallback states."""
    from src.gui.views.metrics.time_management_card import TimeManagementCard

    card = TimeManagementCard()
    qtbot.addWidget(card)

    stats = {
        "time_stats": {
            "has_clock_data": True,
            "total_timed_moves": 120,
            "overall_avg_time": 4.5,
            "formats": {
                "Blitz": {
                    "name": "Blitz",
                    "games": 10,
                    "wins": 6,
                    "draws": 1,
                    "losses": 3,
                    "win_rate": 60.0,
                    "avg_accuracy": 78.4,
                    "avg_move_time": 4.2,
                    "time_losses": 0,
                    "timed_moves": 80,
                },
                "Bullet": {
                    "name": "Bullet",
                    "games": 5,
                    "wins": 2,
                    "draws": 1,
                    "losses": 2,
                    "win_rate": 40.0,
                    "avg_accuracy": 71.0,
                    "avg_move_time": 2.1,
                    "time_losses": 1,
                    "timed_moves": 40,
                },
            },
            "phase_pace": {
                "opening": {"avg_time": 1.5, "moves_count": 30},
                "middlegame": {"avg_time": 6.2, "moves_count": 60},
                "endgame": {"avg_time": 3.8, "moves_count": 30},
            },
            "quality_pace": {
                "best": {"avg_time": 3.4, "moves_count": 50},
                "blunder": {"avg_time": 7.8, "moves_count": 10},
                "other": {"avg_time": 4.1, "moves_count": 60},
            },
            "time_trouble": {
                "normal_moves": 105,
                "normal_blunders": 7,
                "normal_blunder_pct": 6.7,
                "trouble_moves": 15,
                "trouble_blunders": 3,
                "trouble_blunder_pct": 20.0,
                "panic_multiplier": 3.0,
                "total_time_losses": 1,
            },
        }
    }

    card.set_stats(stats)
    assert card.stack is not None
    assert card.current_mode == "formats"
    assert card.stack.currentWidget() == card.formats_page

    # Switch to Move Pace view
    card.btn_pace.click()
    assert card.current_mode == "pace"
    assert card.stack.currentWidget() == card.pace_page

    # Switch to Time Trouble view
    card.btn_trouble.click()
    assert card.current_mode == "trouble"
    assert card.stack.currentWidget() == card.trouble_page

    # Switch back to Formats view
    card.btn_formats.click()
    assert card.current_mode == "formats"
    assert card.stack.currentWidget() == card.formats_page

    # Test fallback state when no clock data exists
    stats_no_clock = {
        "time_stats": {
            "has_clock_data": False,
            "total_timed_moves": 0,
            "formats": {
                "Rapid": {
                    "name": "Rapid",
                    "games": 3,
                    "wins": 2,
                    "draws": 0,
                    "losses": 1,
                    "win_rate": 66.7,
                    "avg_accuracy": 81.0,
                    "avg_move_time": 0.0,
                    "time_losses": 0,
                    "timed_moves": 0,
                }
            },
        }
    }
    card.set_stats(stats_no_clock)
    assert card.stack is not None

    card.btn_pace.click()
    assert card.current_mode == "pace"
    assert card.stack.currentWidget() == card.pace_page

    # Refresh styles
    card.refresh_styles()


def test_hanging_pieces_card_widget(qapp, qtbot):
    """Test HangingPiecesCard rendering, piece breakdowns, and vigilance progress."""
    from src.gui.views.metrics.hanging_pieces_card import HangingPiecesCard

    card = HangingPiecesCard()
    qtbot.addWidget(card)

    # 1. Empty state
    card.set_stats({})
    assert card.content_widget is not None

    # 2. Rich hanging stats
    stats = {
        "total": 10,
        "hanging_stats": {
            "total_hung": 4,
            "hanging_blunders": 2,
            "by_piece": {"pawn": 1, "knight": 2, "bishop": 1, "rook": 0, "queen": 0},
            "opponent_hanging_captured": 5,
            "opponent_hanging_missed": 1,
            "captured_by_piece": {"pawn": 2, "knight": 1, "bishop": 1, "rook": 1, "queen": 0},
        },
    }
    card.set_stats(stats)
    assert card.content_widget is not None

    # Refresh styles
    card.refresh_styles()


def test_tactical_themes_card_widget(qapp, qtbot):
    """Test TacticalThemesCard rendering, motif breakdown grid, and hero pillars."""
    from src.gui.views.metrics.tactical_themes_card import TacticalThemesCard

    card = TacticalThemesCard()
    qtbot.addWidget(card)

    # 1. Empty state
    card.set_stats({})
    assert card.content_widget is not None

    # 2. Rich tactical stats
    stats = {
        "total": 15,
        "tactical_themes": {
            "fork": 8,
            "pin": 5,
            "skewer": 2,
            "discovered_attack": 4,
            "sacrifice": 1,
            "back_rank": 3,
        },
    }
    card.set_stats(stats)
    assert card.content_widget is not None

    # Refresh styles
    card.refresh_styles()


def test_brilliancy_hall_card_widget(qapp, qtbot):
    """Test BrilliancyHallCard rendering, strict 'Brilliant' filtering, and badges."""
    from src.gui.views.metrics.brilliancy_hall_card import BrilliancyHallCard

    card = BrilliancyHallCard()
    qtbot.addWidget(card)

    # 1. Empty state
    card.set_stats({})
    assert card.action_badge.text() == "0 Brilliancies"
    assert card.content_widget is not None

    # 2. Mixed classifications: strictly 'Brilliant' should be included
    stats = {
        "total": 5,
        "brilliancies": [
            {
                "game_id": "game1",
                "opponent": "GrandmasterX",
                "opponent_elo": "2450",
                "date": "2024-05-10",
                "user_color": "White",
                "san": "Bxh7+",
                "uci": "d3h7",
                "move_number": 19,
                "classification": "Brilliant",
                "opening_name": "French Defense: Classical",
            },
            {
                "game_id": "game2",
                "opponent": "TacticianY",
                "opponent_elo": "2300",
                "date": "2024-06-12",
                "user_color": "Black",
                "san": "Nf3+",
                "uci": "g5f3",
                "move_number": 27,
                "classification": "Great",  # Should be filtered out!
                "opening_name": "Sicilian Defense",
            },
            {
                "game_id": "game3",
                "opponent": "ChallengerZ",
                "opponent_elo": "",
                "date": "2024-07-01",
                "user_color": "White",
                "san": "Qxf7#",
                "uci": "f3f7",
                "move_number": 32,
                "classification": "Brilliant",
                "opening_name": "Italian Game",
            },
        ],
    }
    card.set_stats(stats)
    assert card.action_badge.text() == "2 Brilliancies"
    assert card.content_widget is not None

    # 3. Test click-to-load signal emission
    rows = card.findChildren(QFrame, "brilliancy_row")
    assert len(rows) == 2
    with qtbot.waitSignal(card.move_selected) as blocker:
        rows[0].clicked.emit()
    assert blocker.args == ["game1", 36]  # ply 19*2-1 or ply fallback

    # 4. Singular count test
    stats_single = {
        "brilliancies": [
            {
                "opponent": "PlayerA",
                "date": "2024-08-01",
                "san": "Rxd8+",
                "move_number": 15,
                "classification": "Brilliant",
            }
        ]
    }
    card.set_stats(stats_single)
    assert card.action_badge.text() == "1 Brilliancy"

    # 5. Pagination test with > 4 brilliancies
    many_brilliants = {
        "brilliancies": [
            {
                "game_id": f"g_{i}",
                "opponent": f"Opponent {i}",
                "san": f"Qx{i}#",
                "move_number": 20 + i,
                "classification": "Brilliant",
                "ply": 40 + i,
            }
            for i in range(1, 7)
        ]
    }
    card.set_stats(many_brilliants)
    assert hasattr(card, "lbl_page")
    assert card.lbl_page.text() == "Page 1 of 2"
    assert card.btn_next.isEnabled()
    assert not card.btn_prev.isEnabled()

    card.btn_next.click()
    assert card.current_page == 1
    assert card.lbl_page.text() == "Page 2 of 2"
    assert not card.btn_next.isEnabled()
    assert card.btn_prev.isEnabled()

    card.btn_prev.click()
    assert card.current_page == 0
    assert card.lbl_page.text() == "Page 1 of 2"

    # 6. Refresh styles
    card.refresh_styles()


def test_metrics_widget_brilliancy_selection_signal(qapp, qtbot):
    """Test clicking a brilliancy row in MetricsWidget emits game_selected with GameAnalysis and move_index."""
    mock_config = MagicMock()
    mock_config.get.return_value = "TestUser"

    mock_game = MagicMock()
    mock_history = MagicMock()
    mock_history.get_games_for_users.return_value = [{"id": "game_xyz"}]
    mock_history.get_game_analysis.return_value = mock_game

    widget = MetricsWidget(mock_config, mock_history)
    qtbot.addWidget(widget)

    stats = {
        "total": 1,
        "win_rate": 100.0,
        "avg_accuracy": 85.0,
        "brilliancies": [
            {
                "game_id": "game_xyz",
                "opponent": "Rival",
                "san": "Bxf7+",
                "ply": 21,
                "move_number": 11,
                "classification": "Brilliant",
            }
        ],
    }

    widget.show_dashboard(stats)
    assert hasattr(widget, "brilliancy_card")

    rows = widget.brilliancy_card.findChildren(QFrame, "brilliancy_row")
    assert len(rows) == 1

    with qtbot.waitSignal(widget.game_selected) as blocker:
        rows[0].clicked.emit()

    assert blocker.args[0] == mock_game
    assert blocker.args[1] == 20  # ply 21 -> index 20


def test_advantage_conversion_card_widget(qapp, qtbot):
    """Test AdvantageConversionCard rendering, conversion rate, thrown losses, and comebacks."""
    from src.gui.views.metrics.advantage_card import AdvantageConversionCard

    card = AdvantageConversionCard()
    qtbot.addWidget(card)

    # 1. Empty stats
    card.set_stats({})
    assert card.action_badge.text() == "Conversion Analytics"
    assert card.content_widget is not None

    # 2. Populated advantage metrics
    stats = {
        "total": 12,
        "advantage_stats": {
            "had_winning_advantage": 8,
            "converted_advantage": 6,
            "thrown_losses": 1,
            "squandered_draws": 1,
            "conversion_rate": 75.0,
            "throw_rate": 12.5,
            "had_losing_position": 4,
            "comeback_drawn_or_won": 2,
            "comeback_wins": 1,
            "comeback_draws": 1,
            "comeback_rate": 50.0,
        },
    }
    card.set_stats(stats)
    assert "75% Conversion • 1 Thrown" in card.action_badge.text()

    adv_pillar = card.findChild(QFrame, "adv_pillar")
    assert adv_pillar is not None

    cb_pillar = card.findChild(QFrame, "comeback_pillar")
    assert cb_pillar is not None

    ins_frame = card.findChild(QFrame, "conversion_insight_frame")
    assert ins_frame is not None

    # 3. Refresh styles
    card.refresh_styles()
    assert card.action_badge.text().startswith("75% Conversion")


def test_ai_coach_card_widget(qapp, qtbot):
    """Test AICoachCard initial state, structured insight population, and error handling."""
    from src.gui.views.metrics.ai_coach_card import AICoachCard

    mock_service = MagicMock()
    mock_service.get_model_name = MagicMock(return_value="groq/llama-3.3-70b-versatile")

    card = AICoachCard(mock_service)
    qtbot.addWidget(card)

    stats = {
        "total": 15,
        "win_rate": 66.7,
        "avg_accuracy": 84.0,
    }
    card.set_stats(stats)
    assert card.provider_badge.text() == "llama-3.3-70b-versatile"
    intro_container = card.findChild(QWidget, "coach_intro_container")
    assert intro_container is not None

    # 1. Populate structured insights
    structured_insights = (
        "### Strengths & Superpowers\n"
        "- **Endgame Precision**: You hold a 91% endgame accuracy across matches.\n"
        "- **Tactical Alertness**: You successfully executed 5 forks and 2 brilliancies.\n\n"
        "### Critical Leaks & Blindspots\n"
        "- **Piece Safety**: Dropped 3 undefended rooks in non-tactical positions.\n"
        "- **Time Trouble Panic**: Blunder rate spikes 2.8x under 20 seconds.\n\n"
        "### Personalized Training Prescription\n"
        "- **Piece Safety Drills**: Spend 15 minutes daily on undefended piece tactics.\n"
        "- **Clock Pacing**: Commit to a 5-second minimum think per move in complex middlegames.\n"
    )
    card.set_insights(structured_insights)

    assert card.get_insights() == structured_insights
    assert card.findChild(QWidget, "coach_sec_strengths") is not None
    assert card.findChild(QWidget, "coach_sec_leaks") is not None
    assert card.findChild(QWidget, "coach_sec_prescription") is not None

    # 2. Error handling test
    card._handle_insight_error("Error: LLM not configured. Go to Settings.")
    buttons = card.findChildren(QPushButton)
    assert any("Configure LLM" in b.text() for b in buttons)

    # 3. Refresh styles
    card.refresh_styles()

    # 4. Pulsing skeleton loader test
    card._show_loading_skeleton()
    assert card.findChild(QWidget, "coach_skeleton_container") is not None
    assert card._skeleton_anim is not None
    assert card._skeleton_anim.state() == card._skeleton_anim.State.Running
    card._stop_skeleton_anim()
    assert card._skeleton_anim is None


def test_metrics_widget_includes_advantage_and_ai_coach(qapp, qtbot):
    """Test MetricsWidget creates and renders AdvantageConversionCard and AICoachCard."""
    mock_config = MagicMock()
    mock_config.get.return_value = "PlayerA"

    mock_history = MagicMock()
    mock_history.get_games_for_users.return_value = [{"id": "g1"}]

    widget = MetricsWidget(mock_config, mock_history)
    qtbot.addWidget(widget)

    stats = {
        "total": 5,
        "win_rate": 80.0,
        "avg_accuracy": 82.0,
        "advantage_stats": {
            "had_winning_advantage": 3,
            "converted_advantage": 3,
            "thrown_losses": 0,
            "squandered_draws": 0,
            "conversion_rate": 100.0,
            "had_losing_position": 1,
            "comeback_drawn_or_won": 1,
            "comeback_wins": 1,
            "comeback_draws": 0,
            "comeback_rate": 100.0,
        },
    }

    widget.show_dashboard(stats)
    assert hasattr(widget, "advantage_card")
    assert hasattr(widget, "ai_coach_card")
    assert widget.advantage_card is not None
    assert widget.ai_coach_card is not None

    # Test persistence of insights across dashboard rebuilds
    test_insight = "### Strengths & Superpowers\n- **Vision**: Great eye."
    widget.ai_coach_card.insights_generated.emit(test_insight)
    assert widget.current_insights == test_insight

    # Re-render dashboard (simulating page switch / refresh)
    widget.show_dashboard(stats)
    assert widget.ai_coach_card.get_insights() == test_insight


def test_metrics_widget_smart_invalidation_and_filter_cache(qapp, qtbot):
    """Test that MetricsWidget dirty flag avoids redundant recalculations and caches filter states."""
    mock_config = MagicMock()
    mock_config.get.return_value = "PlayerA"

    mock_history = MagicMock()
    mock_history.get_games_for_users.return_value = [
        {
            "id": "g1",
            "white": "PlayerA",
            "black": "Opponent",
            "result": "1-0",
            "summary_json": '{"white": {"accuracy": 85.0}}',
            "speed_category": "Blitz",
        }
    ]

    widget = MetricsWidget(mock_config, mock_history)
    qtbot.addWidget(widget)

    # Wait for the background worker to finish calculating initial stats
    qtbot.waitUntil(lambda: not widget.needs_refresh, timeout=3000)
    assert widget.needs_refresh is False
    call_count = mock_history.get_games_for_users.call_count
    assert call_count >= 1

    # Calling refresh() without force when not dirty should be a no-op
    widget.refresh()
    assert mock_history.get_games_for_users.call_count == call_count

    # Calling mark_dirty() sets needs_refresh to True and clears filter cache
    widget.mark_dirty()
    assert widget.needs_refresh is True
    assert len(widget._filter_cache) == 0

    # Calling refresh() now re-fetches
    widget.refresh()
    assert mock_history.get_games_for_users.call_count == call_count + 1
    qtbot.waitUntil(lambda: not widget.needs_refresh, timeout=3000)

    # Calling refresh(force=True) re-fetches even if not dirty
    widget.refresh(force=True)
    assert mock_history.get_games_for_users.call_count == call_count + 2
    qtbot.waitUntil(lambda: not widget.needs_refresh, timeout=3000)

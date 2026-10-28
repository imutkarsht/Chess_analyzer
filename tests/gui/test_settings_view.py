from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Point the ConfigManager at a per-test directory."""
    monkeypatch.setattr("src.utils.config.get_user_data_dir", lambda: str(tmp_path))
    monkeypatch.delenv("LICHESS_TOKEN", raising=False)
    return tmp_path / "config.json"

def test_settings_view_clamping_without_token(qapp, qtbot, isolated_config):
    """Without Lichess API Token, game limit should be capped at 20."""
    from src.gui.views.settings_view import SettingsView

    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        view = SettingsView()
        qtbot.addWidget(view)

        # Set text inputs
        view.chesscom_input.setText("TestUserChessCom")
        view.lichess_input.setText("TestUserLichess")
        view.lichess_token_input.setText("")  # No token
        view.games_limit_input.setText("25")  # Exceeds max 20 without token

        # Toast replaces QMessageBox — mock the manager call
        with patch("src.gui.components.toast.ToastManager.warning") as mock_toast:
            view.save_usernames()
            mock_toast.assert_called_once()

        # Verify clamped value is written to config and UI input
        assert view.config_manager.get("api_games_limit") == 20
        assert view.games_limit_input.text() == "20"

def test_settings_view_clamping_with_token(qapp, qtbot, isolated_config):
    """With Lichess API Token, game limit up to 30 is accepted and above 30 is capped."""
    from src.gui.views.settings_view import SettingsView

    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        view = SettingsView()
        qtbot.addWidget(view)

        # 1. Test accepting value <= 30 (e.g. 25) with token
        view.lichess_token_input.setText("test_token")
        view.games_limit_input.setText("25")

        view.save_usernames()

        assert view.config_manager.get("api_games_limit") == 25
        assert view.games_limit_input.text() == "25"

        # 2. Test clamping value > 30 (e.g. 35) with token
        view.games_limit_input.setText("35")

        with patch("src.gui.components.toast.ToastManager.warning") as mock_toast:
            view.save_usernames()
            mock_toast.assert_called_once()

        assert view.config_manager.get("api_games_limit") == 30
        assert view.games_limit_input.text() == "30"

def test_save_all_settings_flow(qapp, qtbot, isolated_config):
    """Test the consolidated save_all_settings flow."""
    from src.gui.views.settings_view import SettingsView

    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        view = SettingsView()
        qtbot.addWidget(view)

        # Modify some UI fields
        view.path_input.setText("mock-stockfish")
        view.threads_input.setText("3")
        view.hash_input.setText("256")
        view.chesscom_input.setText("NewUserChessCom")
        view.lichess_input.setText("NewUserLichess")
        view.games_limit_input.setText("15")
        view.explain_trivial_checkbox.setChecked(True)
        view.explain_ttl_combo.setCurrentIndex(view.explain_ttl_combo.findData(7))

        # Mock validation and signals
        view.validate_engine_path = MagicMock()
        view.engine_path_changed = MagicMock()
        view.engine_settings_changed = MagicMock()
        view.llm_config_changed = MagicMock()
        view.usernames_changed = MagicMock()

        view.save_all_settings()

        # Verify changes are stored in the config
        assert view.config_manager.get("engine_path") == "mock-stockfish"
        assert view.config_manager.get("engine_threads") == 3
        assert view.config_manager.get("engine_hash") == 256
        assert view.config_manager.get("chesscom_username") == "NewUserChessCom"
        assert view.config_manager.get("lichess_username") == "NewUserLichess"
        assert view.config_manager.get("api_games_limit") == 15

        # Coach move explanations are part of the single save flow (D8)
        assert view.config_manager.get("explain_llm_for_trivial_moves") is True
        assert view.config_manager.get("explain_cache_ttl_days") == 7

        # Verify signals are emitted
        view.engine_path_changed.emit.assert_called_once_with("mock-stockfish")
        view.engine_settings_changed.emit.assert_called_once()
        view.llm_config_changed.emit.assert_called_once()
        view.usernames_changed.emit.assert_called_once()


def test_mode_toggle_keeps_the_coach_card_and_its_divider(qapp, qtbot, isolated_config):
    """The Coach card is Basic-tier even though its tuning rows are advanced."""
    from src.gui.views.settings_view import SettingsView

    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        view = SettingsView()
        qtbot.addWidget(view)

        divider = next(
            bar for bar, card in view._page_dividers if card is view.coach_settings
        )

        view.mode_toggle_btn.click()  # -> Advanced
        assert view.coach_settings.isHidden() is False
        assert divider.isHidden() is False

        view.mode_toggle_btn.click()  # -> Basic
        assert view.coach_settings.isHidden() is False
        assert divider.isHidden() is False
        assert view.coach_settings.temperature_input.parentWidget().isHidden() is True


def test_settings_nav_rail_stays_outside_the_scroll_area(qapp, qtbot, isolated_config):
    """The category rail must stay fixed while the options panel scrolls."""
    from src.gui.views.settings_view import SettingsView

    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        view = SettingsView()
        qtbot.addWidget(view)

        assert view.scroll_area.widget() is view.settings_panel
        assert view.scroll_area.isAncestorOf(view.category_rail) is False


def test_search_scrolls_to_the_matching_card(qapp, qtbot, isolated_config):
    """Searching jumps the options panel to the relevant card, not the top."""
    from src.gui.views.settings_view import SettingsView

    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        view = SettingsView()
        qtbot.addWidget(view)
        view.resize(1100, 600)
        view.show()
        qapp.processEvents()

        view.search_input.setText("sound effects")
        qapp.processEvents()

        assert view.category_list.currentItem().text() == "Appearance"
        assert view.scroll_area.verticalScrollBar().value() > 0


def test_analysis_page_groups_cards_and_mirrors_shortcuts(qapp, qtbot, isolated_config):
    """Analysis owns four cards, and the eval-panel shortcuts share their keys."""
    from src.gui.views.settings_view import SettingsView

    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        view = SettingsView()
        qtbot.addWidget(view)

        assert view._settings_pages["Analysis"] == [
            view.engine_settings,
            view.full_analysis_settings,
            view.live_analysis_settings,
            view.book_settings,
        ]

        emitted = []
        view.analysis_prefs_changed.connect(lambda: emitted.append(True))

        view.use_cache_checkbox.setChecked(False)
        assert view.config_manager.get("use_cache") is False
        assert emitted == [True]

        view.engine_lines_checkbox.setChecked(True)
        assert view.config_manager.get("engine_lines_enabled") is True
        assert emitted == [True, True]


def test_appearance_page_groups_five_cards(qapp, qtbot, isolated_config):
    """Appearance is split into theme, board, layout, dashboard, and sound cards."""
    from src.gui.views.settings_view import SettingsView

    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        view = SettingsView()
        qtbot.addWidget(view)

        assert view._settings_pages["Appearance"] == [
            view.theme_accent_settings,
            view.board_pieces_settings,
            view.window_layout_settings,
            view.dashboard_layout_settings,
            view.sound_settings,
        ]

        # Board annotation and volume rows are advanced-only.
        assert view.best_move_arrow_checkbox.parentWidget().isHidden() is True
        assert view.sound_volume_input.parentWidget().isHidden() is True

        view.mode_toggle_btn.click()  # -> Advanced
        assert view.best_move_arrow_checkbox.parentWidget().isHidden() is False
        assert view.sound_volume_input.parentWidget().isHidden() is False


def test_data_storage_page_groups_five_cards(qapp, qtbot, isolated_config):
    """Storage, retention, maintenance, backup, and reset are separate cards."""
    from src.gui.views.settings_view import SettingsView

    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        view = SettingsView()
        qtbot.addWidget(view)

        assert view._settings_pages["Data & Storage"] == [
            view.storage_settings,
            view.retention_settings,
            view.maintenance_settings,
            view.backup_settings,
            view.danger_settings,
        ]

        # Usage, maintenance, backup, and reset matter in both modes; only the
        # retention policy is advanced.
        assert view.storage_settings.isHidden() is False
        assert view.retention_settings.isHidden() is True
        retention_divider = next(
            bar for bar, card in view._page_dividers if card is view.retention_settings
        )
        assert retention_divider.isHidden() is True

        view.search_input.setText("backup")
        found = [
            view.category_list.item(row).text()
            for row in range(view.category_list.count())
        ]
        assert found == ["Data & Storage"]


def test_integrations_page_composes_three_cards_and_persists_network_options(
    qapp, qtbot, isolated_config
):
    """Integrations stays one page with three independently bound cards."""
    from src.gui.views.settings_view import SettingsView

    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        view = SettingsView()
        qtbot.addWidget(view)

        assert view._settings_pages["Integrations"] == [view.player_settings]
        assert [card.title() for card in view.player_settings.cards] == [
            "Chess.com",
            "Lichess",
            "Import & Network",
        ]

        view.player_settings.lichess_card.explorer_checkbox.setChecked(False)
        ttl_combo = view.player_settings.import_network_card.cache_ttl_combo
        ttl_combo.setCurrentIndex(ttl_combo.findData(168))

        view.player_settings.commit_all()

        assert view.config_manager.get("lichess_explorer_enabled") is False
        assert view.config_manager.get("profile_cache_ttl_hours") == 168


def test_save_emits_engine_signals_once_after_binder_autosave(qapp, qtbot, isolated_config):
    """Binder-driven cards persist on edit; Save must still notify the engine once."""
    from src.gui.views.settings_view import SettingsView

    with patch("src.utils.config.get_user_data_dir", return_value=str(isolated_config.parent)):
        view = SettingsView()
        qtbot.addWidget(view)

        view.path_input.setText("stockfish-new")
        view.path_input.editingFinished.emit()  # binder autosave
        assert view.config_manager.get("engine_path") == "stockfish-new"

        view.engine_path_changed = MagicMock()
        view.engine_settings_changed = MagicMock()

        with patch("src.gui.components.toast.ToastManager.success"):
            view.save_all_settings()
            view.engine_path_changed.emit.assert_called_once_with("stockfish-new")

            view.engine_path_changed.reset_mock()
            view.save_all_settings()
            view.engine_path_changed.emit.assert_not_called()


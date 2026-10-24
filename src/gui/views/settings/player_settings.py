"""Player accounts and API credentials settings."""

import os

from PyQt6.QtWidgets import QGroupBox, QVBoxLayout

from ...styles import Styles
from .components import SettingsBinder, SettingsForm, make_line_edit
from .modern_widgets import ModernSliderCounter, PasswordFieldWrapper


class PlayerSettings(QGroupBox):
    def __init__(self, config_manager, parent=None):
        super().__init__("Accounts and Credentials", parent)
        self.config_manager = config_manager
        self.setStyleSheet(Styles.get_group_box_style())
        self.setup_ui()

    def setup_ui(self):
        self.form = SettingsForm(self)
        wrapper = QVBoxLayout(self)
        wrapper.setContentsMargins(0, 8, 0, 0)
        wrapper.addWidget(self.form)

        self.binder = SettingsBinder(self.config_manager, self.form, self)

        self.chesscom_input = self.binder.add(
            "chesscom_username",
            make_line_edit("Chess.com username"),
        )
        self.lichess_input = self.binder.add(
            "lichess_username",
            make_line_edit("Lichess.org username"),
        )

        self.lichess_token_input = PasswordFieldWrapper(self)
        self.lichess_token_input.setMaximumWidth(420)
        self.binder.add("lichess_token", self.lichess_token_input)

        self.games_limit_input = ModernSliderCounter(
            1, 30, step=1, value=20, parent=self
        )
        self.binder.add(
            "api_games_limit",
            self.games_limit_input,
            hint="Maximum recent games to fetch at once.",
            width=None,
            on_change=self._on_games_limit_changed,
        )

    def current_token(self) -> str:
        return (
            self.lichess_token_input.text().strip()
            or self.config_manager.get("lichess_token", "")
            or os.getenv("LICHESS_TOKEN")
            or ""
        )

    def max_games_limit(self) -> int:
        """Token holders may fetch up to 30 games; anonymous users cap at 20."""
        return 30 if self.current_token() else 20

    def clamp_games_limit(self, value) -> int:
        try:
            limit = int(value)
        except (TypeError, ValueError):
            limit = 20
        return max(1, min(limit, self.max_games_limit()))

    def apply_games_limit(self, value) -> str:
        """Clamp, persist and sync the games limit; return a warning or ""."""
        try:
            requested = max(1, int(value))
        except (TypeError, ValueError):
            requested = 20
        limit = self.clamp_games_limit(requested)
        self.config_manager.set("api_games_limit", limit)
        if str(limit) != self.games_limit_input.text().strip():
            self.games_limit_input.setText(str(limit))
        if limit == requested:
            return ""
        if self.max_games_limit() == 30:
            return (
                "Games limit capped at 30 (the maximum allowed when a "
                "Lichess API token is configured)."
            )
        return (
            "Games limit capped at 20. Configure a Lichess API Token in the "
            "API Configuration section above to increase this limit to 30."
        )

    def _on_games_limit_changed(self, value):
        self.apply_games_limit(value)

    def reload_from_config(self):
        self.binder.load()

    def set_advanced_visible(self, visible):
        self.binder.set_advanced_visible(visible)

    def refresh_styles(self, *args, **kwargs):
        self.setStyleSheet(Styles.get_group_box_style())
        self.form.refresh_styles()
        for field in (self.chesscom_input, self.lichess_input):
            field.setStyleSheet(Styles.get_input_style())
        self.lichess_token_input.update_style()
        if hasattr(self.games_limit_input, "refresh_styles"):
            self.games_limit_input.refresh_styles()

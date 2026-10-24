"""Player accounts and API credentials settings."""

from PyQt6.QtWidgets import QGroupBox, QVBoxLayout

from ...styles import Styles
from .components import CONTROL_DEFAULT, SettingsForm, make_line_edit
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

        self.chesscom_input = make_line_edit("Chess.com username", CONTROL_DEFAULT)
        self.chesscom_input.setText(self.config_manager.get("chesscom_username", ""))
        self.form.add_row("Chess.com", self.chesscom_input)

        self.lichess_input = make_line_edit("Lichess.org username", CONTROL_DEFAULT)
        self.lichess_input.setText(self.config_manager.get("lichess_username", ""))
        self.form.add_row("Lichess.org", self.lichess_input)

        self.lichess_token_input = PasswordFieldWrapper(self)
        self.lichess_token_input.setMaximumWidth(420)
        self.lichess_token_input.setText(self.config_manager.get("lichess_token", ""))
        self.form.add_row(
            "Lichess token",
            self.lichess_token_input,
            hint="Optional token for Lichess imports and the online explorer.",
        )

        self.games_limit_input = ModernSliderCounter(
            1,
            30,
            step=1,
            value=self.config_manager.get("api_games_limit", 20),
            parent=self,
        )
        self.games_limit_input.setMaximumWidth(220)
        self.form.add_row(
            "Games fetch limit",
            self.games_limit_input,
            hint="Maximum recent games to fetch at once.",
            advanced=True,
            width=None,
        )

    def reload_from_config(self):
        self.chesscom_input.setText(self.config_manager.get("chesscom_username", ""))
        self.lichess_input.setText(self.config_manager.get("lichess_username", ""))
        self.lichess_token_input.setText(self.config_manager.get("lichess_token", ""))
        self.games_limit_input.setText(str(self.config_manager.get("api_games_limit", 20)))

    def set_advanced_visible(self, visible):
        self.form.set_advanced_visible(visible)

    def refresh_styles(self, *args, **kwargs):
        self.setStyleSheet(Styles.get_group_box_style())
        self.form.refresh_styles()
        for field in (self.chesscom_input, self.lichess_input):
            field.setStyleSheet(Styles.get_input_style())
        self.lichess_token_input.update_style()
        if hasattr(self.games_limit_input, "refresh_styles"):
            self.games_limit_input.refresh_styles()

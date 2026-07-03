"""
Player Usernames Settings group component.
"""
from PyQt6.QtWidgets import QGroupBox, QFormLayout, QLineEdit, QLabel
from PyQt6.QtGui import QIntValidator
from ...styles import Styles

class PlayerSettings(QGroupBox):
    def __init__(self, config_manager, parent=None):
        super().__init__("Player Usernames", parent)
        self.config_manager = config_manager
        self.setStyleSheet(Styles.get_group_box_style())
        
        self.setup_ui()

    def setup_ui(self):
        username_layout = QFormLayout(self)
        username_layout.setContentsMargins(20, 25, 20, 20)
        username_layout.setSpacing(15)
        username_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.chesscom_input = QLineEdit()
        self.chesscom_input.setText(self.config_manager.get("chesscom_username", ""))
        self.chesscom_input.setPlaceholderText("Chess.com Username")
        self.chesscom_input.setStyleSheet(Styles.get_input_style())
        
        self.lichess_input = QLineEdit()
        self.lichess_input.setText(self.config_manager.get("lichess_username", ""))
        self.lichess_input.setPlaceholderText("Lichess.org Username")
        self.lichess_input.setStyleSheet(Styles.get_input_style())

        lbl_chesscom = QLabel("Chess.com:")
        lbl_chesscom.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px; background: transparent;")
        
        lbl_lichess_user = QLabel("Lichess.org:")
        lbl_lichess_user.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px; background: transparent;")

        self.games_limit_input = QLineEdit()
        self.games_limit_input.setValidator(QIntValidator(1, 30, self.games_limit_input))
        self.games_limit_input.setText(str(self.config_manager.get("api_games_limit", 20)))
        self.games_limit_input.setPlaceholderText("Number of games to fetch (1-30)")
        self.games_limit_input.setStyleSheet(Styles.get_input_style())
        
        self._lbl_games_limit = QLabel("Games Fetch Limit:")
        self._lbl_games_limit.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px; background: transparent;")

        username_layout.addRow(lbl_chesscom, self.chesscom_input)
        username_layout.addRow(lbl_lichess_user, self.lichess_input)
        username_layout.addRow(self._lbl_games_limit, self.games_limit_input)

    def reload_from_config(self):
        self.chesscom_input.setText(self.config_manager.get("chesscom_username", ""))
        self.lichess_input.setText(self.config_manager.get("lichess_username", ""))
        self.games_limit_input.setText(str(self.config_manager.get("api_games_limit", 20)))

    def set_advanced_visible(self, visible):
        self._lbl_games_limit.setVisible(visible)
        self.games_limit_input.setVisible(visible)

    def refresh_styles(self, input_style, full_input_style):
        self.setStyleSheet(Styles.get_group_box_style())
        self.games_limit_input.setStyleSheet(input_style)
        self.chesscom_input.setStyleSheet(full_input_style)
        self.lichess_input.setStyleSheet(full_input_style)

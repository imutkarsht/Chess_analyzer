"""Board-width matchup header shown above the analysis board."""

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from src.gui.styles import Styles
from src.utils.config import ConfigManager


class BoardGameHeader(QFrame):
    """A flat, board-width line with players and the game result."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BoardGameHeader")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 8)
        layout.setSpacing(8)

        self.white_label = QLabel()
        self.vs_label = QLabel("vs")
        self.black_label = QLabel()
        self.result_label = QLabel()
        layout.addWidget(self.white_label)
        layout.addWidget(self.vs_label)
        layout.addWidget(self.black_label)
        layout.addStretch()
        layout.addWidget(self.result_label)

        self._white_name = ""
        self._black_name = ""
        self._result = ""

        self.refresh_styles()

    def set_info(
        self,
        white: str,
        white_elo,
        black: str,
        black_elo,
        result: str,
    ) -> None:
        self._white_name = white or ""
        self._black_name = black or ""
        self._result = (result or "").strip()
        self.white_label.setText(f"{white} ({white_elo})")
        self.black_label.setText(f"{black} ({black_elo})")
        self.result_label.setText(self._result)
        self.setToolTip(f"{white} ({white_elo}) vs {black} ({black_elo})  [{self._result}]")
        self.refresh_styles()

    def _saved_usernames(self) -> set[str]:
        config = ConfigManager()
        names = {
            str(config.get("chesscom_username", "") or "").strip().casefold(),
            str(config.get("lichess_username", "") or "").strip().casefold(),
        }
        names.discard("")
        return names

    def _user_side(self) -> str | None:
        """Which side the saved username played, if either name matches."""
        usernames = self._saved_usernames()
        if not usernames:
            return None
        if self._white_name.strip().casefold() in usernames:
            return "white"
        if self._black_name.strip().casefold() in usernames:
            return "black"
        return None

    def _result_color(self) -> str:
        """Result colour from the saved player's POV, accent when unknown."""
        result = self._result
        side = self._user_side()
        if side is None or result in ("", "*"):
            return Styles.COLOR_ACCENT
        if result in ("1/2-1/2", "½-½", "0.5-0.5"):
            return Styles.COLOR_RESULT_DRAW
        if result not in ("1-0", "0-1"):
            return Styles.COLOR_ACCENT

        white_won = result == "1-0"
        user_won = (white_won and side == "white") or (not white_won and side == "black")
        return Styles.COLOR_RESULT_WIN if user_won else Styles.COLOR_BLUNDER

    def refresh_styles(self) -> None:
        self.setStyleSheet(Styles.get_board_game_header_style())
        name_style = Styles.get_label_style(size=16, color=Styles.COLOR_TEXT_PRIMARY, weight=600)
        muted_style = Styles.get_label_style(size=14, color=Styles.COLOR_TEXT_SECONDARY, weight=500)
        self.white_label.setStyleSheet(name_style)
        self.black_label.setStyleSheet(name_style)
        self.vs_label.setStyleSheet(muted_style)
        self.result_label.setStyleSheet(
            Styles.get_label_style(size=16, color=self._result_color(), weight=700)
        )

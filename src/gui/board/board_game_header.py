"""Board-width matchup header shown above the analysis board."""

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from src.gui.styles import Styles


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

        self.refresh_styles()

    def set_info(
        self,
        white: str,
        white_elo,
        black: str,
        black_elo,
        result: str,
    ) -> None:
        self.white_label.setText(f"{white} ({white_elo})")
        self.black_label.setText(f"{black} ({black_elo})")
        self.result_label.setText(result)
        self.setToolTip(f"{white} ({white_elo}) vs {black} ({black_elo})  [{result}]")

    def refresh_styles(self) -> None:
        self.setStyleSheet(Styles.get_board_game_header_style())
        name_style = Styles.get_label_style(
            size=13, color=Styles.COLOR_TEXT_PRIMARY, weight=600
        )
        muted_style = Styles.get_label_style(
            size=11, color=Styles.COLOR_TEXT_SECONDARY, weight=500
        )
        self.white_label.setStyleSheet(name_style)
        self.black_label.setStyleSheet(name_style)
        self.vs_label.setStyleSheet(muted_style)
        self.result_label.setStyleSheet(
            Styles.get_label_style(size=13, color=Styles.COLOR_ACCENT, weight=700)
        )

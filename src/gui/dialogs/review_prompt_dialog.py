"""
In-app rating & review prompt dialog for Chess Analyzer Pro.
Clean, modern design matching Chess Analyzer Pro standards.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QStackedWidget,
    QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor

from src.gui.styles import Styles
from src.gui.components.star_rating_widget import StarRatingWidget
from src.backend.services.feedback_service import FeedbackService, FeedbackWorker
from src.utils.config import ConfigManager
from src.constants import REVIEW_SNOOZE_INTERVAL

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False


class ReviewPromptDialog(QDialog):
    """
    Two-stage in-app review prompt dialog:
      - Page 0: Rating, username, comment input & actions.
      - Page 1: Thank you confirmation screen.
    """

    def __init__(self, parent=None, games_count: int = 3):
        super().__init__(parent)
        self.setWindowTitle("Rate Chess Analyzer Pro")
        self.setModal(True)
        self.resize(490, 470)
        self.setMinimumSize(450, 440)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.config_manager = ConfigManager()
        self.games_count = games_count
        self._worker = None

        self.setup_ui()

    def setup_ui(self):
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Styles.COLOR_BACKGROUND};
            }}
            QLabel {{
                background: transparent;
            }}
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Stacked Pages ───────────────────────────────────────────────────
        self.stacked_widget = QStackedWidget(self)

        # Page 0: Prompt & Form
        self.page_prompt = QWidget()
        self._setup_prompt_page(self.page_prompt)
        self.stacked_widget.addWidget(self.page_prompt)

        # Page 1: Thank You
        self.page_thanks = QWidget()
        self._setup_thanks_page(self.page_thanks)
        self.stacked_widget.addWidget(self.page_thanks)

        root_layout.addWidget(self.stacked_widget)
        self.stacked_widget.setCurrentIndex(0)

    def _setup_prompt_page(self, page: QWidget):
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(16)

        # Header section
        header_layout = QVBoxLayout()
        header_layout.setSpacing(6)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Enjoying Chess Analyzer Pro?")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"""
            font-size: 20px;
            font-weight: 700;
            color: {Styles.COLOR_TEXT_PRIMARY};
        """)
        header_layout.addWidget(title)

        games_text = f"You've analyzed {self.games_count} games!" if self.games_count > 0 else "We'd love to hear your thoughts!"
        subtitle = QLabel(f"{games_text} Help us improve your chess training.")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"""
            font-size: 13px;
            color: {Styles.COLOR_TEXT_SECONDARY};
        """)
        header_layout.addWidget(subtitle)
        layout.addLayout(header_layout)

        # Star Rating Widget
        self.star_widget = StarRatingWidget(self, initial_rating=5, star_size=34, show_label=True)
        layout.addWidget(self.star_widget)

        # Form fields
        form_layout = QVBoxLayout()
        form_layout.setSpacing(12)

        # Name label & input
        name_group = QVBoxLayout()
        name_group.setSpacing(5)
        name_lbl = QLabel("Your Name:")
        name_lbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY};")
        name_group.addWidget(name_lbl)

        default_user = (
            self.config_manager.get("chesscom_username", "")
            or self.config_manager.get("lichess_username", "")
            or ""
        )
        self.name_input = QLineEdit(default_user)
        self.name_input.setPlaceholderText("e.g. Grandmaster99")
        self.name_input.setStyleSheet(Styles.get_input_style())
        name_group.addWidget(self.name_input)
        form_layout.addLayout(name_group)

        # Comment label & textarea
        comment_group = QVBoxLayout()
        comment_group.setSpacing(5)
        comment_lbl = QLabel("Your Review:")
        comment_lbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY};")
        comment_group.addWidget(comment_lbl)

        self.comment_input = QTextEdit()
        self.comment_input.setFixedHeight(75)
        self.comment_input.setPlaceholderText("What do you like best? Any suggestions?")
        self.comment_input.setStyleSheet(Styles.get_input_style())
        comment_group.addWidget(self.comment_input)
        form_layout.addLayout(comment_group)

        layout.addLayout(form_layout)

        # Status / Error Label
        self.status_lbl = QLabel("")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet("font-size: 12px; color: #EF4444; background: transparent;")
        self.status_lbl.hide()
        layout.addWidget(self.status_lbl)

        layout.addStretch()

        # Action Buttons: "No, Thanks" on left, "Remind Later" and "Submit Review" on right
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_skip = QPushButton("No, Thanks")
        self.btn_skip.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_skip.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Styles.COLOR_TEXT_MUTED};
                border: none;
                padding: 8px 10px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                color: {Styles.COLOR_TEXT_PRIMARY};
                text-decoration: underline;
            }}
        """)
        self.btn_skip.clicked.connect(self._on_no_thanks)
        btn_layout.addWidget(self.btn_skip)

        btn_layout.addStretch()

        self.btn_remind = QPushButton("Remind Later")
        self.btn_remind.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_remind.setStyleSheet(Styles.get_control_button_style())
        self.btn_remind.clicked.connect(self._on_remind_later)
        btn_layout.addWidget(self.btn_remind)

        self.btn_submit = QPushButton("  Submit Review")
        self.btn_submit.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        if HAS_QTAWESOME:
            self.btn_submit.setIcon(qta.icon("fa5s.paper-plane", color="#FFFFFF"))
        self.btn_submit.setStyleSheet(Styles.get_button_style())
        self.btn_submit.clicked.connect(self._on_submit_review)
        btn_layout.addWidget(self.btn_submit)

        layout.addLayout(btn_layout)

    def _setup_thanks_page(self, page: QWidget):
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 40, 32, 32)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel("🎉")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 48px; background: transparent;")
        layout.addWidget(icon_lbl)

        thanks_title = QLabel("Thank You for Your Review!")
        thanks_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thanks_title.setStyleSheet(f"""
            font-size: 20px;
            font-weight: 700;
            color: {Styles.COLOR_TEXT_PRIMARY};
        """)
        layout.addWidget(thanks_title)

        thanks_desc = QLabel(
            "Your feedback helps make Chess Analyzer Pro better for the entire chess community."
        )
        thanks_desc.setWordWrap(True)
        thanks_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thanks_desc.setStyleSheet(f"""
            font-size: 13px;
            color: {Styles.COLOR_TEXT_SECONDARY};
            line-height: 1.4;
        """)
        layout.addWidget(thanks_desc)

        layout.addSpacing(16)

        btn_close = QPushButton("Keep Analyzing")
        btn_close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_close.setStyleSheet(Styles.get_button_style())
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignCenter)

    def _on_submit_review(self):
        rating = self.star_widget.get_rating()
        if rating < 1:
            self.status_lbl.setText("Please select a star rating (1 to 5).")
            self.status_lbl.setStyleSheet("font-size: 12px; color: #EF4444; background: transparent;")
            self.status_lbl.show()
            return

        self.btn_submit.setEnabled(False)
        self.btn_submit.setText("  Submitting...")
        self.status_lbl.hide()

        username = self.name_input.text().strip()
        comment = self.comment_input.toPlainText().strip()

        self._worker = FeedbackWorker(
            FeedbackService.submit_review,
            rating=rating,
            comment=comment,
            username=username,
        )
        self._worker.finished.connect(self._on_submission_finished)
        self._worker.start()

    def _on_submission_finished(self, success: bool, message: str, data: dict):
        self.btn_submit.setEnabled(True)
        self.btn_submit.setText("  Submit Review")

        if success:
            self.config_manager.set("review_submitted", True)
            self.stacked_widget.setCurrentIndex(1)
        else:
            self.status_lbl.setText(message)
            self.status_lbl.setStyleSheet("font-size: 12px; color: #EF4444; background: transparent;")
            self.status_lbl.show()

    def _on_remind_later(self):
        current_count = self.config_manager.get("games_analyzed_count", 0)
        self.config_manager.set("review_next_prompt_count", current_count + REVIEW_SNOOZE_INTERVAL)
        self.reject()

    def _on_no_thanks(self):
        self.config_manager.set("review_prompt_dismissed", True)
        self.reject()

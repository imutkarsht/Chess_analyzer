"""
Unified Feedback, Bug Report, and Feature Suggestion Dialog.
Clean, modern design matching Chess Analyzer Pro standards.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.backend.services.feedback_service import (
    FeedbackService,
    FeedbackWorker,
    get_recent_logs,
)
from src.gui.components import Button, ButtonSize, ButtonVariant, Tabs, TabVariant
from src.gui.components.star_rating_widget import StarRatingWidget
from src.gui.styles import Styles
from src.utils.config import ConfigManager

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False


class FeedbackDialog(QDialog):
    """
    Unified dialog with 3 modes:
      1. Bug Report (POST /api/feedback, type="bug")
      2. Feature Suggestion (POST /api/feedback, type="feature")
      3. Review (POST /api/reviews)
    """

    def __init__(
        self,
        parent=None,
        initial_tab: str = "bug",
        initial_title: str = "",
        initial_message: str = "",
        initial_logs: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle("Feedback & Support")
        self.setModal(True)
        self.resize(600, 600)
        self.setMinimumSize(540, 560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.config_manager = ConfigManager()
        self._worker = None
        self._current_tab = initial_tab
        self._initial_title = initial_title
        self._initial_message = initial_message
        self._initial_logs = initial_logs or get_recent_logs(max_chars=1000)

        self.setup_ui()
        self._select_tab(self._current_tab)

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

        # ── Header Bar ──────────────────────────────────────────────────────
        header_bar = QWidget()
        header_bar.setFixedHeight(58)
        header_bar.setStyleSheet(f"""
            background-color: {Styles.COLOR_SURFACE};
            border-bottom: 1px solid {Styles.COLOR_BORDER};
        """)
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(24, 0, 24, 0)
        header_layout.setSpacing(12)

        icon_lbl = QLabel()
        if HAS_QTAWESOME:
            icon_lbl.setPixmap(qta.icon("fa5s.comment-dots", color=Styles.COLOR_ACCENT).pixmap(22, 22))
        else:
            icon_lbl.setText("💬")
            icon_lbl.setStyleSheet(f"font-size: 18px; color: {Styles.COLOR_ACCENT};")
        header_layout.addWidget(icon_lbl)

        title_lbl = QLabel("Feedback & Support")
        title_lbl.setStyleSheet(f"""
            font-size: 17px;
            font-weight: 700;
            color: {Styles.COLOR_TEXT_PRIMARY};
            border: none;
        """)
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()

        root_layout.addWidget(header_bar)

        # ── Body Content ────────────────────────────────────────────────────
        body_widget = QWidget()
        body_layout = QVBoxLayout(body_widget)
        body_layout.setContentsMargins(24, 20, 24, 20)
        body_layout.setSpacing(16)

        # Tab selector: the shared accent-filled segmented control.
        self.tabs = Tabs(
            TabVariant.SEGMENTED,
            active_style="accent",
            font_size=13,
            padding=(7, 14, 7, 14),
            radius=6,
            track_padding=4,
        )
        self.tabs.add_tab("Report a Bug", icon="fa5s.bug")
        self.tabs.add_tab("Feature Request", icon="fa5s.lightbulb")
        self.tabs.add_tab("Write Review", icon="fa5s.star")
        self.tabs.current_changed.connect(self._on_tab_index_changed)
        body_layout.addWidget(self.tabs)

        # Stacked Pages
        self.stacked_widget = QStackedWidget(self)

        # Page 0: Bug Report
        self.page_bug = QWidget()
        self._setup_bug_page(self.page_bug)
        self.stacked_widget.addWidget(self.page_bug)

        # Page 1: Feature Request
        self.page_feature = QWidget()
        self._setup_feature_page(self.page_feature)
        self.stacked_widget.addWidget(self.page_feature)

        # Page 2: Review
        self.page_review = QWidget()
        self._setup_review_page(self.page_review)
        self.stacked_widget.addWidget(self.page_review)

        # Page 3: Success Confirmation
        self.page_success = QWidget()
        self._setup_success_page(self.page_success)
        self.stacked_widget.addWidget(self.page_success)

        body_layout.addWidget(self.stacked_widget, 1)

        # Status / Error Label
        self.status_lbl = QLabel("")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet("font-size: 12px; color: #EF4444; background: transparent;")
        self.status_lbl.hide()
        body_layout.addWidget(self.status_lbl)

        # Bottom Action Buttons
        self.bottom_bar = QWidget()
        btn_layout = QHBoxLayout(self.bottom_bar)
        btn_layout.setContentsMargins(0, 4, 0, 0)
        btn_layout.setSpacing(12)

        self.btn_cancel = Button("Cancel", ButtonVariant.FILLED)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        btn_layout.addStretch()

        self.btn_submit = Button("Submit", ButtonVariant.PRIMARY)
        self.btn_submit.clicked.connect(self._on_submit)
        btn_layout.addWidget(self.btn_submit)

        body_layout.addWidget(self.bottom_bar)
        root_layout.addWidget(body_widget)

    _TAB_IDS = ("bug", "feature", "review")

    def _on_tab_index_changed(self, index: int) -> None:
        if 0 <= index < len(self._TAB_IDS):
            self._switch_tab(self._TAB_IDS[index])

    def _select_tab(self, tab_id: str) -> None:
        """Show ``tab_id`` programmatically, keeping the tab bar in sync."""
        if tab_id not in self._TAB_IDS:
            return
        index = self._TAB_IDS.index(tab_id)
        if self.tabs.current_index() == index:
            self._switch_tab(tab_id)
        else:
            self.tabs.set_current_index(index)

    def _switch_tab(self, tab_id: str):
        self._current_tab = tab_id
        self.status_lbl.hide()

        if tab_id == "bug":
            self.stacked_widget.setCurrentIndex(0)
            self.btn_submit.setText("Submit Bug Report")
            submit_icon = "fa5s.paper-plane"
        elif tab_id == "feature":
            self.stacked_widget.setCurrentIndex(1)
            self.btn_submit.setText("Submit Feature Request")
            submit_icon = "fa5s.paper-plane"
        else:
            self.stacked_widget.setCurrentIndex(2)
            self.btn_submit.setText("Submit Review")
            submit_icon = "fa5s.star"

        if HAS_QTAWESOME:
            self.btn_submit.set_icon_spec(submit_icon)

        self.bottom_bar.show()

    def _setup_bug_page(self, page: QWidget):
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(10)

        # Title
        lbl_title = QLabel("Bug Summary:")
        lbl_title.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY};")
        layout.addWidget(lbl_title)

        self.bug_title_input = QLineEdit(self._initial_title)
        self.bug_title_input.setPlaceholderText("e.g. Engine stopped responding on move 42")
        self.bug_title_input.setStyleSheet(Styles.get_input_style())
        layout.addWidget(self.bug_title_input)

        # Description
        lbl_desc = QLabel("What happened?")
        lbl_desc.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY};")
        layout.addWidget(lbl_desc)

        self.bug_desc_input = QTextEdit()
        self.bug_desc_input.setFixedHeight(85)
        self.bug_desc_input.setPlaceholderText("Please describe what you were doing when the issue occurred...")
        if self._initial_message:
            self.bug_desc_input.setPlainText(self._initial_message)
        self.bug_desc_input.setStyleSheet(Styles.get_input_style())
        layout.addWidget(self.bug_desc_input)

        # Email & Name row
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(12)

        v1 = QVBoxLayout()
        v1.setSpacing(4)
        lbl_email = QLabel("Your Email:")
        lbl_email.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {Styles.COLOR_TEXT_SECONDARY};")
        v1.addWidget(lbl_email)
        self.bug_email_input = QLineEdit()
        self.bug_email_input.setPlaceholderText("To get notified when resolved")
        self.bug_email_input.setStyleSheet(Styles.get_input_style())
        v1.addWidget(self.bug_email_input)
        meta_layout.addLayout(v1)

        v2 = QVBoxLayout()
        v2.setSpacing(4)
        lbl_name = QLabel("Your Name:")
        lbl_name.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {Styles.COLOR_TEXT_SECONDARY};")
        v2.addWidget(lbl_name)
        default_user = self.config_manager.get("chesscom_username", "") or self.config_manager.get("lichess_username", "")
        self.bug_name_input = QLineEdit(default_user)
        self.bug_name_input.setPlaceholderText("Player handle or name")
        self.bug_name_input.setStyleSheet(Styles.get_input_style())
        v2.addWidget(self.bug_name_input)
        meta_layout.addLayout(v2)

        layout.addLayout(meta_layout)

        # Diagnostic logs row
        log_header_layout = QHBoxLayout()
        self.cb_include_logs = QCheckBox("Attach diagnostic log excerpt (recommended)")
        self.cb_include_logs.setChecked(True)
        self.cb_include_logs.setStyleSheet(f"""
            QCheckBox {{
                background: transparent;
                border: none;
                padding: 0px;
                color: {Styles.COLOR_TEXT_SECONDARY};
                font-size: 12px;
                font-weight: 500;
            }}
            QCheckBox:hover {{
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
        """)
        log_header_layout.addWidget(self.cb_include_logs)

        log_header_layout.addStretch()

        self.btn_toggle_log = Button(
            "Preview Log",
            ButtonVariant.LINK,
            size=ButtonSize.SM,
            on_click=self._toggle_log_preview,
        )
        log_header_layout.addWidget(self.btn_toggle_log)
        layout.addLayout(log_header_layout)

        # Log preview text box (initially collapsed)
        self.log_preview_box = QTextEdit()
        self.log_preview_box.setFixedHeight(75)
        self.log_preview_box.setReadOnly(True)
        self.log_preview_box.setPlainText(self._initial_logs or "(No recent log entries)")
        self.log_preview_box.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Styles.COLOR_SURFACE};
                color: {Styles.COLOR_TEXT_MUTED};
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 11px;
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                padding: 6px;
            }}
        """)
        self.log_preview_box.hide()
        layout.addWidget(self.log_preview_box)

        layout.addStretch()

    def _toggle_log_preview(self):
        if self.log_preview_box.isVisible():
            self.log_preview_box.hide()
            self.btn_toggle_log.setText("Preview Log")
        else:
            self.log_preview_box.show()
            self.btn_toggle_log.setText("Hide Log")

    def _setup_feature_page(self, page: QWidget):
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(12)

        # Feature Title
        lbl_title = QLabel("Feature Title:")
        lbl_title.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY};")
        layout.addWidget(lbl_title)

        self.feat_title_input = QLineEdit()
        self.feat_title_input.setPlaceholderText("e.g. Opening book explorer support for ECO codes")
        self.feat_title_input.setStyleSheet(Styles.get_input_style())
        layout.addWidget(self.feat_title_input)

        # Description
        lbl_desc = QLabel("Describe your idea:")
        lbl_desc.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY};")
        layout.addWidget(lbl_desc)

        self.feat_desc_input = QTextEdit()
        self.feat_desc_input.setFixedHeight(110)
        self.feat_desc_input.setPlaceholderText("Explain how this feature would work and why it would be helpful...")
        self.feat_desc_input.setStyleSheet(Styles.get_input_style())
        layout.addWidget(self.feat_desc_input)

        # Email & Name row
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(12)

        v1 = QVBoxLayout()
        v1.setSpacing(4)
        lbl_email = QLabel("Your Email:")
        lbl_email.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {Styles.COLOR_TEXT_SECONDARY};")
        v1.addWidget(lbl_email)
        self.feat_email_input = QLineEdit()
        self.feat_email_input.setPlaceholderText("Email address")
        self.feat_email_input.setStyleSheet(Styles.get_input_style())
        v1.addWidget(self.feat_email_input)
        meta_layout.addLayout(v1)

        v2 = QVBoxLayout()
        v2.setSpacing(4)
        lbl_name = QLabel("Your Name:")
        lbl_name.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {Styles.COLOR_TEXT_SECONDARY};")
        v2.addWidget(lbl_name)
        default_user = self.config_manager.get("chesscom_username", "") or self.config_manager.get("lichess_username", "")
        self.feat_name_input = QLineEdit(default_user)
        self.feat_name_input.setPlaceholderText("Player handle or name")
        self.feat_name_input.setStyleSheet(Styles.get_input_style())
        v2.addWidget(self.feat_name_input)
        meta_layout.addLayout(v2)

        layout.addLayout(meta_layout)
        layout.addStretch()

    def _setup_review_page(self, page: QWidget):
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(14)

        # Star Rating
        self.review_star_widget = StarRatingWidget(self, initial_rating=5, star_size=32, show_label=True)
        layout.addWidget(self.review_star_widget)

        # Name
        lbl_name = QLabel("Your Name:")
        lbl_name.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY};")
        layout.addWidget(lbl_name)

        default_user = self.config_manager.get("chesscom_username", "") or self.config_manager.get("lichess_username", "")
        self.review_name_input = QLineEdit(default_user)
        self.review_name_input.setPlaceholderText("e.g. Grandmaster99")
        self.review_name_input.setStyleSheet(Styles.get_input_style())
        layout.addWidget(self.review_name_input)

        # Comment
        lbl_comment = QLabel("Your Review:")
        lbl_comment.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {Styles.COLOR_TEXT_PRIMARY};")
        layout.addWidget(lbl_comment)

        self.review_comment_input = QTextEdit()
        self.review_comment_input.setFixedHeight(90)
        self.review_comment_input.setPlaceholderText("Share your experience with Chess Analyzer Pro...")
        self.review_comment_input.setStyleSheet(Styles.get_input_style())
        layout.addWidget(self.review_comment_input)

        layout.addStretch()

    def _setup_success_page(self, page: QWidget):
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 40, 24, 24)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel("✅")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 48px; background: transparent;")
        layout.addWidget(icon_lbl)

        self.success_title = QLabel("Submission Received!")
        self.success_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.success_title.setStyleSheet(f"""
            font-size: 20px;
            font-weight: 700;
            color: {Styles.COLOR_TEXT_PRIMARY};
            background: transparent;
        """)
        layout.addWidget(self.success_title)

        self.success_desc = QLabel(
            "Thank you for helping us improve Chess Analyzer Pro!"
        )
        self.success_desc.setWordWrap(True)
        self.success_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.success_desc.setStyleSheet(f"""
            font-size: 13px;
            color: {Styles.COLOR_TEXT_SECONDARY};
            background: transparent;
        """)
        layout.addWidget(self.success_desc)

        layout.addSpacing(16)

        btn_done = Button("Done", ButtonVariant.PRIMARY)
        btn_done.clicked.connect(self.accept)
        layout.addWidget(btn_done, alignment=Qt.AlignmentFlag.AlignCenter)

    def _on_submit(self):
        self.status_lbl.hide()

        if self._current_tab == "bug":
            title = self.bug_title_input.text().strip()
            message = self.bug_desc_input.toPlainText().strip()
            email = self.bug_email_input.text().strip()
            name = self.bug_name_input.text().strip()

            if not title:
                self._show_error("Please enter a bug summary/title.")
                return
            if not message:
                self._show_error("Please enter a description of the issue.")
                return

            logs = self._initial_logs if self.cb_include_logs.isChecked() else ""

            self._set_submitting(True)
            self._worker = FeedbackWorker(
                FeedbackService.submit_bug_report,
                title=title,
                message=message,
                name=name,
                email=email,
                logs=logs,
            )
            self._worker.finished.connect(lambda s, m, d: self._on_submission_finished(s, m, d, "Bug report submitted!"))
            self._worker.start()

        elif self._current_tab == "feature":
            title = self.feat_title_input.text().strip()
            message = self.feat_desc_input.toPlainText().strip()
            email = self.feat_email_input.text().strip()
            name = self.feat_name_input.text().strip()

            if not title:
                self._show_error("Please enter a feature title.")
                return
            if not message:
                self._show_error("Please describe your feature idea.")
                return

            self._set_submitting(True)
            self._worker = FeedbackWorker(
                FeedbackService.submit_feature_request,
                title=title,
                message=message,
                name=name,
                email=email,
            )
            self._worker.finished.connect(lambda s, m, d: self._on_submission_finished(s, m, d, "Feature request submitted!"))
            self._worker.start()

        elif self._current_tab == "review":
            rating = self.review_star_widget.get_rating()
            if rating < 1:
                self._show_error("Please select a star rating (1 to 5).")
                return

            name = self.review_name_input.text().strip()
            comment = self.review_comment_input.toPlainText().strip()

            self._set_submitting(True)
            self._worker = FeedbackWorker(
                FeedbackService.submit_review,
                rating=rating,
                comment=comment,
                username=name,
            )
            self._worker.finished.connect(lambda s, m, d: self._on_submission_finished(s, m, d, "Review submitted!"))
            self._worker.start()

    def _set_submitting(self, submitting: bool):
        self.btn_submit.setEnabled(not submitting)
        self.btn_submit.setText("Submitting..." if submitting else "Submit")

    def _show_error(self, message: str):
        self.status_lbl.setText(message)
        self.status_lbl.setStyleSheet("font-size: 12px; color: #EF4444; background: transparent;")
        self.status_lbl.show()

    def _on_submission_finished(self, success: bool, message: str, data: dict, custom_success_title: str):
        self._set_submitting(False)

        if success:
            if self._current_tab == "review":
                self.config_manager.set("review_submitted", True)
            self.success_title.setText(custom_success_title)
            self.success_desc.setText(message)
            self.bottom_bar.hide()
            self.stacked_widget.setCurrentIndex(3)
        else:
            self._show_error(message)

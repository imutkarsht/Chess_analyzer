# SPDX-License-Identifier: GPL-3.0-only
"""Unified Feedback, Bug Report, and Feature Suggestion panel and dialog."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.backend.services.feedback_service import FeedbackService, get_recent_logs
from src.gui.components import (
    Button,
    ButtonSize,
    ButtonVariant,
    Checkbox,
    CheckboxVariant,
    IconLabel,
    Input,
    Label,
    OverlayManager,
    StarRatingWidget,
    Tabs,
    TabVariant,
    TextArea,
    TextRole,
    TextTone,
)
from src.gui.utils.worker_registry import register_worker, remove_worker
from src.utils.config import ConfigManager
from src.utils.logger import logger
from src.workers import FeedbackWorker


class FeedbackPanel(QWidget):
    """Content panel for bug reports, feature suggestions, and reviews.

    Embeds cleanly in ``OverlayCard`` (which supplies the header, close button,
    and footer actions) or inside the legacy ``FeedbackDialog`` shell.
    """

    done_requested = pyqtSignal()
    tab_changed = pyqtSignal(str)
    submitting_changed = pyqtSignal(bool)
    submitted = pyqtSignal()
    content_resized = pyqtSignal()

    _TAB_IDS = ("bug", "feature", "review")

    def __init__(
        self,
        *,
        initial_tab: str = "bug",
        initial_title: str = "",
        initial_message: str = "",
        initial_logs: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self._worker: FeedbackWorker | None = None
        self._shutting_down = False
        self._pending_success_title = ""
        self._current_tab = initial_tab
        self._initial_title = initial_title
        self._initial_message = initial_message
        self._initial_logs = initial_logs or get_recent_logs(max_chars=1000)

        self._build_ui()
        self._select_tab(self._current_tab)

    def _build_ui(self) -> None:
        body_layout = QVBoxLayout(self)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(16)

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

        self.stacked_widget = QStackedWidget(self)

        self.page_bug = QWidget(self.stacked_widget)
        self._setup_bug_page(self.page_bug)
        self.stacked_widget.addWidget(self.page_bug)

        self.page_feature = QWidget(self.stacked_widget)
        self._setup_feature_page(self.page_feature)
        self.stacked_widget.addWidget(self.page_feature)

        self.page_review = QWidget(self.stacked_widget)
        self._setup_review_page(self.page_review)
        self.stacked_widget.addWidget(self.page_review)

        self.page_success = QWidget(self.stacked_widget)
        self._setup_success_page(self.page_success)
        self.stacked_widget.addWidget(self.page_success)

        body_layout.addWidget(self.stacked_widget, 1)

        self.status_lbl = Label("", role=TextRole.CAPTION, tone=TextTone.BLUNDER)
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.hide()
        body_layout.addWidget(self.status_lbl)

    def _on_tab_index_changed(self, index: int) -> None:
        if 0 <= index < len(self._TAB_IDS):
            self._switch_tab(self._TAB_IDS[index])

    def _select_tab(self, tab_id: str) -> None:
        if tab_id not in self._TAB_IDS:
            tab_id = "bug"
        index = self._TAB_IDS.index(tab_id)
        if self.tabs.current_index() == index:
            self._switch_tab(tab_id)
        else:
            self.tabs.set_current_index(index)

    def _switch_tab(self, tab_id: str) -> None:
        self._current_tab = tab_id
        self.status_lbl.hide()
        index = self._TAB_IDS.index(tab_id)
        self.stacked_widget.setCurrentIndex(index)
        self.tab_changed.emit(tab_id)
        self.content_resized.emit()

    def submit_meta(self) -> tuple[str, str, str]:
        """Return ``(button_text, tooltip, icon_spec)`` for the active tab."""
        if self._current_tab == "bug":
            return ("Submit Bug Report", "Send this bug report", "fa5s.paper-plane")
        if self._current_tab == "feature":
            return (
                "Submit Feature Request",
                "Send this feature request",
                "fa5s.paper-plane",
            )
        return ("Submit Review", "Send this rating and review", "fa5s.star")

    def _default_username(self) -> str:
        return self.config_manager.chesscom_username or self.config_manager.lichess_username

    @staticmethod
    def _field_group(label_text: str, field: QWidget, *, caption: bool = False) -> QVBoxLayout:
        group = QVBoxLayout()
        group.setContentsMargins(0, 0, 0, 0)
        group.setSpacing(6)
        group.addWidget(
            Label(
                label_text,
                role=TextRole.CAPTION if caption else TextRole.BODY,
                weight=600,
                tone=TextTone.SECONDARY if caption else TextTone.PRIMARY,
            )
        )
        group.addWidget(field)
        return group

    def _setup_bug_page(self, page: QWidget) -> None:
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(14)

        self.bug_title_input = Input(
            self._initial_title,
            "e.g. Engine stopped responding on move 42",
        )
        layout.addLayout(self._field_group("Bug Summary", self.bug_title_input))

        self.bug_desc_input = TextArea(
            self._initial_message,
            "Please describe what you were doing when the issue occurred...",
            min_height=96,
        )
        layout.addLayout(self._field_group("What happened?", self.bug_desc_input))

        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(12)
        self.bug_email_input = Input(placeholder="To get notified when resolved")
        meta_layout.addLayout(
            self._field_group("Your Email", self.bug_email_input, caption=True), 1
        )
        self.bug_name_input = Input(self._default_username(), "Player handle or name")
        meta_layout.addLayout(
            self._field_group("Your Name", self.bug_name_input, caption=True), 1
        )
        layout.addLayout(meta_layout)

        log_header_layout = QHBoxLayout()
        self.cb_include_logs = Checkbox(
            "Attach diagnostic log excerpt (recommended)",
            CheckboxVariant.COMPACT,
        )
        self.cb_include_logs.setChecked(True)
        log_header_layout.addWidget(self.cb_include_logs)
        log_header_layout.addStretch()

        self.btn_toggle_log = Button(
            "Preview Log",
            ButtonVariant.LINK,
            size=ButtonSize.SM,
            tooltip="Show the diagnostic log excerpt",
            on_click=self._toggle_log_preview,
        )
        log_header_layout.addWidget(self.btn_toggle_log)
        layout.addLayout(log_header_layout)

        self.log_preview_box = TextArea(
            self._initial_logs or "(No recent log entries)",
            variant="code",
            min_height=80,
            font_size=11,
            readonly=True,
        )
        self.log_preview_box.hide()
        layout.addWidget(self.log_preview_box)
        layout.addStretch()

    def _toggle_log_preview(self) -> None:
        if self.log_preview_box.isVisible():
            self.log_preview_box.hide()
            self.btn_toggle_log.setText("Preview Log")
            self.btn_toggle_log.setToolTip("Show the diagnostic log excerpt")
        else:
            self.log_preview_box.show()
            self.btn_toggle_log.setText("Hide Log")
            self.btn_toggle_log.setToolTip("Hide the diagnostic log excerpt")
        self.content_resized.emit()

    def _setup_feature_page(self, page: QWidget) -> None:
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(14)

        self.feat_title_input = Input(
            placeholder="e.g. Opening book explorer support for ECO codes",
        )
        layout.addLayout(self._field_group("Feature Title", self.feat_title_input))

        self.feat_desc_input = TextArea(
            placeholder="Explain how this feature would work and why it would be helpful...",
            min_height=115,
        )
        layout.addLayout(self._field_group("Describe your idea", self.feat_desc_input))

        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(12)
        self.feat_email_input = Input(placeholder="Email address")
        meta_layout.addLayout(
            self._field_group("Your Email", self.feat_email_input, caption=True), 1
        )
        self.feat_name_input = Input(self._default_username(), "Player handle or name")
        meta_layout.addLayout(
            self._field_group("Your Name", self.feat_name_input, caption=True), 1
        )
        layout.addLayout(meta_layout)
        layout.addStretch()

    def _setup_review_page(self, page: QWidget) -> None:
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(14)

        self.review_star_widget = StarRatingWidget(
            self, initial_rating=5, star_size=32, show_label=True
        )
        layout.addWidget(self.review_star_widget)

        self.review_name_input = Input(self._default_username(), "e.g. Grandmaster99")
        layout.addLayout(self._field_group("Your Name", self.review_name_input))

        self.review_comment_input = TextArea(
            placeholder="Share your experience with Chess Analyzer Pro...",
            min_height=96,
        )
        layout.addLayout(self._field_group("Your Review", self.review_comment_input))
        layout.addStretch()

    def _setup_success_page(self, page: QWidget) -> None:
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 28, 16, 16)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = IconLabel("fa5s.check-circle", size=44, tone=TextTone.BEST, fallback="✓")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)

        self.success_title = Label(
            "Submission Received!",
            role=TextRole.DIALOG_TITLE,
            weight=600,
        )
        self.success_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.success_title)

        self.success_desc = Label(
            "Thank you for helping us improve Chess Analyzer Pro!",
            role=TextRole.BODY,
            tone=TextTone.SECONDARY,
            wrap=True,
        )
        self.success_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.success_desc)

        layout.addSpacing(12)

        btn_done = Button(
            "Done",
            ButtonVariant.PRIMARY,
            tooltip="Close this dialog",
            on_click=self.done_requested.emit,
        )
        layout.addWidget(btn_done, alignment=Qt.AlignmentFlag.AlignCenter)

    def submit(self) -> None:
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
            self._start_worker(
                FeedbackService.submit_bug_report,
                "Bug report submitted!",
                title=title,
                message=message,
                name=name,
                email=email,
                logs=logs,
            )

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

            self._start_worker(
                FeedbackService.submit_feature_request,
                "Feature request submitted!",
                title=title,
                message=message,
                name=name,
                email=email,
            )

        elif self._current_tab == "review":
            rating = self.review_star_widget.get_rating()
            if rating < 1:
                self._show_error("Please select a star rating (1 to 5).")
                return

            name = self.review_name_input.text().strip()
            comment = self.review_comment_input.toPlainText().strip()
            self._start_worker(
                FeedbackService.submit_review,
                "Review submitted!",
                rating=rating,
                comment=comment,
                username=name,
            )

    def _start_worker(self, fn, success_title: str, **kwargs) -> None:
        self._shutting_down = False
        self._pending_success_title = success_title
        self.submitting_changed.emit(True)
        worker = FeedbackWorker(fn, **kwargs)
        register_worker(worker)
        worker.finished.connect(lambda *_args, w=worker: remove_worker(w))
        worker.finished.connect(self._on_submission_finished)
        self._worker = worker
        worker.start()

    def _show_error(self, message: str) -> None:
        self.status_lbl.setText(message)
        self.status_lbl.set_tone(TextTone.BLUNDER)
        self.status_lbl.show()
        self.content_resized.emit()

    def _on_submission_finished(self, success: bool, message: str, _data: dict) -> None:
        self._worker = None
        if self._shutting_down:
            return
        self.submitting_changed.emit(False)

        if success:
            if self._current_tab == "review":
                self.config_manager.set("review_submitted", True)
            self.success_title.setText(self._pending_success_title)
            self.success_desc.setText(message)
            self.tabs.hide()
            self.stacked_widget.setCurrentIndex(3)
            self.submitted.emit()
            self.content_resized.emit()
        else:
            self._show_error(message)

    def shutdown(self) -> None:
        self._shutting_down = True
        worker, self._worker = self._worker, None
        if worker is not None:
            try:
                worker.finished.disconnect(self._on_submission_finished)
            except (TypeError, RuntimeError):
                pass


class FeedbackDialog(QDialog):
    """Native QDialog wrapper around ``FeedbackPanel``."""

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
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.panel = FeedbackPanel(
            initial_tab=initial_tab,
            initial_title=initial_title,
            initial_message=initial_message,
            initial_logs=initial_logs,
            parent=self,
        )
        self._setup_ui()
        self._sync_submit_button()

    def _setup_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header_bar = QWidget()
        header_bar.setObjectName("FeedbackHeader")
        header_bar.setFixedHeight(58)
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(24, 0, 24, 0)
        header_layout.setSpacing(12)
        header_layout.addWidget(
            IconLabel("fa5s.comment-dots", size=22, tone=TextTone.ACCENT, fallback="💬")
        )
        header_layout.addWidget(
            Label("Feedback & Support", role=TextRole.DIALOG_TITLE, weight=600)
        )
        header_layout.addStretch()
        root_layout.addWidget(header_bar)

        body_widget = QWidget()
        body_layout = QVBoxLayout(body_widget)
        body_layout.setContentsMargins(24, 20, 24, 20)
        body_layout.setSpacing(16)
        body_layout.addWidget(self.panel, 1)

        self.bottom_bar = QWidget()
        btn_layout = QHBoxLayout(self.bottom_bar)
        btn_layout.setContentsMargins(0, 4, 0, 0)
        btn_layout.setSpacing(12)

        self.btn_cancel = Button(
            "Cancel",
            ButtonVariant.HOLLOW,
            tooltip="Close without sending feedback",
            on_click=self.reject,
        )
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch()

        self.btn_submit = Button(
            "Submit",
            ButtonVariant.PRIMARY,
            tooltip="Send this feedback",
            on_click=self.panel.submit,
        )
        btn_layout.addWidget(self.btn_submit)
        body_layout.addWidget(self.bottom_bar)
        root_layout.addWidget(body_widget)

        self.panel.tab_changed.connect(lambda _tab: self._sync_submit_button())
        self.panel.submitting_changed.connect(self._on_submitting_changed)
        self.panel.submitted.connect(self.bottom_bar.hide)
        self.panel.done_requested.connect(self.accept)

    def _sync_submit_button(self) -> None:
        text, tooltip, icon = self.panel.submit_meta()
        self.btn_submit.setText(text)
        self.btn_submit.setToolTip(tooltip)
        self.btn_submit.set_icon_spec(icon)

    def _on_submitting_changed(self, submitting: bool) -> None:
        self.btn_submit.setEnabled(not submitting)
        self.btn_submit.setText("Submitting..." if submitting else self.panel.submit_meta()[0])

    def reject(self) -> None:
        self.panel.shutdown()
        super().reject()

    def closeEvent(self, event) -> None:
        self.panel.shutdown()
        super().closeEvent(event)


def open_feedback_overlay(
    parent,
    *,
    initial_tab: str = "bug",
    initial_title: str = "",
    initial_message: str = "",
    initial_logs: str = "",
) -> None:
    """Open the Feedback panel as an in-window overlay."""
    if isinstance(parent, QWidget):
        try:
            manager = OverlayManager.for_window(parent)
            card = manager.create_card(
                title="Feedback & Support",
                description="Send a bug report, suggest a feature, or leave a review.",
                max_width=600,
                minimum_width=400,
                dismiss_on_escape=True,
                dismiss_on_backdrop=False,
            )
            panel = FeedbackPanel(
                initial_tab=initial_tab,
                initial_title=initial_title,
                initial_message=initial_message,
                initial_logs=initial_logs,
                parent=card,
            )
            card.set_content(panel)

            cancel_btn = Button(
                "Cancel",
                ButtonVariant.HOLLOW,
                tooltip="Close without sending feedback",
                on_click=card.reject,
            )
            text, tooltip, icon = panel.submit_meta()
            submit_btn = Button(
                text,
                ButtonVariant.PRIMARY,
                icon=icon,
                tooltip=tooltip,
                on_click=panel.submit,
            )
            card.add_action(cancel_btn)
            card.add_action(submit_btn, primary=True)

            def sync_submit(_tab: str = "") -> None:
                t, tip, ic = panel.submit_meta()
                submit_btn.setText(t)
                submit_btn.setToolTip(tip)
                submit_btn.set_icon_spec(ic)

            def on_submitting(submitting: bool) -> None:
                submit_btn.set_loading(submitting)
                cancel_btn.setEnabled(not submitting)
                card.dismiss_on_escape = not submitting
                card.close_button.setVisible(not submitting)

            def on_submitted() -> None:
                card.footer.hide()
                card.notify_content_changed()

            panel.tab_changed.connect(sync_submit)
            panel.submitting_changed.connect(on_submitting)
            panel.submitted.connect(on_submitted)
            panel.done_requested.connect(card.accept)
            panel.content_resized.connect(card.notify_content_changed)

            card.add_cleanup(panel.shutdown)
            manager.open(card)
            return
        except Exception:
            logger.warning("open_feedback_overlay failed, falling back", exc_info=True)

    FeedbackDialog(
        parent,
        initial_tab=initial_tab,
        initial_title=initial_title,
        initial_message=initial_message,
        initial_logs=initial_logs,
    ).exec()

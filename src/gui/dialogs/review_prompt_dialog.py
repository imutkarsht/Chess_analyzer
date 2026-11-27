# SPDX-License-Identifier: GPL-3.0-only
"""In-app rating & review prompt panel, dialog wrapper, and overlay launcher."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.backend.services.feedback_service import FeedbackService
from src.constants import REVIEW_SNOOZE_INTERVAL
from src.gui.components import (
    Button,
    ButtonVariant,
    IconLabel,
    Input,
    Label,
    OverlayManager,
    StarRatingWidget,
    TextArea,
    TextRole,
    TextTone,
)
from src.gui.utils.worker_registry import register_worker, remove_worker
from src.utils.config import ConfigManager
from src.utils.logger import logger
from src.workers import FeedbackWorker


class ReviewPromptPanel(QWidget):
    """Two-stage rating and review form for ``OverlayCard`` or ``ReviewPromptDialog``."""

    done_requested = pyqtSignal()
    dismiss_requested = pyqtSignal()
    submitting_changed = pyqtSignal(bool)
    submitted = pyqtSignal()
    content_resized = pyqtSignal()

    def __init__(self, games_count: int = 3, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.games_count = games_count
        self._worker: FeedbackWorker | None = None
        self._shutting_down = False

        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.stacked_widget = QStackedWidget(self)

        self.page_prompt = QWidget(self.stacked_widget)
        self._setup_prompt_page(self.page_prompt)
        self.stacked_widget.addWidget(self.page_prompt)

        self.page_thanks = QWidget(self.stacked_widget)
        self._setup_thanks_page(self.page_thanks)
        self.stacked_widget.addWidget(self.page_thanks)

        root_layout.addWidget(self.stacked_widget)
        self.stacked_widget.setCurrentIndex(0)

    def _setup_prompt_page(self, page: QWidget) -> None:
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.star_widget = StarRatingWidget(
            self, initial_rating=5, star_size=34, show_label=True
        )
        layout.addWidget(self.star_widget)

        name_group = QVBoxLayout()
        name_group.setContentsMargins(0, 0, 0, 0)
        name_group.setSpacing(6)
        name_group.addWidget(Label("Your Name", role=TextRole.BODY, weight=600))
        default_user = (
            self.config_manager.chesscom_username or self.config_manager.lichess_username
        )
        self.name_input = Input(default_user, "e.g. Grandmaster99")
        name_group.addWidget(self.name_input)
        layout.addLayout(name_group)

        comment_group = QVBoxLayout()
        comment_group.setContentsMargins(0, 0, 0, 0)
        comment_group.setSpacing(6)
        comment_group.addWidget(Label("Your Review", role=TextRole.BODY, weight=600))
        self.comment_input = TextArea(
            placeholder="What do you like best? Any suggestions?",
            min_height=84,
        )
        comment_group.addWidget(self.comment_input)
        layout.addLayout(comment_group)

        self.status_lbl = Label("", role=TextRole.CAPTION, tone=TextTone.BLUNDER)
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.hide()
        layout.addWidget(self.status_lbl)

    def _setup_thanks_page(self, page: QWidget) -> None:
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 24, 16, 12)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = IconLabel("fa5s.check-circle", size=44, tone=TextTone.BEST, fallback="🎉")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)

        thanks_title = Label(
            "Thank You for Your Review!",
            role=TextRole.DIALOG_TITLE,
            weight=600,
        )
        thanks_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(thanks_title)

        thanks_desc = Label(
            "Your feedback helps make Chess Analyzer Pro better for the entire chess community.",
            role=TextRole.BODY,
            tone=TextTone.SECONDARY,
            wrap=True,
        )
        thanks_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(thanks_desc)

        layout.addSpacing(8)

        btn_close = Button(
            "Keep Analyzing",
            ButtonVariant.PRIMARY,
            tooltip="Close this dialog and return to analysis",
            on_click=self.done_requested.emit,
        )
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignCenter)

    def submit_review(self) -> None:
        rating = self.star_widget.get_rating()
        if rating < 1:
            self.status_lbl.setText("Please select a star rating (1 to 5).")
            self.status_lbl.set_tone(TextTone.BLUNDER)
            self.status_lbl.show()
            self.content_resized.emit()
            return

        self._shutting_down = False
        self.submitting_changed.emit(True)
        self.status_lbl.hide()

        username = self.name_input.text().strip()
        comment = self.comment_input.toPlainText().strip()

        worker = FeedbackWorker(
            FeedbackService.submit_review,
            rating=rating,
            comment=comment,
            username=username,
        )
        register_worker(worker)
        worker.finished.connect(lambda *_args, w=worker: remove_worker(w))
        worker.finished.connect(self._on_submission_finished)
        self._worker = worker
        worker.start()

    def _on_submission_finished(self, success: bool, message: str, _data: dict) -> None:
        self._worker = None
        if self._shutting_down:
            return
        self.submitting_changed.emit(False)

        if success:
            self.config_manager.set("review_submitted", True)
            self.stacked_widget.setCurrentIndex(1)
            self.submitted.emit()
            self.content_resized.emit()
        else:
            self.status_lbl.setText(message)
            self.status_lbl.set_tone(TextTone.BLUNDER)
            self.status_lbl.show()
            self.content_resized.emit()

    def remind_later(self) -> None:
        current_count = self.config_manager.games_analyzed_count
        self.config_manager.set(
            "review_next_prompt_count", current_count + REVIEW_SNOOZE_INTERVAL
        )
        self.dismiss_requested.emit()

    def no_thanks(self) -> None:
        self.config_manager.set("review_prompt_dismissed", True)
        self.dismiss_requested.emit()

    def shutdown(self) -> None:
        self._shutting_down = True
        worker, self._worker = self._worker, None
        if worker is not None:
            try:
                worker.finished.disconnect(self._on_submission_finished)
            except (TypeError, RuntimeError):
                pass


class ReviewPromptDialog(QDialog):
    """Native QDialog wrapper around ``ReviewPromptPanel``."""

    def __init__(self, parent=None, games_count: int = 3):
        super().__init__(parent)
        self.setWindowTitle("Rate Chess Analyzer Pro")
        self.setModal(True)
        self.resize(490, 470)
        self.setMinimumSize(450, 440)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.games_count = games_count
        self.panel = ReviewPromptPanel(games_count=games_count, parent=self)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        header_layout = QVBoxLayout()
        header_layout.setSpacing(6)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = Label(
            "Enjoying Chess Analyzer Pro?",
            role=TextRole.DIALOG_TITLE,
            weight=600,
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title)

        subtitle = Label(
            _subtitle_for(self.games_count),
            role=TextRole.BODY,
            tone=TextTone.SECONDARY,
            wrap=True,
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(subtitle)
        layout.addLayout(header_layout)

        layout.addWidget(self.panel, 1)

        self.btn_row_widget = QWidget()
        btn_layout = QHBoxLayout(self.btn_row_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(10)

        self.btn_skip = Button(
            "No, Thanks",
            ButtonVariant.LINK,
            tooltip="Close without leaving a review",
            on_click=self.panel.no_thanks,
        )
        btn_layout.addWidget(self.btn_skip)
        btn_layout.addStretch()

        self.btn_remind = Button(
            "Remind Later",
            ButtonVariant.HOLLOW,
            tooltip="Ask again the next time the review prompt is due",
            on_click=self.panel.remind_later,
        )
        btn_layout.addWidget(self.btn_remind)

        self.btn_submit = Button(
            "Submit Review",
            ButtonVariant.PRIMARY,
            icon="fa5s.paper-plane",
            tooltip="Send this rating and review",
            on_click=self.panel.submit_review,
        )
        btn_layout.addWidget(self.btn_submit)
        layout.addWidget(self.btn_row_widget)

        self.panel.submitting_changed.connect(self._on_submitting)
        self.panel.submitted.connect(self.btn_row_widget.hide)
        self.panel.done_requested.connect(self.accept)
        self.panel.dismiss_requested.connect(self.reject)

    def _on_submitting(self, submitting: bool) -> None:
        self.btn_submit.setEnabled(not submitting)
        self.btn_submit.setText("Submitting..." if submitting else "Submit Review")

    def reject(self) -> None:
        self.panel.shutdown()
        super().reject()

    def closeEvent(self, event) -> None:
        self.panel.shutdown()
        super().closeEvent(event)


def _subtitle_for(games_count: int) -> str:
    games_text = (
        f"You've analyzed {games_count} games!"
        if games_count > 0
        else "We'd love to hear your thoughts!"
    )
    return f"{games_text} Help us improve your chess training."


def open_review_prompt(parent, *, games_count: int = 3) -> None:
    """Open the review prompt panel as an in-window overlay."""
    if isinstance(parent, QWidget):
        try:
            manager = OverlayManager.for_window(parent)
            card = manager.create_card(
                title="Enjoying Chess Analyzer Pro?",
                description=_subtitle_for(games_count),
                max_width=500,
                minimum_width=380,
                dismiss_on_escape=True,
                dismiss_on_backdrop=False,
            )
            panel = ReviewPromptPanel(games_count=games_count, parent=card)
            card.set_content(panel)

            skip_btn = Button(
                "No, Thanks",
                ButtonVariant.LINK,
                tooltip="Close without leaving a review",
                on_click=panel.no_thanks,
            )
            remind_btn = Button(
                "Remind Later",
                ButtonVariant.HOLLOW,
                tooltip="Ask again the next time the review prompt is due",
                on_click=panel.remind_later,
            )
            submit_btn = Button(
                "Submit Review",
                ButtonVariant.PRIMARY,
                icon="fa5s.paper-plane",
                tooltip="Send this rating and review",
                on_click=panel.submit_review,
            )
            card.add_action(skip_btn)
            card.add_action(remind_btn)
            card.add_action(submit_btn, primary=True)

            def on_submitting(submitting: bool) -> None:
                submit_btn.set_loading(submitting)
                remind_btn.setEnabled(not submitting)
                skip_btn.setEnabled(not submitting)
                card.dismiss_on_escape = not submitting
                card.close_button.setVisible(not submitting)

            def on_submitted() -> None:
                card.footer.hide()
                card.notify_content_changed()

            panel.submitting_changed.connect(on_submitting)
            panel.submitted.connect(on_submitted)
            panel.done_requested.connect(card.accept)
            panel.dismiss_requested.connect(card.reject)
            panel.content_resized.connect(card.notify_content_changed)

            card.add_cleanup(panel.shutdown)
            manager.open(card)
            return
        except Exception:
            logger.warning("open_review_prompt overlay failed, falling back", exc_info=True)

    ReviewPromptDialog(parent, games_count=games_count).exec()

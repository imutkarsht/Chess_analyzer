# SPDX-License-Identifier: GPL-3.0-only
"""History widgets for the batch-analysis workflow."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from src.backend.models.analysis_batch import (
    BATCH_CANCELLED,
    BATCH_COMPLETED,
    BATCH_FAILED,
    BATCH_PAUSED,
    BATCH_RUNNING,
    AnalysisBatch,
)
from src.gui.components import (
    Button,
    ButtonSize,
    ButtonVariant,
    Label,
    MiniBar,
    StatusBadge,
    TextRole,
    TextTone,
)
from src.gui.styles import Styles


class BatchSelectionBar(QFrame):
    """Selection count and page/clear actions shown in History bulk mode."""

    select_page_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BatchSelectionBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(10)

        self.count_label = Label("0 selected", role=TextRole.BODY_STRONG, weight=600)
        layout.addWidget(self.count_label)
        layout.addStretch()

        self.btn_select_page = Button(
            "Select page",
            ButtonVariant.HOLLOW,
            ButtonSize.SM,
            on_click=lambda: self.select_page_requested.emit(),
        )
        self.btn_select_page.setAccessibleName("Select games on this page")
        layout.addWidget(self.btn_select_page)

        self.btn_clear = Button(
            "Clear selection",
            ButtonVariant.LINK,
            ButtonSize.SM,
            on_click=lambda: self.clear_requested.emit(),
        )
        self.btn_clear.setAccessibleName("Clear batch selection")
        layout.addWidget(self.btn_clear)

        self.btn_exit = Button(
            "Exit selection",
            ButtonVariant.LINK,
            ButtonSize.SM,
            on_click=lambda: self.exit_requested.emit(),
        )
        self.btn_exit.setAccessibleName("Exit batch selection mode")
        layout.addWidget(self.btn_exit)

        self.set_count(0)
        self.refresh_styles()

    def set_count(self, count: int) -> None:
        count = max(0, int(count))
        self.count_label.setText(f"{count:,} selected")
        self.btn_clear.setEnabled(count > 0)

    def set_page_available(self, available: bool) -> None:
        self.btn_select_page.setEnabled(bool(available))

    def refresh_styles(self) -> None:
        self.setStyleSheet(Styles.get_batch_selection_bar_style())
        self.btn_select_page.refresh_styles()
        self.btn_clear.refresh_styles()
        self.btn_exit.refresh_styles()


class BatchQueueCard(QFrame):
    """Progress and controls for the one persisted batch-analysis queue."""

    pause_requested = pyqtSignal()
    resume_requested = pyqtSignal()
    cancel_requested = pyqtSignal()
    dismiss_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BatchQueueCard")
        self._active_label = ""
        self._move_current = 0
        self._move_total = 0
        self._state = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.title_label = Label("", role=TextRole.BODY_STRONG, weight=700)
        header.addWidget(self.title_label)
        self.state_badge = StatusBadge("", TextTone.MUTED, font_size=11)
        header.addWidget(self.state_badge)
        header.addStretch()
        self.btn_pause = Button(
            "Pause",
            ButtonVariant.HOLLOW,
            ButtonSize.SM,
            icon="fa5s.pause",
            on_click=lambda: self.pause_requested.emit(),
        )
        self.btn_pause.setAccessibleName("Pause batch analysis")
        header.addWidget(self.btn_pause)
        self.btn_resume = Button(
            "Resume",
            ButtonVariant.PRIMARY,
            ButtonSize.SM,
            icon="fa5s.play",
            on_click=lambda: self.resume_requested.emit(),
        )
        self.btn_resume.setAccessibleName("Resume batch analysis")
        header.addWidget(self.btn_resume)
        self.btn_dismiss = Button(
            "Dismiss",
            ButtonVariant.HOLLOW,
            ButtonSize.SM,
            on_click=lambda: self.dismiss_requested.emit(),
        )
        self.btn_dismiss.setAccessibleName("Dismiss batch summary")
        header.addWidget(self.btn_dismiss)
        self.btn_cancel = Button(
            variant=ButtonVariant.GHOST,
            size=ButtonSize.SM,
            icon="fa5s.times",
            icon_position="only",
            tooltip="Cancel batch analysis",
            on_click=lambda: self.cancel_requested.emit(),
        )
        self.btn_cancel.setAccessibleName("Cancel batch analysis")
        header.addWidget(self.btn_cancel)
        root.addLayout(header)

        self.current_label = Label(
            "", role=TextRole.BODY, tone=TextTone.SECONDARY, wrap=True
        )
        root.addWidget(self.current_label)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(10)
        self.overall_bar = MiniBar(height=6)
        self.overall_bar.setAccessibleName("Batch progress")
        progress_row.addWidget(self.overall_bar, 1)
        self.overall_label = Label("", role=TextRole.MICRO, tone=TextTone.MUTED)
        progress_row.addWidget(self.overall_label)
        root.addLayout(progress_row)

        self.move_widget = QWidget()
        self.move_widget.setStyleSheet(Styles.get_transparent_style())
        self.move_row = QHBoxLayout(self.move_widget)
        self.move_row.setContentsMargins(0, 0, 0, 0)
        self.move_row.setSpacing(10)
        self.move_bar = MiniBar(height=4)
        self.move_bar.setAccessibleName("Current game move progress")
        self.move_row.addWidget(self.move_bar, 1)
        self.move_label = Label("", role=TextRole.MICRO, tone=TextTone.MUTED)
        self.move_row.addWidget(self.move_label)
        root.addWidget(self.move_widget)

        self.summary_label = Label(
            "", role=TextRole.CAPTION, tone=TextTone.SECONDARY, wrap=True
        )
        root.addWidget(self.summary_label)

        self.setVisible(False)
        self.refresh_styles()

    def show_batch(
        self,
        batch: AnalysisBatch,
        *,
        active_label: str = "",
        position: int = 0,
        move_current: int = 0,
        move_total: int = 0,
    ) -> None:
        self._state = batch.state
        self._active_label = active_label or self._active_label
        self._move_current = max(0, int(move_current))
        self._move_total = max(0, int(move_total))
        summary = batch.summary()

        if batch.state == BATCH_RUNNING:
            self._show_running(summary, position)
        elif batch.state == BATCH_PAUSED:
            self._show_paused(summary)
        else:
            self._show_summary(batch.state, summary)

    def hide_card(self) -> None:
        self.setVisible(False)
        self._state = ""

    def refresh_styles(self) -> None:
        self.setStyleSheet(Styles.get_batch_queue_card_style())
        self.btn_pause.refresh_styles()
        self.btn_resume.refresh_styles()
        self.btn_dismiss.refresh_styles()
        self.btn_cancel.refresh_styles()
        self.overall_bar.refresh_styles()
        self.move_bar.refresh_styles()

    def _show_running(self, summary, position: int) -> None:
        self.setVisible(True)
        total = max(1, summary.total)
        self.title_label.setText(
            f"Batch analysis · Game {position or summary.processed + 1} of {summary.total}"
        )
        self.state_badge.setText("Running")
        self.state_badge.set_tone(TextTone.ENGINE_BUSY)
        self.current_label.setText(
            self._active_label or "Preparing the next game…"
        )
        self.current_label.setVisible(True)
        self.overall_bar.setValue(round(100 * summary.processed / total))
        self.overall_label.setText(f"{summary.processed} of {summary.total} done")
        self.move_widget.setVisible(True)
        self._update_move_progress()
        self.summary_label.setVisible(False)
        self._set_running_buttons()

    def _show_paused(self, summary) -> None:
        self.setVisible(True)
        self.title_label.setText(
            f"Batch paused · {summary.processed} of {summary.total} done"
        )
        self.state_badge.setText("Paused")
        self.state_badge.set_tone(TextTone.INACCURACY)
        self.current_label.setText(
            f"Resume continues {self._active_label}." if self._active_label else
            "Resume continues from the first unanalyzed position."
        )
        self.current_label.setVisible(True)
        total = max(1, summary.total)
        self.overall_bar.setValue(round(100 * summary.processed / total))
        self.overall_label.setText(f"{summary.processed} of {summary.total} done")
        self.move_widget.setVisible(False)
        self.summary_label.setText(_summary_text(summary))
        self.summary_label.setVisible(True)
        self._set_paused_buttons()

    def _show_summary(self, state: str, summary) -> None:
        self.setVisible(True)
        titles = {
            BATCH_COMPLETED: "Batch complete",
            BATCH_CANCELLED: "Batch cancelled",
            BATCH_FAILED: "Batch stopped",
        }
        self.title_label.setText(titles.get(state, "Batch finished"))
        tone = {
            BATCH_COMPLETED: TextTone.ENGINE_READY,
            BATCH_CANCELLED: TextTone.INACCURACY,
            BATCH_FAILED: TextTone.BLUNDER,
        }.get(state, TextTone.MUTED)
        self.state_badge.setText("Complete" if state == BATCH_COMPLETED else "Ended")
        self.state_badge.set_tone(tone)
        self.current_label.setVisible(False)
        self.overall_bar.setValue(
            round(100 * summary.processed / max(1, summary.total))
        )
        self.overall_label.setText(f"{summary.processed} of {summary.total} done")
        self.move_widget.setVisible(False)
        self.summary_label.setText(_summary_text(summary))
        self.summary_label.setVisible(True)
        self._set_summary_buttons()

    def _update_move_progress(self) -> None:
        if self._move_total <= 0:
            self.move_widget.setVisible(False)
            return
        self.move_widget.setVisible(True)
        self.move_bar.setValue(
            round(100 * min(self._move_current, self._move_total) / self._move_total)
        )
        self.move_label.setText(
            f"move {min(self._move_current, self._move_total)} / {self._move_total}"
        )

    def set_move_progress(self, current: int, total: int) -> None:
        self._move_current = max(0, int(current))
        self._move_total = max(0, int(total))
        if self._state == BATCH_RUNNING:
            self._update_move_progress()

    def _set_running_buttons(self) -> None:
        self.btn_pause.setVisible(True)
        self.btn_pause.setEnabled(True)
        self.btn_resume.setVisible(False)
        self.btn_dismiss.setVisible(False)
        self.btn_cancel.setVisible(True)

    def _set_paused_buttons(self) -> None:
        self.btn_pause.setVisible(False)
        self.btn_resume.setVisible(True)
        self.btn_resume.setEnabled(True)
        self.btn_dismiss.setVisible(False)
        self.btn_cancel.setVisible(True)

    def _set_summary_buttons(self) -> None:
        self.btn_pause.setVisible(False)
        self.btn_resume.setVisible(False)
        self.btn_dismiss.setVisible(True)
        self.btn_cancel.setVisible(False)


def _summary_text(summary) -> str:
    parts = []
    if summary.completed:
        parts.append(f"{summary.completed} completed")
    if summary.skipped:
        parts.append(f"{summary.skipped} skipped")
    if summary.failed:
        parts.append(f"{summary.failed} failed")
    if summary.paused:
        parts.append(f"{summary.paused} paused")
    if summary.not_started:
        parts.append(f"{summary.not_started} not started")
    if summary.pending:
        parts.append(f"{summary.pending} remaining")
    return " · ".join(parts) if parts else "No games processed."

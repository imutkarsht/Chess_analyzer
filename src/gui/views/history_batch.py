# SPDX-License-Identifier: GPL-3.0-only
"""History widgets for the batch-analysis workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from PyQt6 import sip
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

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
    ElidedLabel,
    IconLabel,
    Label,
    MiniBar,
    StatusBadge,
    TextRole,
    TextTone,
)
from src.gui.styles import Styles
from src.utils.format_utils import format_clock


@dataclass(frozen=True)
class UpNextEntry:
    """One pending queue row shown in the card's reorderable list."""

    game_id: str
    label: str
    moves: int
    eta_seconds: float | None = None
    number: int = 0


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
        """Selection-bar chrome is global; buttons self-refresh."""
        self.style().unpolish(self)
        self.style().polish(self)


class _QueueRow(QWidget):
    """One draggable Up next row with a remove action."""

    remove_requested = pyqtSignal(str)
    drag_requested = pyqtSignal(str)

    def __init__(self, number: int, entry: UpNextEntry, parent=None):
        super().__init__(parent)
        self.entry = entry
        self._drag_start = None
        self.setFixedHeight(42)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 8, 6)
        layout.setSpacing(10)

        self.number_label = Label(
            str(entry.number or number), role=TextRole.MICRO, tone=TextTone.MUTED
        )
        self.number_label.setFixedWidth(18)
        layout.addWidget(self.number_label)

        name = ElidedLabel(entry.label, role=TextRole.BODY, weight=600)
        name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(name, 1)

        moves = Label(
            f"{entry.moves} moves" if entry.moves else "—",
            role=TextRole.MICRO,
            tone=TextTone.MUTED,
        )
        layout.addWidget(moves)

        self.eta_label = Label(
            f"~{format_clock(entry.eta_seconds, pad_minutes=True, round_seconds=True)}"
            if entry.eta_seconds is not None
            else "—",
            role=TextRole.MICRO,
            tone=TextTone.MUTED,
        )
        self.eta_label.setMinimumWidth(58)
        self.eta_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self.eta_label)

        handle = IconLabel(size=16)
        handle.set_icon("fa5s.grip-vertical")
        handle.setToolTip("Drag to reorder")
        layout.addWidget(handle)

        self.remove_button = Button(
            variant=ButtonVariant.GHOST,
            size=ButtonSize.SM,
            icon="fa5s.times",
            icon_position="only",
            tooltip="Remove from this batch",
            on_click=lambda: self.remove_requested.emit(self.entry.game_id),
        )
        self.remove_button.setFixedSize(24, 24)
        self.remove_button.setAccessibleName("Remove game from batch")
        layout.addWidget(self.remove_button)

        for child in (self.number_label, name, self.eta_label, moves, handle):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_number(self, number: int) -> None:
        self.number_label.setText(str(number))

    def set_eta(self, eta_seconds: float | None) -> None:
        self.eta_label.setText(
            f"~{format_clock(eta_seconds, pad_minutes=True, round_seconds=True)}"
            if eta_seconds is not None
            else "—"
        )

    def mousePressEvent(self, event):
        if sip.isdeleted(self):
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if sip.isdeleted(self):
            return
        if (
            self._drag_start is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and (event.position().toPoint() - self._drag_start).manhattanLength()
            >= QApplication.startDragDistance()
        ):
            self._drag_start = None
            self.drag_requested.emit(self.entry.game_id)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if sip.isdeleted(self):
            return
        self._drag_start = None
        super().mouseReleaseEvent(event)

    def refresh_styles(self) -> None:
        """Row chrome is global; the remove button self-refreshes."""
        return


class _ReorderList(QListWidget):
    """Internal-move list used by the Up next section."""

    drag_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BatchUpNextList")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSpacing(0)
        self.setUniformItemSizes(True)
        self._dragging = False

    @property
    def is_dragging(self) -> bool:
        return self._dragging

    def startDrag(self, supported_actions):
        self._dragging = True
        try:
            super().startDrag(supported_actions)
        finally:
            self._dragging = False
            self.drag_finished.emit()

    def begin_drag(self, game_id: str) -> None:
        for row in range(self.count()):
            item = self.item(row)
            widget = self.itemWidget(item)
            if isinstance(widget, _QueueRow) and widget.entry.game_id == game_id:
                self.setCurrentItem(item)
                self.startDrag(Qt.DropAction.MoveAction)
                return


class BatchQueueCard(QFrame):
    """Polished status card for the one persisted batch-analysis queue."""

    pause_requested = pyqtSignal()
    resume_requested = pyqtSignal()
    cancel_requested = pyqtSignal()
    dismiss_requested = pyqtSignal()
    collapse_requested = pyqtSignal()
    reorder_requested = pyqtSignal(object)
    remove_requested = pyqtSignal(str)
    up_next_refresh_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BatchQueueCard")
        self.setMaximumWidth(980)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._active_label = ""
        self._move_current = 0
        self._move_total = 0
        self._game_eta_seconds: float | None = None
        self._game_elapsed_seconds = 0.0
        self._elapsed_seconds = 0.0
        self._eta_seconds: float | None = None
        self._depth: int | None = None
        self._state = ""
        self._populating_up_next = False
        self._up_next: list[UpNextEntry] = []
        self._pending_up_next: list[UpNextEntry] | None = None
        self._up_next_dirty = False

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        # Header: status dot, title, state, actions.
        header = QHBoxLayout()
        header.setSpacing(8)
        dot = Label("●", role=TextRole.BODY, tone=TextTone.ACCENT)
        header.addWidget(dot)
        self.title_label = Label("Batch analysis", role=TextRole.BODY_LARGE, weight=700)
        header.addWidget(self.title_label)
        self.state_badge = StatusBadge("", TextTone.MUTED, font_size=11)
        header.addWidget(self.state_badge)
        header.addStretch()

        self.btn_pause = Button(
            "Pause",
            ButtonVariant.HOLLOW,
            ButtonSize.MD,
            icon="fa5s.pause",
            on_click=lambda: self.pause_requested.emit(),
        )
        self.btn_pause.setAccessibleName("Pause batch analysis")
        header.addWidget(self.btn_pause)

        self.btn_resume = Button(
            "Resume",
            ButtonVariant.PRIMARY,
            ButtonSize.MD,
            icon="fa5s.play",
            on_click=lambda: self.resume_requested.emit(),
        )
        self.btn_resume.setAccessibleName("Resume batch analysis")
        header.addWidget(self.btn_resume)

        self.btn_dismiss = Button(
            "Dismiss",
            ButtonVariant.HOLLOW,
            ButtonSize.MD,
            on_click=lambda: self.dismiss_requested.emit(),
        )
        self.btn_dismiss.setAccessibleName("Dismiss batch summary")
        header.addWidget(self.btn_dismiss)

        self.btn_collapse = Button(
            variant=ButtonVariant.GHOST,
            size=ButtonSize.MD,
            icon="fa5s.chevron-up",
            icon_position="only",
            tooltip="Collapse batch details",
            on_click=lambda: self.collapse_requested.emit(),
        )
        self.btn_collapse.setAccessibleName("Collapse batch details")
        self.btn_collapse.setFixedSize(36, 36)
        header.addWidget(self.btn_collapse)

        self.btn_cancel = Button(
            variant=ButtonVariant.GHOST,
            size=ButtonSize.MD,
            icon="fa5s.times",
            icon_position="only",
            tooltip="Cancel batch analysis",
            on_click=lambda: self.cancel_requested.emit(),
        )
        self.btn_cancel.setAccessibleName("Cancel batch analysis")
        self.btn_cancel.setFixedSize(36, 36)
        header.addWidget(self.btn_cancel)
        root.addLayout(header)

        # Four summary tiles.
        stats = QHBoxLayout()
        stats.setSpacing(10)
        self.progress_value = self._add_stat_tile(stats, "Progress")
        self.elapsed_value = self._add_stat_tile(stats, "Elapsed")
        self.eta_value = self._add_stat_tile(stats, "ETA")
        self.finish_value = self._add_stat_tile(stats, "Finishes at")
        root.addLayout(stats)

        # Whole-batch progress.
        overall_row = QHBoxLayout()
        overall_row.setSpacing(8)
        overall_row.addWidget(
            Label("Overall", role=TextRole.BODY, tone=TextTone.SECONDARY)
        )
        overall_row.addStretch()
        self.overall_percent = Label("", role=TextRole.CAPTION, tone=TextTone.SECONDARY)
        overall_row.addWidget(self.overall_percent)
        root.addLayout(overall_row)
        self.overall_bar = MiniBar(height=8, radius=4)
        self.overall_bar.setAccessibleName("Batch progress")
        root.addWidget(self.overall_bar)

        # Current game panel.
        self.current_panel = QFrame()
        self.current_panel.setObjectName("BatchCurrentGame")
        current_layout = QVBoxLayout(self.current_panel)
        current_layout.setContentsMargins(14, 12, 14, 12)
        current_layout.setSpacing(8)

        current_head = QHBoxLayout()
        current_head.setSpacing(8)
        self.game_title = ElidedLabel("", role=TextRole.BODY_LARGE, weight=700)
        self.game_title.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        current_head.addWidget(self.game_title, 1)
        self.game_position = Label("", role=TextRole.CAPTION, tone=TextTone.SECONDARY)
        current_head.addWidget(self.game_position)
        current_layout.addLayout(current_head)

        move_head = QHBoxLayout()
        move_head.setSpacing(8)
        self.move_label = Label("", role=TextRole.CAPTION, tone=TextTone.SECONDARY)
        move_head.addWidget(self.move_label)
        move_head.addStretch()
        self.move_percent = Label("", role=TextRole.CAPTION, tone=TextTone.SECONDARY)
        move_head.addWidget(self.move_percent)
        current_layout.addLayout(move_head)

        self.move_bar = MiniBar(height=6, radius=3)
        self.move_bar.setAccessibleName("Current game move progress")
        current_layout.addWidget(self.move_bar)

        self.game_meta = Label("", role=TextRole.MICRO, tone=TextTone.MUTED)
        self.game_meta.setWordWrap(True)
        current_layout.addWidget(self.game_meta)
        root.addWidget(self.current_panel)

        # Up next, with drag reorder.
        self.up_next_container = QWidget()
        Styles.apply_transparent(self.up_next_container)
        up_next_layout = QVBoxLayout(self.up_next_container)
        up_next_layout.setContentsMargins(0, 0, 0, 0)
        up_next_layout.setSpacing(6)
        up_next_layout.addWidget(
            Label("Up next", role=TextRole.BODY, tone=TextTone.SECONDARY)
        )
        self.up_next_list = _ReorderList()
        self.up_next_list.model().rowsMoved.connect(self._on_rows_moved)
        self.up_next_list.drag_finished.connect(self._apply_pending_up_next)
        up_next_layout.addWidget(self.up_next_list)
        root.addWidget(self.up_next_container)

        self.summary_label = Label(
            "", role=TextRole.CAPTION, tone=TextTone.SECONDARY, wrap=True
        )
        root.addWidget(self.summary_label)

        footer = QHBoxLayout()
        footer.setSpacing(12)
        self.footer_hint = Label(
            "ETA is based on your average speed so far and improves as games finish",
            role=TextRole.MICRO,
            tone=TextTone.MUTED,
        )
        footer.addWidget(self.footer_hint, 1)
        self.footer_status = Label(
            "Analysis continues if you leave this page",
            role=TextRole.MICRO,
            tone=TextTone.MUTED,
        )
        footer.addWidget(self.footer_status)
        root.addLayout(footer)

        self.setVisible(False)
        self.refresh_styles()

    @staticmethod
    def _add_stat_tile(layout: QHBoxLayout, caption: str) -> Label:
        tile = QFrame()
        tile.setObjectName("BatchStatTile")
        tile_layout = QVBoxLayout(tile)
        tile_layout.setContentsMargins(12, 8, 12, 8)
        tile_layout.setSpacing(1)
        tile_layout.addWidget(
            Label(caption, role=TextRole.MICRO, tone=TextTone.SECONDARY)
        )
        value = Label("", role=TextRole.STAT, weight=700)
        tile_layout.addWidget(value)
        layout.addWidget(tile, 1)
        return value

    def show_batch(
        self,
        batch: AnalysisBatch,
        *,
        active_label: str | None = None,
        position: int = 0,
        move_current: int = 0,
        move_total: int = 0,
        elapsed_seconds: float | None = None,
        eta_seconds: float | None = None,
        game_elapsed_seconds: float | None = None,
        depth: int | None = None,
        reveal: bool = True,
    ) -> None:
        self._state = batch.state
        if active_label is not None:
            self._active_label = active_label
        self._move_current = max(0, int(move_current))
        self._move_total = max(0, int(move_total))
        self._game_eta_seconds = None
        if game_elapsed_seconds is not None:
            self._game_elapsed_seconds = max(0.0, float(game_elapsed_seconds))
        if depth is not None:
            self._depth = int(depth)
        if elapsed_seconds is not None:
            self._elapsed_seconds = max(0.0, float(elapsed_seconds))
        elif self._elapsed_seconds <= 0:
            self._elapsed_seconds = max(0.0, float(batch.elapsed_seconds or 0.0))
        self._eta_seconds = eta_seconds
        summary = batch.summary()

        if batch.state == BATCH_RUNNING:
            self._show_running(summary, position)
        elif batch.state == BATCH_PAUSED:
            self._show_paused(summary, position)
        else:
            self._show_summary(batch.state, summary)
        self.setVisible(reveal)

    def hide_card(self) -> None:
        self.setVisible(False)
        self._state = ""
        self._up_next = []
        self._pending_up_next = None
        self.set_up_next([])

    def refresh_styles(self) -> None:
        """Card chrome is global; only the data-driven mini bars need repainting."""
        for bar in (self.overall_bar, self.move_bar):
            bar.set_color(Styles.COLOR_ACCENT)
            bar.set_track_color(Styles.COLOR_BORDER)
            bar.refresh_styles()

    def set_up_next(self, entries: list[UpNextEntry]) -> None:
        if self.up_next_list.is_dragging:
            # Rebuilding the list while Qt is inside startDrag() deletes the
            # row widget still receiving mouse events. Apply after the drop.
            self._pending_up_next = list(entries)
            return
        old_signature = [
            (entry.game_id, entry.number, entry.moves) for entry in self._up_next
        ]
        new_signature = [
            (entry.game_id, entry.number, entry.moves) for entry in entries
        ]
        self._up_next = list(entries)
        self._up_next_dirty = True
        if not self.isVisible():
            return
        if (
            old_signature == new_signature
            and self.up_next_list.count() == len(entries)
        ):
            for row, entry in enumerate(entries):
                widget = self.up_next_list.itemWidget(self.up_next_list.item(row))
                if isinstance(widget, _QueueRow):
                    widget.set_eta(entry.eta_seconds)
            self._up_next_dirty = False
            self._update_up_next_visibility()
            return
        self._rebuild_up_next()

    def _rebuild_up_next(self) -> None:
        entries = self._up_next
        self._populating_up_next = True
        try:
            self.up_next_list.clear()
            for number, entry in enumerate(entries, start=1):
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 42))
                row = _QueueRow(number, entry)
                row.remove_requested.connect(self.remove_requested.emit)
                row.drag_requested.connect(self.up_next_list.begin_drag)
                self.up_next_list.addItem(item)
                self.up_next_list.setItemWidget(item, row)
            rows = min(3, max(1, len(entries)))
            self.up_next_list.setFixedHeight(42 * rows + 2)
        finally:
            self._populating_up_next = False
        self._up_next_dirty = False
        self._update_up_next_visibility()

    def remove_up_next(self, game_id: str) -> None:
        was_dirty = self._up_next_dirty
        self._up_next = [
            entry for entry in self._up_next if entry.game_id != game_id
        ]
        if self.up_next_list.is_dragging or not self.isVisible():
            self._up_next_dirty = True
            return
        if was_dirty:
            self._rebuild_up_next()
            return
        for row in range(self.up_next_list.count()):
            item = self.up_next_list.item(row)
            widget = self.up_next_list.itemWidget(item)
            if isinstance(widget, _QueueRow) and widget.entry.game_id == game_id:
                self.up_next_list.takeItem(row)
                widget.deleteLater()
                break
        numbers = sorted(entry.number for entry in self._up_next if entry.number)
        if len(numbers) != len(self._up_next):
            numbers = list(range(1, len(self._up_next) + 1))
        for row, number in enumerate(numbers):
            item = self.up_next_list.item(row)
            widget = self.up_next_list.itemWidget(item) if item is not None else None
            if isinstance(widget, _QueueRow):
                widget.set_number(number)
        self._up_next_dirty = False
        self._update_up_next_visibility()

    def _update_up_next_visibility(self) -> None:
        self.up_next_container.setVisible(
            bool(self._up_next) and self._state in (BATCH_RUNNING, BATCH_PAUSED)
        )

    def _apply_pending_up_next(self) -> None:
        if self._pending_up_next is None:
            return
        self._pending_up_next = None
        self._up_next_dirty = True
        self.up_next_refresh_requested.emit()

    def showEvent(self, event):
        super().showEvent(event)
        if self._up_next_dirty:
            self._rebuild_up_next()

    def set_timing(self, elapsed_seconds: float, eta_seconds: float | None) -> None:
        self._elapsed_seconds = max(0.0, float(elapsed_seconds))
        self._eta_seconds = eta_seconds
        self._update_stats()

    def set_move_progress(
        self,
        current: int,
        total: int,
        game_eta_seconds: float | None = None,
        game_elapsed_seconds: float | None = None,
    ) -> None:
        self._move_current = max(0, int(current))
        self._move_total = max(0, int(total))
        self._game_eta_seconds = game_eta_seconds
        if game_elapsed_seconds is not None:
            self._game_elapsed_seconds = max(0.0, float(game_elapsed_seconds))
        if self._state == BATCH_RUNNING:
            self._update_current_panel()

    def _show_running(self, summary, position: int) -> None:
        self.title_label.setText("Batch analysis")
        self.state_badge.setText("Running")
        self.state_badge.set_tone(TextTone.ENGINE_BUSY)
        self.state_badge.setVisible(True)
        self._update_stats()
        self._update_overall(summary)
        self.game_title.setText(self._active_label or "Preparing the next game…")
        self.game_position.setText(f"Game {position or summary.processed + 1} of {summary.total}")
        self._update_current_panel()
        self.current_panel.setVisible(True)
        self.up_next_container.setVisible(bool(self._up_next))
        self.summary_label.setVisible(False)
        self.footer_hint.setVisible(True)
        self.footer_status.setVisible(True)
        self._set_running_buttons()

    def _show_paused(self, summary, position: int) -> None:
        self.title_label.setText("Batch paused")
        self.state_badge.setText("Paused")
        self.state_badge.set_tone(TextTone.INACCURACY)
        self.state_badge.setVisible(True)
        self._update_stats()
        self._update_overall(summary)
        self.game_title.setText(self._active_label or "Ready to resume")
        self.game_position.setText(
            f"Game {position or summary.processed + 1} of {summary.total}"
        )
        self._update_current_panel()
        self.current_panel.setVisible(True)
        self.up_next_container.setVisible(bool(self._up_next))
        self.summary_label.setText(_summary_text(summary))
        self.summary_label.setVisible(True)
        self.footer_hint.setVisible(False)
        self.footer_status.setVisible(False)
        self._set_paused_buttons()

    def _show_summary(self, state: str, summary) -> None:
        titles = {
            BATCH_COMPLETED: "Batch complete",
            BATCH_CANCELLED: "Batch cancelled",
            BATCH_FAILED: "Batch stopped",
        }
        if state == BATCH_COMPLETED and summary.failed:
            title = "Batch finished with failures"
        else:
            title = titles.get(state, "Batch finished")
        self.title_label.setText(title)
        self.state_badge.setVisible(False)
        self._update_stats()
        self._update_overall(summary)
        self.current_panel.setVisible(False)
        self.up_next_container.setVisible(False)
        self.summary_label.setText(_summary_text(summary))
        self.summary_label.setVisible(True)
        self.footer_hint.setVisible(False)
        self.footer_status.setVisible(False)
        self._set_summary_buttons()

    def _update_stats(self) -> None:
        total = max(0, getattr(self, "_summary_total", 0))
        processed = min(getattr(self, "_summary_processed", 0), total)
        self.progress_value.setText(f"{processed} / {total}")
        self.elapsed_value.setText(
            format_clock(self._elapsed_seconds, pad_minutes=True, round_seconds=True)
        )
        self.eta_value.setText(
            f"~{format_clock(self._eta_seconds, pad_minutes=True, round_seconds=True)}"
            if self._eta_seconds is not None
            else "—"
        )
        if self._eta_seconds is not None:
            finish = datetime.now() + timedelta(seconds=max(0, self._eta_seconds))
            self.finish_value.setText(finish.strftime("%I:%M %p").lstrip("0"))
        else:
            self.finish_value.setText("—")

    def _update_overall(self, summary) -> None:
        self._summary_total = summary.total
        self._summary_processed = min(summary.processed, summary.total)
        total = max(1, summary.total)
        percent = round(100 * self._summary_processed / total)
        self.overall_bar.setValue(percent)
        self.overall_percent.setText(f"{percent}%")
        self._update_stats()

    def _update_current_panel(self) -> None:
        current = min(self._move_current, self._move_total)
        percent = (
            round(100 * current / self._move_total) if self._move_total else 0
        )
        self.move_label.setText(f"Move {current} / {self._move_total}")
        self.move_percent.setText(f"{percent}%")
        self.move_bar.setValue(percent)

        parts = []
        if self._game_elapsed_seconds > 0:
            parts.append(
                f"Game elapsed {format_clock(self._game_elapsed_seconds, pad_minutes=True, round_seconds=True)}"
            )
        if self._game_eta_seconds is not None:
            parts.append(
                f"Left ~{format_clock(self._game_eta_seconds, pad_minutes=True, round_seconds=True)}"
            )
        if current > 0 and self._game_elapsed_seconds > 0:
            speed = current / max(0.001, self._game_elapsed_seconds)
            parts.append(f"Speed {speed:.1f} moves/s")
        if self._depth is not None:
            parts.append(f"Depth {self._depth}")
        self.game_meta.setText("   ·   ".join(parts))
        self.game_meta.setVisible(bool(parts))

    def _on_rows_moved(self, *_args) -> None:
        if self._populating_up_next or sip.isdeleted(self.up_next_list):
            return
        rows = []
        order = []
        for row in range(self.up_next_list.count()):
            widget = self.up_next_list.itemWidget(self.up_next_list.item(row))
            if isinstance(widget, _QueueRow):
                rows.append(widget)
                order.append(widget.entry.game_id)
        if not order:
            return
        numbers = sorted(entry.number for entry in self._up_next if entry.number)
        if len(numbers) != len(rows):
            numbers = list(range(1, len(rows) + 1))
        for row, number in zip(rows, numbers, strict=True):
            row.set_number(number)
        by_id = {entry.game_id: entry for entry in self._up_next}
        reordered = []
        for game_id, number in zip(order, numbers, strict=True):
            entry = by_id.get(game_id)
            if entry is not None:
                reordered.append(
                    UpNextEntry(
                        entry.game_id,
                        entry.label,
                        entry.moves,
                        entry.eta_seconds,
                        number,
                    )
                )
        self._up_next = reordered
        self.reorder_requested.emit(order)

    def _set_running_buttons(self) -> None:
        self.btn_pause.setVisible(True)
        self.btn_pause.setEnabled(True)
        self.btn_pause.setText("Pause")
        self.btn_resume.setVisible(False)
        self.btn_dismiss.setVisible(False)
        self.btn_cancel.setVisible(True)
        self.btn_cancel.setEnabled(True)

    def _set_paused_buttons(self) -> None:
        self.btn_pause.setVisible(False)
        self.btn_resume.setVisible(True)
        self.btn_resume.setEnabled(True)
        self.btn_dismiss.setVisible(False)
        self.btn_cancel.setVisible(True)
        self.btn_cancel.setEnabled(True)

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
    return "  ·  ".join(parts) if parts else "No games processed."




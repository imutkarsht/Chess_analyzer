"""Dedicated game import workspace, hosted by the History page."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.backend.storage.game_history import GameHistoryManager
from src.gui.components import (
    Button,
    ButtonSize,
    ButtonVariant,
    Input,
    InputSize,
    InputVariant,
    Label,
    MiniBar,
    SegmentedControl,
    Select,
    SelectSize,
    StatusBadge,
    TextRole,
    TextTone,
)
from src.gui.components.feedback.toast import ToastManager
from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.gui.utils.debounce import Debouncer
from src.utils.config import ConfigManager

from .batch import GameBatch, GameCandidate
from .boards import MiniBoardFenWorker, register_worker, remove_worker
from .delegates import (
    BoardDelegate,
    CheckboxDelegate,
    CheckboxHeader,
    StatusPillDelegate,
)
from .model import (
    COL_BOARD,
    COL_DETAILS,
    COL_MOVES,
    GameImportFilterProxy,
    GameImportTableModel,
)
from .worker import (
    GameImportWorker,
)
from .worker import (
    register_worker as register_import_worker,
)
from .worker import (
    remove_worker as remove_import_worker,
)

_ROWS_WITH_BOARDS = 80
_ROWS_COMPACT = 44


class GameImportView(QWidget):
    """Full-page import table with selection and a single-game open action."""

    back_requested = pyqtSignal()
    open_game_requested = pyqtSignal(str, object)  # (pgn_text, source_data)
    games_added = pyqtSignal(int, int)  # (inserted, skipped)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._batch: GameBatch | None = None
        self._config = ConfigManager()
        self._history_manager = GameHistoryManager()
        self._import_worker: GameImportWorker | None = None
        self._fen_worker: MiniBoardFenWorker | None = None
        self._fen_token = 0
        self._fen_queued = False
        self._fen_requested: set[int] = set()
        self._fen_failed: set[int] = set()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._setup_ui()

        manager = ThemeManager.instance()
        manager.theme_changed.connect(self._on_theme_changed)
        manager.accent_changed.connect(self._on_theme_changed)

    def _setup_ui(self) -> None:
        Styles.apply_background(self)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header_bar = QFrame()
        self.header_bar.setObjectName("ImportHeader")
        header = QHBoxLayout(self.header_bar)
        header.setContentsMargins(24, 14, 24, 14)
        header.setSpacing(12)

        self.btn_back = Button(
            "Back to History",
            ButtonVariant.HOLLOW,
            ButtonSize.SM,
            icon="fa5s.arrow-left",
            on_click=self.back_requested.emit,
        )
        header.addWidget(self.btn_back)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.lbl_title = Label(
            "Import games", role=TextRole.DIALOG_TITLE, weight=700
        )
        self.lbl_subtitle = Label(
            "", role=TextRole.CAPTION, tone=TextTone.SECONDARY
        )
        title_box.addWidget(self.lbl_title)
        title_box.addWidget(self.lbl_subtitle)
        header.addLayout(title_box, 1)

        self.badge_count = StatusBadge(
            "0 games",
            TextTone.ACCENT,
            variant="quiet",
            font_size=11,
            weight=700,
            padding="4px 10px",
            radius=10,
        )
        self.badge_saved = StatusBadge(
            "0 in history",
            TextTone.SECONDARY,
            variant="quiet",
            font_size=11,
            weight=600,
            padding="4px 10px",
            radius=10,
        )
        header.addWidget(self.badge_count)
        header.addWidget(self.badge_saved)
        root.addWidget(self.header_bar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.surface = QWidget()
        surface_layout = QVBoxLayout(self.surface)
        surface_layout.setContentsMargins(0, 0, 0, 0)
        surface_layout.setSpacing(0)

        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(24, 12, 24, 12)
        toolbar_layout.setSpacing(8)

        self.search_input = Input(
            placeholder="Filter games…",
            variant=InputVariant.SEARCH,
            size=InputSize.SM,
            clearable=True,
        )
        self.search_input.setMinimumWidth(220)
        self.search_input.setMaximumWidth(380)
        self._search_debounce = Debouncer(self, interval=150)
        self.search_input.textChanged.connect(
            lambda *_: self._search_debounce.call(self._apply_filters)
        )
        toolbar_layout.addWidget(self.search_input, 1)

        self.result_filter = Select(
            [
                ("All results", "all"),
                ("White win", "1-0"),
                ("Black win", "0-1"),
                ("Draw", "1/2-1/2"),
            ],
            size=SelectSize.SM,
            min_width=110,
            on_change=lambda _value: self._apply_filters(),
        )
        self.time_filter = Select(
            [
                ("All speeds", "all"),
                ("Bullet", "Bullet"),
                ("Blitz", "Blitz"),
                ("Rapid", "Rapid"),
                ("Classical", "Classical"),
                ("Daily", "Daily"),
                ("Unknown", "Unknown"),
            ],
            size=SelectSize.SM,
            min_width=110,
            on_change=lambda _value: self._apply_filters(),
        )
        self.history_filter = SegmentedControl(
            [("All", "all"), ("New", "new"), ("Saved", "saved")],
            value="all",
        )
        self.history_filter.valueChanged.connect(
            lambda _value: self._apply_filters()
        )
        toolbar_layout.addWidget(self.result_filter)
        toolbar_layout.addWidget(self.time_filter)
        toolbar_layout.addWidget(self.history_filter)

        self.lbl_filtered = Label(
            "",
            role=TextRole.CAPTION,
            tone=TextTone.MUTED,
        )
        toolbar_layout.addWidget(self.lbl_filtered)

        self.btn_clear_selection = Button(
            "Clear",
            ButtonVariant.GHOST,
            ButtonSize.SM,
            on_click=self._clear_selection,
        )
        self.btn_boards = Button(
            "Boards",
            ButtonVariant.GHOST,
            ButtonSize.SM,
            icon="fa5s.chess-board",
            checkable=True,
            tooltip="Show board thumbnails",
            on_click=self._on_boards_toggled,
        )
        toolbar_layout.addWidget(self.btn_clear_selection)
        toolbar_layout.addWidget(self.btn_boards)
        surface_layout.addWidget(toolbar)

        self.model = GameImportTableModel(self)
        self.proxy = GameImportFilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(Qt.ItemDataRole.UserRole + 1)
        self.proxy.setDynamicSortFilter(True)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.header = CheckboxHeader(Qt.Orientation.Horizontal, self.table)
        self.table.setHorizontalHeader(self.header)
        self.header.setStretchLastSection(False)
        self.header.setFixedHeight(40)
        self.header.setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.header.toggled.connect(self._on_header_toggled)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(1, 84)
        self.table.setColumnWidth(2, 118)
        self.table.setColumnWidth(5, 76)
        self.table.setColumnWidth(6, 88)
        self.table.setColumnWidth(7, 64)
        self.table.setColumnWidth(9, 104)
        self.header.setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self.header.setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        self.header.setSectionResizeMode(
            8, QHeaderView.ResizeMode.Stretch
        )
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(2, Qt.SortOrder.DescendingOrder)
        self.table.doubleClicked.connect(self._on_double_clicked)
        self.table.setItemDelegateForColumn(0, CheckboxDelegate(self.table))
        self.table.setItemDelegateForColumn(1, BoardDelegate(self.table))
        self.table.setItemDelegateForColumn(9, StatusPillDelegate(self.table))
        surface_layout.addWidget(self.table, 1)

        self.action_bar = QFrame()
        self.action_bar.setObjectName("ImportActionBar")
        actions = QHBoxLayout(self.action_bar)
        actions.setContentsMargins(24, 12, 24, 12)
        actions.setSpacing(10)

        self.lbl_selection = Label(
            "0 of 0 row(s) selected.",
            role=TextRole.CAPTION,
            tone=TextTone.SECONDARY,
        )
        actions.addWidget(self.lbl_selection)

        self._import_label = Label(
            "",
            role=TextRole.CAPTION,
            tone=TextTone.SECONDARY,
        )
        self._import_progress = MiniBar(0)
        self._import_progress.setFixedWidth(180)
        self._import_label.setVisible(False)
        self._import_progress.setVisible(False)
        actions.addWidget(self._import_label)
        actions.addWidget(self._import_progress)
        actions.addStretch(1)

        self.btn_add = Button(
            "Add to history",
            ButtonVariant.HOLLOW,
            ButtonSize.MD,
            icon="fa5s.database",
            on_click=self._add_selected,
        )
        self.btn_add.setEnabled(False)
        actions.addWidget(self.btn_add)

        self.btn_open = Button(
            "Open game",
            ButtonVariant.PRIMARY,
            ButtonSize.MD,
            icon="fa5s.play",
            on_click=self._open_checked,
        )
        self.btn_open.setEnabled(False)
        actions.addWidget(self.btn_open)
        surface_layout.addWidget(self.action_bar)

        content_layout.addWidget(self.surface)
        root.addWidget(content, 1)

        self.model.selection_changed.connect(self._on_selection_changed)
        self.table.selectionModel().currentRowChanged.connect(
            lambda *_args: self._on_selection_changed(
                self.model.checked_count()
            )
        )
        self._fen_timer = QTimer(self)
        self._fen_timer.setSingleShot(True)
        self._fen_timer.setInterval(120)
        self._fen_timer.timeout.connect(self._request_visible_fens)
        self.table.verticalScrollBar().valueChanged.connect(
            lambda _value: self._fen_timer.start()
        )
        self.table.verticalScrollBar().rangeChanged.connect(
            lambda *_args: self._fen_timer.start()
        )
        self.proxy.modelReset.connect(lambda: self._fen_timer.start())
        self.proxy.layoutChanged.connect(lambda: self._fen_timer.start())
        self.header.sortIndicatorChanged.connect(
            lambda *_args: self._fen_timer.start()
        )
        self._apply_board_visibility(
            bool(self._config.get("import_show_boards", True))
        )
        self.refresh_styles()

    # ------------------------------------------------------------------
    # Data API
    # ------------------------------------------------------------------
    def set_batch(self, batch: GameBatch) -> None:
        self._batch = batch
        self._fen_token += 1
        self._fen_queued = False
        self._fen_requested.clear()
        self._fen_failed.clear()
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self.result_filter.set_current_index(0, emit=False)
        self.time_filter.set_current_index(0, emit=False)
        self.history_filter.set_value("all", emit=False)
        self.model.set_candidates(batch.candidates)
        self.lbl_subtitle.setText(batch.label)
        count = len(batch.candidates)
        saved = sum(1 for candidate in batch.candidates if candidate.in_history)
        self.badge_count.setText(f"{count} game" if count == 1 else f"{count} games")
        self.badge_saved.setText(
            f"{saved} in history" if saved != 1 else "1 in history"
        )
        self.table.setColumnHidden(
            COL_MOVES,
            not any(c.move_count is not None for c in batch.candidates),
        )
        self.table.setColumnHidden(
            COL_DETAILS,
            not any((c.opening or c.event) for c in batch.candidates),
        )
        self._apply_filters()
        if count == 1:
            if not batch.candidates[0].in_history:
                self.model.set_checked(batch.candidates[0].candidate_id, True)
            elif self.proxy.rowCount():
                self.table.setCurrentIndex(self.proxy.index(0, 0))
        self._on_selection_changed(self.model.checked_count())
        self._fen_timer.start()

    def clear(self) -> None:
        self._batch = None
        self._fen_token += 1
        self._fen_requested.clear()
        self._fen_failed.clear()
        self.model.set_candidates([])
        self.lbl_subtitle.setText("")
        self.badge_count.setText("0 games")
        self.badge_saved.setText("0 in history")
        self.lbl_selection.setText("0 of 0 row(s) selected.")
        self.lbl_filtered.setText("")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_header_toggled(self, checked: bool) -> None:
        candidate_ids = []
        for row in range(self.proxy.rowCount()):
            source_index = self.proxy.mapToSource(
                self.proxy.index(row, 0)
            )
            candidate = self.model.candidate_at(source_index.row())
            if candidate is not None:
                candidate_ids.append(candidate.candidate_id)
        self.model.set_many_checked(candidate_ids, checked)

    def _clear_selection(self) -> None:
        self.model.set_many_checked(self.model.all_candidate_ids(), False)

    def _on_boards_toggled(self) -> None:
        enabled = self.btn_boards.isChecked()
        self._config.set("import_show_boards", enabled)
        self._config.save_config()
        self._apply_board_visibility(enabled)
        if enabled:
            self._request_visible_fens()

    def _apply_board_visibility(self, enabled: bool) -> None:
        self.btn_boards.setChecked(enabled)
        self.table.setColumnHidden(COL_BOARD, not enabled)
        self.table.verticalHeader().setDefaultSectionSize(
            _ROWS_WITH_BOARDS if enabled else _ROWS_COMPACT
        )

    def _apply_filters(self) -> None:
        self.proxy.set_filters(
            search=self.search_input.text(),
            result=self.result_filter.current_value(),
            time_class=self.time_filter.current_value(),
            history=self.history_filter.value(),
        )
        shown = self.proxy.rowCount()
        total = self.model.rowCount()
        self.lbl_filtered.setText(
            f"{shown} shown" if shown != total else ""
        )
        self._on_selection_changed(self.model.checked_count())
        self._fen_timer.start()

    def _on_selection_changed(self, count: int) -> None:
        total = self.model.rowCount()
        shown = self.proxy.rowCount()
        shown_selectable = 0
        shown_checked = 0
        for row in range(shown):
            source_index = self.proxy.mapToSource(
                self.proxy.index(row, 0)
            )
            candidate = self.model.candidate_at(source_index.row())
            if candidate is None or candidate.in_history:
                continue
            shown_selectable += 1
            if self.model.is_checked(candidate.candidate_id):
                shown_checked += 1
        self.lbl_selection.setText(
            f"{count} of {total} row(s) selected."
        )
        current = self._current_candidate()
        self.btn_open.setEnabled(count == 1 or (count == 0 and current is not None))
        self.btn_add.setEnabled(count >= 1)
        self.btn_add.setText(
            f"Add {count} to history" if count > 1 else "Add to history"
        )
        if count >= 2:
            self.btn_open.set_variant(ButtonVariant.HOLLOW)
            self.btn_add.set_variant(ButtonVariant.PRIMARY)
        else:
            self.btn_open.set_variant(ButtonVariant.PRIMARY)
            self.btn_add.set_variant(ButtonVariant.HOLLOW)
        self.btn_open.refresh_styles()
        self.btn_add.refresh_styles()
        self.header.set_state(
            shown_selectable > 0 and shown_checked == shown_selectable,
            0 < shown_checked < shown_selectable,
        )

    def _current_candidate(self) -> GameCandidate | None:
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        source_index = self.proxy.mapToSource(index)
        return self.model.candidate_at(source_index.row())

    def _open_checked(self) -> None:
        checked = self.model.checked_candidates()
        if len(checked) == 1:
            self._emit_open(checked[0])
            return
        if not checked:
            current = self._current_candidate()
            if current is not None:
                self._emit_open(current)

    def _add_selected(self) -> None:
        if self._import_worker is not None:
            return
        checked = self.model.checked_candidates()
        if not checked:
            return
        self._import_label.setText(f"Adding 0 / {len(checked)}…")
        self._import_label.setVisible(True)
        self._import_progress.setRange(0, len(checked))
        self._import_progress.setValue(0)
        self._import_progress.setVisible(True)
        self.btn_add.setEnabled(False)
        self.btn_open.setEnabled(False)
        self.btn_clear_selection.setEnabled(False)
        self.table.setEnabled(False)

        worker = GameImportWorker(checked, self._history_manager)
        self._import_worker = worker
        worker.progress.connect(self._on_import_progress)
        worker.completed.connect(self._on_import_completed)
        worker.failed.connect(self._on_import_failed)
        worker.finished.connect(
            lambda w=worker: remove_import_worker(w)
        )
        register_import_worker(worker)
        worker.start()

    def _on_import_progress(self, done: int, total: int) -> None:
        self._import_label.setText(f"Adding {done} / {total}…")
        self._import_progress.setValue(done)

    def _on_import_completed(self, inserted: int, skipped: int) -> None:
        checked = {
            candidate.candidate_id
            for candidate in self.model.checked_candidates()
        }
        self.model.mark_in_history(checked)
        self._import_worker = None
        self._finish_import()
        if inserted:
            ToastManager.success(
                self,
                f"Added {inserted} game(s) to history"
                + (f" ({skipped} skipped)." if skipped else "."),
            )
        else:
            ToastManager.info(
                self, "Those games are already in history."
            )
        self.games_added.emit(inserted, skipped)

    def _on_import_failed(self, message: str) -> None:
        self._import_worker = None
        self._finish_import()
        ToastManager.error(self, f"Could not add games: {message}")

    def _finish_import(self) -> None:
        self._import_label.setVisible(False)
        self._import_progress.setVisible(False)
        self.btn_clear_selection.setEnabled(True)
        self.table.setEnabled(True)
        self._on_selection_changed(self.model.checked_count())

    def _on_double_clicked(self, proxy_index) -> None:
        source_index = self.proxy.mapToSource(proxy_index)
        candidate = self.model.candidate_at(source_index.row())
        if candidate is not None:
            self._emit_open(candidate)

    def _emit_open(self, candidate: GameCandidate) -> None:
        pgn = candidate.pgn_text()
        if pgn:
            self.open_game_requested.emit(pgn, candidate.source_data)

    # ------------------------------------------------------------------
    # Visible-row mini boards
    # ------------------------------------------------------------------
    def _request_visible_fens(self) -> None:
        if self._batch is None or self.table.isColumnHidden(COL_BOARD):
            return
        if self._fen_worker is not None:
            self._fen_queued = True
            return

        row_count = self.proxy.rowCount()
        if row_count == 0:
            return
        top = self.table.rowAt(0)
        bottom = self.table.rowAt(self.table.viewport().height() - 1)
        if top < 0:
            top = 0
        if bottom < 0:
            bottom = min(row_count - 1, top + 30)

        items: list[tuple[int, str]] = []
        for proxy_row in range(top, bottom + 1):
            source_index = self.proxy.mapToSource(
                self.proxy.index(proxy_row, 0)
            )
            candidate = self.model.candidate_at(source_index.row())
            if candidate is None or candidate.last_fen is not None:
                continue
            if candidate.candidate_id in self._fen_requested:
                continue
            if candidate.candidate_id in self._fen_failed:
                continue
            pgn = candidate.pgn_text()
            if pgn:
                items.append((candidate.candidate_id, pgn))
        if not items:
            return

        self._fen_requested.update(
            candidate_id for candidate_id, _pgn in items
        )
        token = self._fen_token
        worker = MiniBoardFenWorker(token, items)
        self._fen_worker = worker
        worker.completed.connect(
            lambda result_token, results: self._on_fens_ready(
                result_token, results
            )
        )
        worker.finished.connect(lambda w=worker: remove_worker(w))
        register_worker(worker)
        worker.start()

    def _on_fens_ready(self, token: int, results: dict[int, str | None]) -> None:
        self._fen_worker = None
        if token != self._fen_token:
            if self._fen_queued:
                self._fen_queued = False
                QTimer.singleShot(0, self._request_visible_fens)
            return
        by_id = {
            candidate.candidate_id: candidate
            for candidate in (self._batch.candidates if self._batch else [])
        }
        changed = False
        for candidate_id, fen in results.items():
            self._fen_requested.discard(candidate_id)
            candidate = by_id.get(candidate_id)
            if candidate is not None and fen:
                candidate.last_fen = fen
                changed = True
            else:
                self._fen_failed.add(candidate_id)
        if changed and self.model.rowCount():
            self.model.dataChanged.emit(
                self.model.index(0, COL_BOARD),
                self.model.index(self.model.rowCount() - 1, COL_BOARD),
                [Qt.ItemDataRole.DisplayRole],
            )
        if self._fen_queued:
            self._fen_queued = False
            QTimer.singleShot(0, self._request_visible_fens)

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------
    def _on_theme_changed(self, *_args) -> None:
        self.refresh_styles()
        self.table.viewport().update()

    def refresh_styles(self, *_args) -> None:
        Styles.apply_background(self)
        self.header_bar.setStyleSheet(
            Styles.get_header_bar_ext_style(Styles.COLOR_BACKGROUND)
        )
        self.action_bar.setStyleSheet(
            f"""
            QFrame#ImportActionBar {{
                background-color: transparent;
                border-top: 1px solid {Styles.COLOR_BORDER};
            }}
            """
        )
        self.table.setStyleSheet(Styles.get_import_table_style())
        self.btn_back.refresh_styles()
        self.btn_open.refresh_styles()
        self.btn_add.refresh_styles()
        self.btn_clear_selection.refresh_styles()
        self._import_progress.refresh_styles()
        self.btn_boards.refresh_styles()
        self.search_input.refresh_styles()
        self.result_filter.refresh_styles()
        self.time_filter.refresh_styles()
        self.history_filter.refresh_styles()

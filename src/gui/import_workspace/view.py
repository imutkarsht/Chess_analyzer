"""Dedicated game import workspace, hosted by the History page."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.backend.storage.game_history import GameHistoryManager
from src.gui.components import EmptyState
from src.gui.components.feedback.toast import ToastManager
from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.gui.utils.worker_registry import register_worker, remove_worker
from src.utils.config import ConfigManager

from .action_bar import ImportActionBar
from .batch import GameBatch, GameCandidate
from .boards import MiniBoardFenWorker, MiniBoardPosition
from .delegates import (
    BoardDelegate,
    CheckboxDelegate,
    CheckboxHeader,
    StatusPillDelegate,
)
from .header import ImportHeader
from .model import (
    COL_BOARD,
    COL_DETAILS,
    COL_MOVES,
    COL_STATUS,
    COL_TERMINATION,
    GameImportFilterProxy,
    GameImportTableModel,
)
from .toolbar import ImportToolbar
from .worker import GameImportWorker

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

        self.header = ImportHeader()
        self.header.back_requested.connect(self.back_requested.emit)
        root.addWidget(self.header)
        self._alias_header()

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.surface = QWidget()
        surface_layout = QVBoxLayout(self.surface)
        surface_layout.setContentsMargins(0, 0, 0, 0)
        surface_layout.setSpacing(0)

        self.toolbar = ImportToolbar()
        self.toolbar.filters_changed.connect(self._apply_filters)
        self.toolbar.boards_toggled.connect(self._on_boards_toggled)
        surface_layout.addWidget(self.toolbar)
        self._alias_toolbar()

        self.model = GameImportTableModel(self)
        self.proxy = GameImportFilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(Qt.ItemDataRole.UserRole + 1)
        self.proxy.setDynamicSortFilter(True)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.header_view = CheckboxHeader(
            Qt.Orientation.Horizontal, self.table
        )
        self.table.setHorizontalHeader(self.header_view)
        self.header_view.setStretchLastSection(False)
        self.header_view.setFixedHeight(40)
        self.header_view.setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.header_view.toggled.connect(self._on_header_toggled)
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
        self.table.setColumnWidth(8, 200)
        self.table.setColumnWidth(9, 280)
        self.table.setColumnWidth(10, 104)
        self.header_view.setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self.header_view.setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        self.header_view.setSectionResizeMode(
            8, QHeaderView.ResizeMode.Interactive
        )
        self.header_view.setSectionResizeMode(
            9, QHeaderView.ResizeMode.Interactive
        )
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(2, Qt.SortOrder.DescendingOrder)
        self.table.doubleClicked.connect(self._on_double_clicked)
        self.table.setItemDelegateForColumn(0, CheckboxDelegate(self.table))
        self.table.setItemDelegateForColumn(1, BoardDelegate(self.table))
        self.table.setItemDelegateForColumn(
            COL_STATUS, StatusPillDelegate(self.table)
        )

        self.table_stack = QStackedWidget()
        self.table_stack.addWidget(self.table)
        self.empty_state = EmptyState("No games match these filters.")
        self.table_stack.addWidget(self.empty_state)
        self.table_stack.setCurrentWidget(self.table)
        surface_layout.addWidget(self.table_stack, 1)

        self.action_bar = ImportActionBar()
        self.action_bar.open_clicked.connect(self._open_checked)
        self.action_bar.add_clicked.connect(self._add_selected)
        surface_layout.addWidget(self.action_bar)
        self._alias_action_bar()

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
        self.header_view.sortIndicatorChanged.connect(
            lambda *_args: self._fen_timer.start()
        )
        self._apply_board_visibility(
            bool(self._config.get("import_show_boards", True))
        )
        self.refresh_styles()

    # ------------------------------------------------------------------
    # Compatibility aliases used by tests and integration call sites
    # ------------------------------------------------------------------
    def _alias_header(self) -> None:
        self.header_bar = self.header
        self.btn_back = self.header.btn_back
        self.lbl_subtitle = self.header.lbl_subtitle
        self.badge_count = self.header.badge_count
        self.badge_saved = self.header.badge_saved

    def _alias_toolbar(self) -> None:
        self.search_input = self.toolbar.search_input
        self.result_filter = self.toolbar.result_filter
        self.color_filter = self.toolbar.color_filter
        self.time_filter = self.toolbar.time_filter
        self.history_filter = self.toolbar.history_filter
        self.lbl_filtered = self.toolbar.lbl_filtered
        self.btn_clear_filters = self.toolbar.btn_clear_filters
        self.btn_boards = self.toolbar.btn_boards

    def _alias_action_bar(self) -> None:
        self.lbl_selection = self.action_bar.lbl_selection
        self.btn_add = self.action_bar.btn_add
        self.btn_open = self.action_bar.btn_open

    # ------------------------------------------------------------------
    # Data API
    # ------------------------------------------------------------------
    def set_batch(self, batch: GameBatch) -> None:
        self._batch = batch
        self._fen_token += 1
        self._fen_queued = False
        self._fen_requested.clear()
        self._fen_failed.clear()
        self.toolbar.reset_filters(emit=False)
        self.model.set_candidates(batch.candidates)
        self._configure_result_filter(batch.candidates)
        saved = sum(1 for candidate in batch.candidates if candidate.in_history)
        self.header.set_batch_info(batch.label, len(batch.candidates), saved)
        self.table.setColumnHidden(
            COL_MOVES,
            not any(
                c.move_count is not None or c.index is not None
                for c in batch.candidates
            ),
        )
        self.table.setColumnHidden(
            COL_DETAILS,
            not any(
                (c.opening or c.eco or c.event)
                for c in batch.candidates
            ),
        )
        self.table.setColumnHidden(
            COL_TERMINATION,
            not any(c.termination for c in batch.candidates),
        )
        self._fit_dynamic_columns(batch.candidates)
        self._apply_filters()
        if len(batch.candidates) == 1:
            if not batch.candidates[0].in_history:
                self.model.set_checked(batch.candidates[0].candidate_id, True)
            elif self.proxy.rowCount():
                self.table.setCurrentIndex(self.proxy.index(0, 0))
        self._on_selection_changed(self.model.checked_count())
        self._fen_timer.start()

    def _fit_dynamic_columns(self, candidates: list[GameCandidate]) -> None:
        metrics = self.table.fontMetrics()

        def fitted(texts: list[str], minimum: int, maximum: int) -> int:
            longest = max(
                (metrics.horizontalAdvance(text) for text in texts if text),
                default=0,
            )
            return max(minimum, min(maximum, longest + 28))

        if not self.table.isColumnHidden(COL_DETAILS):
            self.table.setColumnWidth(
                COL_DETAILS,
                fitted(
                    [
                        (
                            f"{c.eco} · {c.opening}"
                            if c.eco and c.opening
                            else (c.opening or c.eco or c.event or "")
                        )
                        for c in candidates
                    ],
                    160,
                    320,
                ),
            )
        if not self.table.isColumnHidden(COL_TERMINATION):
            self.table.setColumnWidth(
                COL_TERMINATION,
                fitted(
                    [c.termination or "" for c in candidates],
                    140,
                    360,
                ),
            )

    def _configure_result_filter(self, candidates: list[GameCandidate]) -> None:
        usernames = {
            str(self._config.get(key, "")).strip().casefold()
            for key in ("chesscom_username", "lichess_username")
        }
        usernames.discard("")
        perspective = bool(usernames) and any(
            self._involves_username(candidate, usernames)
            for candidate in candidates
        )
        self.proxy.set_player_context(usernames, perspective)
        self.toolbar.set_perspective(perspective)

    @staticmethod
    def _involves_username(
        candidate: GameCandidate, usernames: set[str]
    ) -> bool:
        white = (candidate.white or "").strip().casefold()
        black = (candidate.black or "").strip().casefold()
        return (white in usernames) ^ (black in usernames)

    def clear(self) -> None:
        self._batch = None
        self._fen_token += 1
        self._fen_requested.clear()
        self._fen_failed.clear()
        self.model.set_candidates([])
        self.header.reset()
        self.lbl_selection.setText("0 of 0 row(s) selected.")
        self.lbl_filtered.setText("")
        self.toolbar.btn_clear_filters.setVisible(False)
        self.table_stack.setCurrentWidget(self.table)

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

    def _clear_filters(self) -> None:
        self.toolbar.reset_filters()

    def _on_boards_toggled(self, enabled: bool | None = None) -> None:
        if enabled is None:
            enabled = self.btn_boards.isChecked()
        self._config.set("import_show_boards", enabled)
        self._config.save_config()
        self._apply_board_visibility(enabled)
        if enabled:
            self._request_visible_fens()

    def _apply_board_visibility(self, enabled: bool) -> None:
        self.toolbar.set_boards_checked(enabled)
        self.table.setColumnHidden(COL_BOARD, not enabled)
        self.table.verticalHeader().setDefaultSectionSize(
            _ROWS_WITH_BOARDS if enabled else _ROWS_COMPACT
        )

    def _apply_filters(self) -> None:
        if not self.color_filter.isHidden():
            self.proxy.set_player_color(self.color_filter.current_value())
        self.proxy.set_filters(
            search=self.search_input.text(),
            result=self.result_filter.current_value(),
            time_class=self.time_filter.current_value(),
            history=self.history_filter.value(),
        )
        shown = self.proxy.rowCount()
        total = self.model.rowCount()
        self.toolbar.update_counts(shown, total)
        self._update_empty_state(shown, total)
        self._on_selection_changed(self.model.checked_count())
        self._fen_timer.start()

    def _update_empty_state(self, shown: int, total: int) -> None:
        if shown or not total:
            self.table_stack.setCurrentWidget(self.table)
        else:
            self.table_stack.setCurrentWidget(self.empty_state)

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
        current = self._current_candidate()
        self.action_bar.set_selection(
            count, total, current is not None
        )
        self.header_view.set_state(
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
        self.action_bar.begin_import(len(checked))
        self.btn_clear_filters.setEnabled(False)
        self.table.setEnabled(False)

        worker = GameImportWorker(checked, self._history_manager)
        self._import_worker = worker
        worker.progress.connect(self.action_bar.update_progress)
        worker.completed.connect(self._on_import_completed)
        worker.failed.connect(self._on_import_failed)
        worker.finished.connect(lambda w=worker: remove_worker(w))
        register_worker(worker)
        worker.start()

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
        self.action_bar.finish_import()
        self.btn_clear_filters.setEnabled(True)
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

    def _on_fens_ready(
        self, token: int, results: dict[int, MiniBoardPosition]
    ) -> None:
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
        for candidate_id, position in results.items():
            self._fen_requested.discard(candidate_id)
            candidate = by_id.get(candidate_id)
            if candidate is not None and position.fen:
                candidate.last_fen = position.fen
                candidate.last_move_uci = position.last_move_uci
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
        self.header.refresh_styles()
        self.toolbar.refresh_styles()
        self.action_bar.refresh_styles()
        self.table.setStyleSheet(Styles.get_import_table_style())

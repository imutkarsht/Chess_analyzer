import json
import os
import tempfile
import time
from pathlib import Path
from threading import Event

import qtawesome as qta
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMenu,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.backend.storage.annotated_pgn import AnnotatedPGNExporter
from src.backend.storage.game_history import GAME_CSV_COLUMNS, GameHistoryManager
from src.backend.storage.game_query import GameQuery
from src.gui.components import (
    Button,
    ButtonVariant,
    Label,
    TextRole,
)
from src.gui.components.feedback.toast import ToastHandle, ToastManager
from src.gui.components.lists.game_list_widget import GameListWidget
from src.gui.import_workspace import GameBatch, GameImportView
from src.gui.styles import Styles
from src.gui.utils.debounce import Debouncer
from src.gui.utils.gui_utils import create_button
from src.gui.utils.worker_registry import register_worker, remove_worker
from src.utils.logger import logger

from .history_batch import BatchQueueCard, BatchSelectionBar
from .history_filter_bar import HistoryFilterBar


class GameImportWorker(QThread):
    """Background worker for parsing CSV files and bulk-inserting games off the UI thread."""

    finished = pyqtSignal(int, int)  # imported_count, skipped_count
    error = pyqtSignal(str)

    def __init__(self, history_manager: GameHistoryManager, file_path: str, parent=None):
        super().__init__(parent)
        self.history_manager = history_manager
        self.file_path = file_path

    def run(self):
        try:
            import csv

            max_limit = 2147483647
            try:
                csv.field_size_limit(max_limit)
            except OverflowError:
                csv.field_size_limit(50 * 1024 * 1024)

            existing_ids = self.history_manager.get_all_game_ids()
            rows_to_save = []
            skipped_count = 0

            with open(self.file_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    game_id = row.get("id")
                    if game_id and game_id in existing_ids:
                        skipped_count += 1
                        continue
                    rows_to_save.append(row)

            imported_count = self.history_manager.save_games_bulk(rows_to_save)
            self.finished.emit(imported_count, skipped_count)
        except Exception as e:
            logger.error(f"Background game import failed: {e}")
            self.error.emit(str(e))


class AnnotatedPGNExportWorker(QThread):
    """Stream filtered game history to PGN without blocking the History view."""

    exported = pyqtSignal(int, int)  # exported_count, skipped_count
    progress = pyqtSignal(int, int)  # processed_count, total_count
    cancelled = pyqtSignal(int, int)  # exported_count, skipped_count
    error = pyqtSignal(str)
    _BATCH_SIZE = 25
    _YIELD_EVERY = 25

    def __init__(
        self,
        history_manager: GameHistoryManager,
        file_path: str,
        query: GameQuery | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.history_manager = history_manager
        self.file_path = file_path
        self.query = query or GameQuery()
        self._cancel_requested = Event()

    def request_cancel(self) -> None:
        self._cancel_requested.set()

    def run(self) -> None:
        temporary_path: Path | None = None
        try:
            total = self.history_manager.count_games(self.query)
            if not total:
                self.exported.emit(0, 0)
                return

            output_path = Path(self.file_path)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=output_path.parent,
                prefix=f".{output_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as output:
                temporary_path = Path(output.name)
                exported_count = 0
                skipped_count = 0
                processed_count = 0
                has_output = False

                rows = self.history_manager.iter_games_for_export(
                    self.query, self._BATCH_SIZE
                )
                try:
                    for row in rows:
                        if self._cancel_requested.is_set():
                            break
                        try:
                            pgn = row.get("pgn") or ""
                            if self._is_unanalyzed(row):
                                pgn = AnnotatedPGNExporter.validate_unanalyzed_pgn(
                                    str(row.get("id") or ""),
                                    pgn,
                                    row.get("move_count"),
                                )
                            else:
                                game = self.history_manager.row_to_game_analysis(row)
                                pgn = AnnotatedPGNExporter.export_game(game)
                            self._write_game(output, pgn, has_output)
                            has_output = True
                            exported_count += 1
                        except Exception as error:
                            skipped_count += 1
                            logger.warning(
                                "Skipping game %s during annotated PGN export: %s",
                                row.get("id", "<unknown>"),
                                error,
                            )

                        processed_count += 1
                        if processed_count % self._YIELD_EVERY == 0:
                            self.progress.emit(processed_count, total)
                            time.sleep(0)
                finally:
                    close_iterator = getattr(rows, "close", None)
                    if close_iterator is not None:
                        close_iterator()

                self.progress.emit(processed_count, total)
                cancelled = self._cancel_requested.is_set()

            if cancelled:
                self.cancelled.emit(exported_count, skipped_count)
                return

            os.replace(temporary_path, output_path)
            temporary_path = None
            self.exported.emit(exported_count, skipped_count)
        except Exception as e:
            logger.error("Annotated PGN export failed: %s", e, exc_info=True)
            self.error.emit(str(e))
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _is_unanalyzed(row: dict) -> bool:
        moves_json = row.get("moves_json")
        if not moves_json:
            return True
        try:
            return not json.loads(moves_json)
        except (json.JSONDecodeError, TypeError, ValueError):
            return False

    @staticmethod
    def _write_game(output, pgn: str, has_output: bool) -> None:
        if has_output:
            output.write("\n")
        output.write(pgn)
        if not pgn.endswith("\n"):
            output.write("\n")


class HistoryView(QWidget):
    game_selected = pyqtSignal(object)  # Emits GameAnalysis object
    game_action_requested = pyqtSignal(object, str)  # Emits (GameAnalysis, action)
    game_deleted = pyqtSignal(str)
    batch_analysis_requested = pyqtSignal(object)  # list[str] in selection order
    batch_control_requested = pyqtSignal(str)  # pause | resume | cancel | dismiss
    games_imported = pyqtSignal(int)
    history_cleared = pyqtSignal()
    open_imported_game = pyqtSignal(str, object)

    def __init__(self, config_manager=None):
        super().__init__()
        self.config_manager = config_manager
        self.history_manager = GameHistoryManager()
        self.games = []
        self._import_worker: GameImportWorker | None = None
        self._export_worker: AnnotatedPGNExportWorker | None = None
        self._export_toast: ToastHandle | None = None
        self.analyzing_game_id: str | None = None
        self._bulk_mode = False
        self._selected_games: dict[str, object] = {}
        self._batchable_count = 0
        self._batch_running = False
        self._batch_active_game_id: str | None = None
        self._batch_queued_ids: set[str] = set()
        self._batch_active_label = ""
        self._batch_position = 0
        self._batch_total = 0
        self._batch_move_current = 0
        self._batch_move_total = 0
        self._pre_bulk_analysis_filter = ""
        self.usernames: list[str] = []
        self._total = 0
        self._offset = 0
        self._loading_more = False
        # Load the second page while the reader is still looking at the first,
        # so scrolling rarely waits on the database or on row construction.
        self._prefetch_timer = QTimer(self)
        self._prefetch_timer.setSingleShot(True)
        self._prefetch_timer.setInterval(250)
        self._prefetch_timer.timeout.connect(self._prefetch_next_page)
        # Every keystroke used to rebuild all 10 row widgets; coalesce instead.
        self._filter_debounce = Debouncer(self, interval=150)

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.page_stack = QStackedWidget()
        self.page_stack.setStyleSheet("background: transparent;")
        self.layout.addWidget(self.page_stack)

        self.history_page = QWidget()
        Styles.apply_background(self.history_page)
        history_page_layout = QVBoxLayout(self.history_page)
        history_page_layout.setContentsMargins(0, 0, 0, 0)
        history_page_layout.setSpacing(0)

        # Header Bar Container
        self.header_bar = QFrame()
        self.header_bar.setStyleSheet(Styles.get_header_bar_ext_style(Styles.COLOR_BACKGROUND))
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(24, 12, 24, 12)
        header_layout.setSpacing(8)

        # Title
        self.header_lbl = Label("Game History", role=TextRole.PAGE_TITLE)
        header_layout.addWidget(self.header_lbl)

        header_layout.addStretch()

        # Batch analysis is explicit: it only appears when at least two games
        # actually need engine time, and bulk mode selects the subset.
        self.btn_batch = Button(
            "Batch analyze",
            ButtonVariant.PRIMARY,
            icon="fa5s.play-circle",
            on_click=self._on_batch_button_clicked,
            tooltip="Analyze selected History games one by one",
        )
        self.btn_batch.setAccessibleName("Batch analyze History games")
        self.btn_batch.setVisible(False)
        header_layout.addWidget(self.btn_batch)

        # Action Buttons in Top Header (Import, Export, Clear, Refresh)
        self.btn_import = self._create_icon_button("Import", "fa5s.file-import", self.import_games)
        header_layout.addWidget(self.btn_import)

        self.btn_export = self._create_icon_button("Export", "fa5s.file-export", None)
        self.export_menu = QMenu(self)
        self.export_menu.setStyleSheet(Styles.get_menu_style())
        self.export_csv_action = self.export_menu.addAction("Export CSV")
        self.export_csv_action.triggered.connect(self.export_games)
        self.export_pgn_action = self.export_menu.addAction("Export Annotated PGN")
        self.export_pgn_action.triggered.connect(self.export_annotated_pgn)
        self._refresh_export_menu_icons()
        self.btn_export.setMenu(self.export_menu)
        header_layout.addWidget(self.btn_export)

        self.btn_cancel_export = Button(
            "Cancel export",
            ButtonVariant.OUTLINED,
            on_click=self._cancel_annotated_pgn_export,
        )
        self.btn_cancel_export.setVisible(False)
        header_layout.addWidget(self.btn_cancel_export)

        self.btn_clear = self._create_icon_button(
            "Delete all games",
            "fa5s.trash-alt",
            self.clear_history,
            danger=True,
        )
        header_layout.addWidget(self.btn_clear)

        self.btn_refresh = create_button(
            "Refresh", style="secondary", on_click=self.load_history, icon_name="fa5s.sync-alt"
        )
        header_layout.addWidget(self.btn_refresh)

        history_page_layout.addWidget(self.header_bar)

        # Content Container Widget
        self.content_widget = QWidget()
        Styles.apply_background(self.content_widget)
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(24, 16, 24, 16)
        content_layout.setSpacing(16)

        self.filter_bar = HistoryFilterBar()
        self.filter_bar.search_changed.connect(self._on_search_changed)
        self.filter_bar.filters_changed.connect(self.apply_filters)
        self.filter_bar.sort_changed.connect(self._on_sort_changed)
        content_layout.addWidget(self.filter_bar)
        self._alias_filter_controls()

        self.batch_selection_bar = BatchSelectionBar()
        self.batch_selection_bar.setVisible(False)
        self.batch_selection_bar.select_page_requested.connect(self._select_current_page)
        self.batch_selection_bar.clear_requested.connect(self._clear_batch_selection)
        self.batch_selection_bar.exit_requested.connect(self._exit_batch_mode)
        content_layout.addWidget(self.batch_selection_bar)

        self.batch_queue_card = BatchQueueCard()
        self.batch_queue_card.pause_requested.connect(
            lambda: self.batch_control_requested.emit("pause")
        )
        self.batch_queue_card.resume_requested.connect(
            lambda: self.batch_control_requested.emit("resume")
        )
        self.batch_queue_card.cancel_requested.connect(
            lambda: self.batch_control_requested.emit("cancel")
        )
        self.batch_queue_card.dismiss_requested.connect(
            lambda: self.batch_control_requested.emit("dismiss")
        )
        content_layout.addWidget(self.batch_queue_card)

        # Game List
        self.game_list = GameListWidget()
        self.game_list.game_selected.connect(self.on_game_selected)
        self.game_list.game_action_requested.connect(self._on_game_action_requested)
        self.game_list.game_delete_requested.connect(self._on_game_delete_requested)
        self.game_list.batch_selection_toggled.connect(self._on_batch_selection_toggled)
        self.game_list.load_more_requested.connect(self._load_more)
        content_layout.addWidget(self.game_list)
        self.apply_default_view_mode()

        history_page_layout.addWidget(self.content_widget)

        self.import_view = GameImportView()
        self.import_view.back_requested.connect(self.close_import_workspace)
        self.import_view.open_game_requested.connect(self.open_imported_game.emit)
        self.import_view.games_added.connect(self._on_import_games_added)
        self.page_stack.addWidget(self.history_page)
        self.page_stack.addWidget(self.import_view)
        self.page_stack.setCurrentWidget(self.history_page)

        # Load initial data
        self.load_history()

    def _alias_filter_controls(self) -> None:
        """Keep the established HistoryView control names for callers/tests."""
        self.search_input = self.filter_bar.search_input
        self.result_filter = self.filter_bar.result_filter
        self.type_filter = self.filter_bar.type_filter
        self.source_filter = self.filter_bar.source_filter
        self.analysis_filter = self.filter_bar.analysis_filter
        self.ownership_filter = self.filter_bar.ownership_filter
        self.sort_dropdown = self.filter_bar.sort_dropdown
        self.btn_filters = self.filter_bar.btn_filters
        self.filter_panel = self.filter_bar.panel

    def show_import_workspace(self, batch: GameBatch) -> None:
        """Show a fetched/indexed batch in the import workspace."""
        if self._bulk_mode:
            self._exit_batch_mode()
        self.import_view.set_batch(batch)
        self.page_stack.setCurrentWidget(self.import_view)

    def close_import_workspace(self) -> None:
        """Return to the normal history list and release the batch."""
        self.import_view.clear()
        self.page_stack.setCurrentWidget(self.history_page)
        self.load_history()

    def _on_import_games_added(self, inserted: int, _skipped: int) -> None:
        if inserted:
            self.games_imported.emit(inserted)

    def _create_icon_button(self, text, icon_name, callback=None, danger=False):
        """Create a Button with a themed icon."""
        return Button(
            text,
            ButtonVariant.FILLED,
            icon=icon_name,
            danger=danger,
            on_click=callback,
        )

    def _refresh_export_menu_icons(self):
        """Retint the export menu icons from the live palette."""
        color = Styles.COLOR_TEXT_SECONDARY
        self.export_csv_action.setIcon(qta.icon("fa5s.file-csv", color=color))
        self.export_pgn_action.setIcon(qta.icon("fa5s.file-code", color=color))

    def apply_default_view_mode(self):
        """Apply the Appearance default layout without overriding a manual toggle."""
        mode = "compact"
        if self.config_manager:
            mode = self.config_manager.get("history_view_mode", "compact")
        if mode not in ("compact", "detailed"):
            mode = "compact"
        self.game_list.set_view_mode(mode)

    def set_analyzing_game_id(self, game_id: str | None):
        """Inform HistoryView of the game currently being analyzed."""
        self.analyzing_game_id = game_id
        if hasattr(self, "game_list"):
            self.game_list.set_analyzing_game_id(game_id)

    # ── Batch selection ───────────────────────────────────────────────────────

    def _on_batch_button_clicked(self) -> None:
        if self._bulk_mode:
            self._request_batch_start()
            return
        self._enter_batch_mode()

    def _enter_batch_mode(self) -> None:
        if self._bulk_mode or self._batch_running or self._batchable_count <= 1:
            return
        self._bulk_mode = True
        self._pre_bulk_analysis_filter = self.analysis_filter.value() or ""
        self.analysis_filter.set_value("", emit=False)
        self.analysis_filter.setEnabled(False)
        self.analysis_filter.setToolTip(
            "Batch mode shows only unanalyzed and paused games"
        )
        self.batch_selection_bar.setVisible(True)
        self.batch_selection_bar.set_count(0)
        self.game_list.set_selection_mode(True, set())
        self._update_batch_button()
        self.apply_filters(clear_selection=False)

    def _exit_batch_mode(self) -> None:
        if not self._bulk_mode:
            return
        self._bulk_mode = False
        self._selected_games.clear()
        self.game_list.set_selection_mode(False, set())
        self.batch_selection_bar.setVisible(False)
        self.analysis_filter.setEnabled(True)
        self.analysis_filter.setToolTip("")
        self.analysis_filter.set_value(self._pre_bulk_analysis_filter, emit=False)
        self._pre_bulk_analysis_filter = ""
        self._update_batch_button()
        self.apply_filters(clear_selection=False)

    def _on_batch_selection_toggled(self, game, selected: bool) -> None:
        game_id = getattr(game, "game_id", None)
        if not game_id:
            return
        if selected:
            self._selected_games[game_id] = game
        else:
            self._selected_games.pop(game_id, None)
        self.batch_selection_bar.set_count(len(self._selected_games))
        self._update_batch_button()

    def _select_current_page(self) -> None:
        for game in self.game_list.page_games(self._page_size()):
            game_id = getattr(game, "game_id", None)
            if game_id:
                self._selected_games[game_id] = game
        self.game_list.set_selected_ids(set(self._selected_games))
        self.batch_selection_bar.set_count(len(self._selected_games))
        self._update_batch_button()

    def _clear_batch_selection(self) -> None:
        self._selected_games.clear()
        self.game_list.set_selected_ids(set())
        self.batch_selection_bar.set_count(0)
        self._update_batch_button()

    def _update_selection_bar_page(self) -> None:
        if not self._bulk_mode:
            return
        self.batch_selection_bar.set_page_available(
            bool(self.game_list.page_games(self._page_size()))
        )

    def _refresh_batch_availability(self) -> None:
        try:
            self._batchable_count = int(
                self.history_manager.count_games(GameQuery(batchable_only=True))
            )
        except Exception as e:
            logger.debug(f"Failed to count batchable games: {e}")
            self._batchable_count = 0
        self._update_batch_button()

    def _update_batch_button(self) -> None:
        if self._batch_running:
            self.btn_batch.setVisible(True)
            self.btn_batch.setText("Batch running")
            self.btn_batch.setEnabled(False)
            return
        if self._bulk_mode:
            count = len(self._selected_games)
            self.btn_batch.setVisible(True)
            if count == 1:
                self.btn_batch.setText("Analyze 1 game")
            elif count > 1:
                self.btn_batch.setText(f"Analyze {count} games")
            else:
                self.btn_batch.setText("Analyze games")
            self.btn_batch.setEnabled(count > 0)
            return
        visible = self._batchable_count > 1
        self.btn_batch.setVisible(visible)
        self.btn_batch.setText("Batch analyze")
        self.btn_batch.setEnabled(visible)

    def _request_batch_start(self) -> None:
        selected_ids = list(self._selected_games)
        if not selected_ids:
            return
        try:
            rows = self.history_manager.fetch_game_rows_by_ids(selected_ids)
        except Exception as e:
            logger.error(f"Failed to prepare batch selection: {e}")
            ToastManager.error(self, f"Could not prepare batch: {e}")
            return

        by_id = {row.get("id"): row for row in rows}
        for game_id in [gid for gid in selected_ids if gid not in by_id]:
            self._selected_games.pop(game_id, None)
        self.game_list.set_selected_ids(set(self._selected_games))
        self.batch_selection_bar.set_count(len(self._selected_games))
        self._update_batch_button()

        valid_ids = [game_id for game_id in selected_ids if game_id in by_id]
        if not valid_ids:
            ToastManager.warning(self, "Those games are no longer in History.")
            return

        analyze = resume = skip = 0
        for game_id in valid_ids:
            status = str(by_id[game_id].get("analysis_status") or "").strip().lower()
            if status == "completed":
                skip += 1
            elif status == "paused":
                resume += 1
            else:
                analyze += 1

        from src.gui.utils.gui_utils import confirm_dialog

        noun = "game" if len(valid_ids) == 1 else "games"
        message = (
            f"Analyze {len(valid_ids)} selected {noun}?\n\n"
            f"• {analyze} will be analyzed\n"
            f"• {resume} will resume from partial results\n"
            f"• {skip} already complete will be skipped"
        )
        if not confirm_dialog(
            self,
            "Start Batch Analysis",
            message,
            confirm_label="Start batch",
            danger=False,
        ):
            return
        self.batch_analysis_requested.emit(valid_ids)

    def on_batch_started(self, batch) -> None:
        """Close bulk selection and reflect the new running queue."""
        self._bulk_mode = False
        self._selected_games.clear()
        self.game_list.set_selection_mode(False, set())
        self.batch_selection_bar.setVisible(False)
        self.analysis_filter.setEnabled(True)
        self.analysis_filter.setToolTip("")
        if self._pre_bulk_analysis_filter:
            self.analysis_filter.set_value(self._pre_bulk_analysis_filter, emit=False)
        self._pre_bulk_analysis_filter = ""
        self._batch_total = batch.total
        self._batch_active_label = ""
        self.set_batch_running(
            True,
            active_game_id=None,
            queued_ids={item.game_id for item in batch.pending_items()},
        )
        self.batch_queue_card.show_batch(batch, active_label="", position=1)
        self.apply_filters(clear_selection=False)

    def set_batch_running(
        self,
        running: bool,
        active_game_id: str | None = None,
        queued_ids: set[str] | None = None,
    ) -> None:
        """Lock/restore History actions for a running batch."""
        self._batch_running = bool(running)
        self._batch_active_game_id = active_game_id if running else None
        self._batch_queued_ids = set(queued_ids or ()) if running else set()
        if running:
            self.game_list.set_batch_runtime(
                active_game_id,
                self._batch_position,
                self._batch_total,
                self._batch_queued_ids,
                locked=True,
            )
        else:
            self.game_list.clear_batch_runtime()
        self.btn_clear.setEnabled(not running)
        self._update_batch_button()

    def set_batch_active(
        self,
        game_id: str,
        label: str,
        position: int,
        total: int,
        queued_ids: set[str],
        batch=None,
    ) -> None:
        self._batch_active_game_id = game_id
        self._batch_active_label = label
        self._batch_position = int(position)
        self._batch_total = int(total)
        self._batch_queued_ids = set(queued_ids)
        self._batch_move_current = 0
        self._batch_move_total = 0
        self.game_list.set_batch_runtime(
            game_id,
            self._batch_position,
            self._batch_total,
            self._batch_queued_ids,
            locked=True,
        )
        if batch is not None:
            self.batch_queue_card.show_batch(
                batch,
                active_label=label,
                position=self._batch_position,
            )

    def update_batch_move_progress(self, current: int, total: int) -> None:
        self._batch_move_current = max(0, int(current))
        self._batch_move_total = max(0, int(total))
        self.batch_queue_card.set_move_progress(
            self._batch_move_current, self._batch_move_total
        )

    def set_batch_queue(
        self,
        batch,
        *,
        active_label: str = "",
        position: int | None = None,
        move_current: int | None = None,
        move_total: int | None = None,
    ) -> None:
        self._batch_total = batch.total
        self._batch_active_label = active_label or self._batch_active_label
        if position is not None:
            self._batch_position = int(position)
        if move_current is not None:
            self._batch_move_current = max(0, int(move_current))
        if move_total is not None:
            self._batch_move_total = max(0, int(move_total))
        if batch.state == "running":
            self._batch_running = True
            self._batch_queued_ids = {
                item.game_id for item in batch.pending_items()
            }
            self.set_batch_running(
                True,
                self._batch_active_game_id,
                self._batch_queued_ids,
            )
        else:
            self.set_batch_running(False)
            self._batch_queued_ids = set()
        self.batch_queue_card.show_batch(
            batch,
            active_label=self._batch_active_label,
            position=self._batch_position,
            move_current=self._batch_move_current,
            move_total=self._batch_move_total,
        )

    def refresh_batch_queue(self) -> None:
        """Reload the persisted card without starting any work."""
        try:
            batch = self.history_manager.get_analysis_batch()
        except Exception as e:
            logger.debug(f"Failed to load batch queue: {e}")
            return
        if batch is None:
            self.hide_batch_queue()
            return
        self.set_batch_queue(batch, active_label=self._batch_active_label)

    def hide_batch_queue(self) -> None:
        self.batch_queue_card.hide_card()
        self.set_batch_running(False)
        self._batch_active_label = ""
        self._batch_position = 0
        self._batch_total = 0
        self._batch_move_current = 0
        self._batch_move_total = 0

    def load_history(self):
        """Reload the current query from the first page, keeping the reader's place."""
        self._reload(preserve_position=True)

    def apply_filters(self, clear_selection: bool = True):
        """Re-run the query from the first page after a filter or sort change."""
        if clear_selection and self._bulk_mode:
            self._clear_batch_selection()
        self._reload(preserve_position=False)

    def _on_search_changed(self):
        # Clear before the debounce so a hidden selection can never be run.
        if self._bulk_mode:
            self._clear_batch_selection()
        self._filter_debounce.call(self.apply_filters)

    def _on_sort_changed(self):
        self.apply_filters(clear_selection=False)

    # ── Query + paging ────────────────────────────────────────────────────────

    _DETAILED_PAGE_SIZE = 10
    _COMPACT_PAGE_SIZE = 15
    _MAX_RESTORE_PAGES = 4
    _MAX_RETAINED_GAMES = 300

    def _page_size(self) -> int:
        """Cards are taller than rows, so the page size follows the view mode."""
        if self.game_list.view_mode == "detailed":
            return self._DETAILED_PAGE_SIZE
        return self._COMPACT_PAGE_SIZE

    def _current_query(self) -> GameQuery:
        """Translate the filter controls into a single database query."""
        return GameQuery(
            search=self.filter_bar.search_text(),
            result=self.result_filter.current_value() or "",
            analysis_status=(
                "" if self._bulk_mode else (self.analysis_filter.value() or "")
            ),
            ownership=self.ownership_filter.value() or "",
            speed=self.type_filter.current_value() or "",
            source=self.source_filter.current_value() or "",
            batchable_only=self._bulk_mode,
            sort=self.sort_dropdown.current_value() or "newest",
            usernames=tuple(self.usernames),
            limit=self._page_size(),
            offset=0,
        )

    def _refresh_usernames(self):
        if not self.config_manager:
            self.usernames = []
            return
        chesscom = self.config_manager.get("chesscom_username", "")
        lichess = self.config_manager.get("lichess_username", "")
        self.usernames = [u for u in [chesscom, lichess] if u]

    def _fetch_page(self, query: GameQuery) -> list:
        """Fetch one page of hydrated rows for the list."""
        rows = self.history_manager.fetch_games_page(query)
        return [self.history_manager.row_to_game_analysis(row) for row in rows]

    def _reload(self, preserve_position: bool):
        self._prefetch_timer.stop()
        try:
            self._refresh_usernames()
            query = self._current_query()
            top_id = self.game_list.top_game_id() if preserve_position else None

            total = self.history_manager.count_games(query)
            self._total = total
            self.filter_bar.set_result_count(total)
            self._offset = 0
            self.game_list.reset(total, self.usernames)

            games = self._fetch_page(query)
            self._offset = len(games)
            self.games = games[-self._MAX_RETAINED_GAMES :]
            self.game_list.append_rows(games)

            if top_id:
                # Re-create enough pages to find the row the reader was on, so
                # returning from a game does not throw them back to the top.
                pages = 1
                while (
                    not self.game_list.scroll_to_game(top_id)
                    and self._offset < total
                    and pages < self._MAX_RESTORE_PAGES
                ):
                    extra = self._fetch_page(query.with_offset(self._offset))
                    if not extra:
                        break
                    self._offset += len(extra)
                    self.games.extend(extra)
                    self.games = self.games[-self._MAX_RETAINED_GAMES :]
                    self.game_list.append_rows(extra)
                    pages += 1
            self._update_empty_state()
            self._refresh_batch_availability()
            self._update_selection_bar_page()
            self._schedule_prefetch()
        except Exception as e:
            logger.error(f"Failed to load history: {e}")

    def _update_empty_state(self) -> None:
        if self._total > 0:
            self.game_list.show_list()
            return
        if self._bulk_mode:
            if self.filter_bar.filters_active():
                self.game_list.show_empty(
                    "No unanalyzed or paused games match these filters.",
                    "Clear filters",
                    self.filter_bar.reset_filters,
                )
            else:
                self.game_list.show_empty(
                    "No games need analysis.",
                    "Exit selection",
                    lambda: self._exit_batch_mode(),
                )
            return
        if self.filter_bar.filters_active():
            self.game_list.show_empty(
                "No games match your search and filters.",
                "Clear filters",
                self.filter_bar.reset_filters,
            )
        else:
            self.game_list.show_empty(
                "No games yet. Games you analyze or import will appear here."
            )

    def _schedule_prefetch(self):
        """Warm the next page while the first one is still being read."""
        if self.isVisible() and self._offset < self._total and self._offset <= self._page_size():
            self._prefetch_timer.start()

    def _prefetch_next_page(self):
        if self._offset >= self._total or self._loading_more:
            return
        self._load_more()

    def _load_more(self):
        """Append the next page when the list nears its end."""
        if self._loading_more or self._offset >= self._total:
            return
        self._loading_more = True
        try:
            query = self._current_query().with_offset(self._offset)
            games = self._fetch_page(query)
            if not games:
                self._total = self._offset
                self.game_list.set_total(self._total)
                self.filter_bar.set_result_count(self._total)
                self._update_empty_state()
                return
            self._offset += len(games)
            self.games.extend(games)
            self.games = self.games[-self._MAX_RETAINED_GAMES :]
            self.game_list.append_rows(games)
            self._update_selection_bar_page()
        except Exception as e:
            logger.error(f"Failed to load more history: {e}")
        finally:
            self._loading_more = False

    def _on_game_delete_requested(self, game_id: str) -> None:
        if self._batch_active_game_id == game_id:
            ToastManager.warning(
                self, "This game is being analyzed in the batch. Pause or cancel first."
            )
            return

        from src.gui.utils.gui_utils import confirm_dialog

        if not confirm_dialog(
            self,
            "Delete Game",
            "Remove this game from history? This cannot be undone.",
            confirm_label="Delete",
        ):
            return
        try:
            self.history_manager.delete_game(game_id)
        except Exception as e:
            logger.error(f"Failed to delete game {game_id}: {e}")
            ToastManager.error(self, f"Could not delete game: {e}")
            return
        self._on_game_deleted(game_id)

    def _on_game_deleted(self, game_id: str):
        """Keep paging and batch selection state in sync after a delete."""
        self._offset = max(0, self._offset - 1)
        self._total = max(0, self._total - 1)
        self.filter_bar.set_result_count(self._total)
        self.games = [g for g in self.games if getattr(g, "game_id", None) != game_id]
        self.game_list.remove_row(game_id)
        self._selected_games.pop(game_id, None)
        self._batch_queued_ids.discard(game_id)
        self.game_list.set_selected_ids(set(self._selected_games))
        self.batch_selection_bar.set_count(len(self._selected_games))
        self._refresh_batch_availability()
        self.game_deleted.emit(game_id)
        if self._offset < self._total:
            self._load_more()
        else:
            self._update_empty_state()
        self._update_selection_bar_page()
        try:
            if self.history_manager.get_analysis_batch() is not None:
                self.refresh_batch_queue()
        except Exception as e:
            logger.debug(f"Failed to refresh batch queue after delete: {e}")

    def refresh_game(self, game_id: str | None):
        """Refresh one rendered row after its analysis changed."""
        if not game_id:
            return
        try:
            row = self.history_manager.fetch_game_row(game_id)
            if row:
                self.game_list.update_row(game_id, self.history_manager.row_to_game_analysis(row))
        except Exception as e:
            logger.debug(f"Failed to refresh history row {game_id}: {e}")
        self._refresh_batch_availability()


    def on_game_selected(self, game):
        self.game_selected.emit(self._full_game(game))

    def _on_game_action_requested(self, game, action: str):
        self.game_action_requested.emit(self._full_game(game), action)

    def _full_game(self, game):
        """Hydrate a list row into the complete record before handing it out.

        List rows intentionally carry only metadata and summary (no moves, no
        pgn), so anything that opens a game needs the full record loaded for
        that one id — never for the whole page.
        """
        game_id = getattr(game, "game_id", None)
        if not game_id or game.moves or game.pgn_content:
            return game
        try:
            full = self.history_manager.get_game_analysis(game_id)
        except Exception as e:
            logger.error(f"Failed to hydrate game {game_id}: {e}")
            return game
        return full or game

    def clear_history(self):
        if self._batch_running:
            ToastManager.warning(
                self, "Pause or cancel the running batch before deleting all games."
            )
            return

        from src.gui.utils.gui_utils import confirm_dialog

        if confirm_dialog(
            self,
            "Delete All Games",
            "Delete every game from History? This cannot be undone.",
            confirm_label="Delete All",
        ):
            self.history_manager.clear_history()
            logger.info("Deleted all games from history via UI")
            self.hide_batch_queue()
            self.history_cleared.emit()
            self.load_history()

    def export_games(self):
        try:
            import csv

            from PyQt6.QtWidgets import QFileDialog

            file_name, _ = QFileDialog.getSaveFileName(
                self, "Export Games", "games.csv", "CSV Files (*.csv)"
            )
            if not file_name:
                return

            query = self._current_query()
            total = self.history_manager.count_games(query)
            if not total:
                ToastManager.warning(self, "No games to export.")
                return

            exported_count = 0
            with open(file_name, mode="w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=GAME_CSV_COLUMNS)
                writer.writeheader()

                for game_dict in self.history_manager.iter_games_for_export(query):
                    row = {
                        k: game_dict.get(k) if game_dict.get(k) is not None else ""
                        for k in GAME_CSV_COLUMNS
                    }
                    writer.writerow(row)
                    exported_count += 1

            logger.info(f"Exported {exported_count} games to {file_name}")
            ToastManager.success(self, f"Exported {exported_count} games.")

        except Exception as e:
            logger.error(f"Export failed: {e}")
            ToastManager.error(self, f"Export failed: {e}")

    def export_annotated_pgn(self):
        if self._export_worker is not None:
            return

        try:
            from PyQt6.QtWidgets import QFileDialog

            file_name, _ = QFileDialog.getSaveFileName(
                self,
                "Export Annotated PGN",
                "games.pgn",
                "PGN Files (*.pgn)",
            )
            if not file_name:
                return
            if not Path(file_name).suffix:
                file_name = f"{file_name}.pgn"

            self.btn_export.setEnabled(False)
            self.btn_cancel_export.setVisible(True)
            self._export_toast = ToastManager.loading(
                self, "Exporting annotated PGN…", show_progress=True
            )
            worker = AnnotatedPGNExportWorker(
                self.history_manager,
                file_name,
                self._current_query(),
            )
            self._export_worker = worker
            worker.exported.connect(self._on_annotated_pgn_exported)
            worker.progress.connect(self._on_annotated_pgn_export_progress)
            worker.cancelled.connect(self._on_annotated_pgn_export_cancelled)
            worker.error.connect(self._on_annotated_pgn_export_error)
            worker.finished.connect(lambda: remove_worker(worker))
            worker.finished.connect(self._on_annotated_pgn_worker_finished)
            register_worker(worker)
            worker.start()
        except Exception as e:
            logger.error("Failed to start annotated PGN export: %s", e, exc_info=True)
            self.btn_export.setEnabled(True)
            self.btn_cancel_export.setVisible(False)
            if self._export_toast is not None:
                self._export_toast.update(f"Export failed: {e}", variant="error")
            else:
                ToastManager.error(self, f"Export failed: {e}")
            self._export_toast = None

    def _on_annotated_pgn_export_progress(self, processed: int, total: int) -> None:
        if self._export_toast is not None:
            self._export_toast.update(
                f"Exporting games: {processed} of {total}…", variant="loading"
            )
            self._export_toast.set_progress(processed / total if total else 0)

    def _on_annotated_pgn_exported(self, count: int, skipped: int) -> None:
        if self._export_toast is not None:
            if count:
                message = f"Exported {count} games."
                if skipped:
                    message += f" Skipped {skipped} invalid games."
                self._export_toast.update(message, variant="success")
            elif skipped:
                self._export_toast.update(
                    f"No valid games exported; skipped {skipped} invalid games.",
                    variant="warning",
                )
            else:
                self._export_toast.update("No games to export.", variant="warning")
            self._export_toast = None

    def _on_annotated_pgn_export_cancelled(self, _count: int, _skipped: int) -> None:
        if self._export_toast is not None:
            self._export_toast.update(
                "Export cancelled. No file was written.", variant="warning"
            )
            self._export_toast = None

    def _on_annotated_pgn_export_error(self, message: str) -> None:
        if self._export_toast is not None:
            self._export_toast.update(f"Export failed: {message}", variant="error")
            self._export_toast = None

    def _on_annotated_pgn_worker_finished(self) -> None:
        self._export_worker = None
        self.btn_export.setEnabled(True)
        self.btn_cancel_export.setVisible(False)
        self.btn_cancel_export.setEnabled(True)
        self.btn_cancel_export.setText("Cancel export")

    def _cancel_annotated_pgn_export(self) -> None:
        if self._export_worker is None:
            return
        self._export_worker.request_cancel()
        self.btn_cancel_export.setEnabled(False)
        self.btn_cancel_export.setText("Cancelling…")

    def import_games(self):
        handle: ToastHandle | None = None
        try:
            from PyQt6.QtWidgets import QFileDialog

            file_name, _ = QFileDialog.getOpenFileName(
                self, "Import Games", "", "CSV Files (*.csv)"
            )
            if not file_name:
                return

            handle = ToastManager.loading(self, "Importing games…")

            self._import_worker = GameImportWorker(self.history_manager, file_name, parent=self)

            def _on_import_finished(imported_count: int, skipped_count: int):
                logger.info(
                    f"Imported {imported_count} games from {file_name} (skipped: {skipped_count})"
                )
                self.apply_filters()
                if imported_count > 0:
                    self.games_imported.emit(imported_count)
                handle.update(
                    f"Imported: {imported_count}, Skipped: {skipped_count}",
                    variant="success",
                )
                self._import_worker = None

            def _on_import_error(err: str):
                logger.error(f"Import failed: {err}")
                handle.update(f"Import failed: {err}", variant="error")
                self._import_worker = None

            self._import_worker.finished.connect(_on_import_finished)
            self._import_worker.error.connect(_on_import_error)
            self._import_worker.start()

        except Exception as e:
            logger.error(f"Failed to start import: {e}")
            if handle is not None:
                handle.dismiss()
            ToastManager.error(self, f"Failed to start import: {e}")

    def refresh_styles(self):
        """Re-applies styles to game history view components."""
        if hasattr(self, "header_bar"):
            self.header_bar.setStyleSheet(Styles.get_header_bar_ext_style(Styles.COLOR_BACKGROUND))
        if hasattr(self, "content_widget"):
            Styles.apply_background(self.content_widget)
        if hasattr(self, "filter_bar"):
            self.filter_bar.refresh_styles()
        if hasattr(self, "btn_batch"):
            self.btn_batch.refresh_styles()
        if hasattr(self, "batch_selection_bar"):
            self.batch_selection_bar.refresh_styles()
        if hasattr(self, "batch_queue_card"):
            self.batch_queue_card.refresh_styles()
        if hasattr(self, "btn_import"):
            self.btn_import.refresh_styles()
        if hasattr(self, "btn_export"):
            self.btn_export.refresh_styles()
        if hasattr(self, "export_menu"):
            self.export_menu.setStyleSheet(Styles.get_menu_style())
        if hasattr(self, "export_csv_action"):
            self._refresh_export_menu_icons()
        if hasattr(self, "btn_clear"):
            self.btn_clear.refresh_styles()
        if hasattr(self, "btn_refresh"):
            self.btn_refresh.refresh_styles()
        if hasattr(self, "game_list"):
            self.game_list.refresh_styles()
        if hasattr(self, "import_view"):
            self.import_view.refresh_styles()

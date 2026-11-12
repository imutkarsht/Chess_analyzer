from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

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
from src.utils.logger import logger

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


class HistoryView(QWidget):
    game_selected = pyqtSignal(object)  # Emits GameAnalysis object
    game_action_requested = pyqtSignal(object, str)  # Emits (GameAnalysis, action)
    game_deleted = pyqtSignal(str)
    games_imported = pyqtSignal(int)
    history_cleared = pyqtSignal()
    open_imported_game = pyqtSignal(str, object)

    def __init__(self, config_manager=None):
        super().__init__()
        self.config_manager = config_manager
        self.history_manager = GameHistoryManager()
        self.games = []
        self._import_worker: GameImportWorker | None = None
        self.analyzing_game_id: str | None = None
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

        # Action Buttons in Top Header (Import, Export, Clear, Refresh)
        self.btn_import = self._create_icon_button("Import", "fa5s.file-import", self.import_games)
        header_layout.addWidget(self.btn_import)

        self.btn_export = self._create_icon_button("Export", "fa5s.file-export", self.export_games)
        header_layout.addWidget(self.btn_export)

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
        self.filter_bar.search_changed.connect(
            lambda: self._filter_debounce.call(self.apply_filters)
        )
        self.filter_bar.filters_changed.connect(self.apply_filters)
        content_layout.addWidget(self.filter_bar)
        self._alias_filter_controls()

        # Game List
        self.game_list = GameListWidget()
        self.game_list.game_selected.connect(self.on_game_selected)
        self.game_list.game_action_requested.connect(self._on_game_action_requested)
        self.game_list.game_deleted.connect(self._on_game_deleted)
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

    def _create_icon_button(self, text, icon_name, callback, danger=False):
        """Create a Button with a themed icon."""
        return Button(
            text,
            ButtonVariant.FILLED,
            icon=icon_name,
            danger=danger,
            on_click=callback,
        )

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

    def load_history(self):
        """Reload the current query from the first page, keeping the reader's place."""
        self._reload(preserve_position=True)

    def apply_filters(self):
        """Re-run the query from the first page after a filter or sort change."""
        self._reload(preserve_position=False)

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
            analysis_status=self.analysis_filter.value() or "",
            ownership=self.ownership_filter.value() or "",
            speed=self.type_filter.current_value() or "",
            source=self.source_filter.current_value() or "",
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
            self._schedule_prefetch()
        except Exception as e:
            logger.error(f"Failed to load history: {e}")

    def _update_empty_state(self) -> None:
        if self._total > 0:
            self.game_list.show_list()
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
        except Exception as e:
            logger.error(f"Failed to load more history: {e}")
        finally:
            self._loading_more = False

    def _on_game_deleted(self, game_id: str):
        """Keep paging state in sync after an in-place delete."""
        self._offset = max(0, self._offset - 1)
        self._total = max(0, self._total - 1)
        self.filter_bar.set_result_count(self._total)
        self.games = [g for g in self.games if getattr(g, "game_id", None) != game_id]
        self.game_deleted.emit(game_id)
        if self._offset < self._total:
            self._load_more()
        else:
            self._update_empty_state()

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
        from src.gui.utils.gui_utils import confirm_dialog

        if confirm_dialog(
            self,
            "Delete All Games",
            "Delete every game from History? This cannot be undone.",
            confirm_label="Delete All",
        ):
            self.history_manager.clear_history()
            logger.info("Deleted all games from history via UI")
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

            history_games = self.history_manager.get_all_games(limit=None)
            if not history_games:
                ToastManager.warning(self, "No games to export.")
                return

            with open(file_name, mode="w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=GAME_CSV_COLUMNS)
                writer.writeheader()

                for game_dict in history_games:
                    row = {
                        k: game_dict.get(k) if game_dict.get(k) is not None else ""
                        for k in GAME_CSV_COLUMNS
                    }
                    writer.writerow(row)

            logger.info(f"Exported {len(history_games)} games to {file_name}")
            ToastManager.success(self, f"Exported {len(history_games)} games.")

        except Exception as e:
            logger.error(f"Export failed: {e}")
            ToastManager.error(self, f"Export failed: {e}")

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
        if hasattr(self, "btn_import"):
            self.btn_import.refresh_styles()
        if hasattr(self, "btn_export"):
            self.btn_export.refresh_styles()
        if hasattr(self, "btn_clear"):
            self.btn_clear.refresh_styles()
        if hasattr(self, "btn_refresh"):
            self.btn_refresh.refresh_styles()
        if hasattr(self, "game_list"):
            self.game_list.refresh_styles()
        if hasattr(self, "import_view"):
            self.import_view.refresh_styles()

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.backend.storage.game_history import GAME_CSV_COLUMNS, GameHistoryManager
from src.backend.storage.game_query import (
    RESULT_DRAW,
    RESULT_LOSS,
    RESULT_WIN,
    GameQuery,
)
from src.gui.components import Button, ButtonVariant, Input, InputVariant, Select
from src.gui.components.feedback.toast import ToastHandle, ToastManager
from src.gui.components.lists.game_list_widget import GameListWidget
from src.gui.styles import Styles
from src.gui.utils.debounce import Debouncer
from src.gui.utils.gui_utils import create_button
from src.utils.logger import logger


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

        # Header Bar Container
        self.header_bar = QFrame()
        self.header_bar.setStyleSheet(Styles.get_header_bar_ext_style(Styles.COLOR_BACKGROUND))
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(24, 12, 24, 12)
        header_layout.setSpacing(8)

        # Title
        self.header_lbl = QLabel("Game History")
        self.header_lbl.setStyleSheet(
            Styles.get_label_style(size=22, color=Styles.COLOR_TEXT_PRIMARY, bold=True)
            + " "
            + Styles.get_transparent_label_style()
        )
        header_layout.addWidget(self.header_lbl)

        header_layout.addStretch()

        # Action Buttons in Top Header (Import, Export, Clear, Refresh)
        self.btn_import = self._create_icon_button("Import", "fa5s.file-import", self.import_games)
        header_layout.addWidget(self.btn_import)

        self.btn_export = self._create_icon_button("Export", "fa5s.file-export", self.export_games)
        header_layout.addWidget(self.btn_export)

        self.btn_clear = self._create_icon_button(
            "Clear", "fa5s.trash-alt", self.clear_history, danger=True
        )
        header_layout.addWidget(self.btn_clear)

        self.btn_refresh = create_button(
            "Refresh", style="secondary", on_click=self.load_history, icon_name="fa5s.sync-alt"
        )
        header_layout.addWidget(self.btn_refresh)

        self.layout.addWidget(self.header_bar)

        # Content Container Widget
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet(Styles.get_background_style())
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(24, 16, 24, 16)
        content_layout.setSpacing(16)

        # Filter Row
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)

        # Search Bar
        self.search_input = Input(
            placeholder="Search player, opening, date...",
            variant=InputVariant.SEARCH,
            clearable=True,
        )
        self.search_input.setMinimumWidth(240)
        # A search field is a fixed column, not the flexible one: the filters
        # need the remaining width more than the text box does.
        self.search_input.setMaximumWidth(420)
        self.search_input.textChanged.connect(
            lambda *_: self._filter_debounce.call(self.apply_filters)
        )
        filter_layout.addWidget(self.search_input, 1)

        filter_layout.addSpacing(10)

        lbl_style = (
            f"{Styles.get_label_style(size=12, color=Styles.COLOR_TEXT_PRIMARY, weight=600)}"
            " border: none; background: transparent;"
        )

        def _filter_label(text: str) -> QLabel:
            # A Preferred label policy lets the row's spare width stretch the
            # label and push its dropdown away, so pin it to the text width.
            lbl = QLabel(text)
            lbl.setStyleSheet(lbl_style)
            lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            return lbl

        # Result Filter
        self.result_label = _filter_label("Result:")
        filter_layout.addWidget(self.result_label)

        self.result_filter = Select(
            ["All", "Wins", "Losses", "Draws"], on_change=self.apply_filters
        )
        self.result_filter.setFixedWidth(100)
        filter_layout.addWidget(self.result_filter)

        # Type / Speed Category Filter
        self.type_label = _filter_label("Type:")
        filter_layout.addWidget(self.type_label)

        self.type_filter = Select(
            ["All", "Rapid", "Blitz", "Bullet", "Classical", "Daily", "UltraBullet"],
            on_change=self.apply_filters,
        )
        self.type_filter.setFixedWidth(110)
        filter_layout.addWidget(self.type_filter)

        # Source Filter
        self.source_label = _filter_label("Source:")
        filter_layout.addWidget(self.source_label)

        self.source_filter = Select(
            ["All", "Chess.com", "Lichess", "File"], on_change=self.apply_filters
        )
        self.source_filter.setFixedWidth(110)
        filter_layout.addWidget(self.source_filter)

        filter_layout.addStretch()

        # Sort Dropdown
        self.sort_label = _filter_label("Sort:")
        filter_layout.addWidget(self.sort_label)

        self.sort_dropdown = Select(
            ["Newest First", "Oldest First", "Most Moves", "Fewest Moves"],
            on_change=self.apply_filters,
        )
        self.sort_dropdown.setFixedWidth(135)
        filter_layout.addWidget(self.sort_dropdown)

        content_layout.addLayout(filter_layout)

        # Game List
        self.game_list = GameListWidget()
        self.game_list.game_selected.connect(self.on_game_selected)
        self.game_list.game_action_requested.connect(self._on_game_action_requested)
        self.game_list.game_deleted.connect(self._on_game_deleted)
        self.game_list.load_more_requested.connect(self._load_more)
        content_layout.addWidget(self.game_list)
        self.apply_default_view_mode()

        self.layout.addWidget(self.content_widget)

        # Load initial data
        self.load_history()

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

    def _page_size(self) -> int:
        """Cards are taller than rows, so the page size follows the view mode."""
        if self.game_list.view_mode == "detailed":
            return self._DETAILED_PAGE_SIZE
        return self._COMPACT_PAGE_SIZE

    def _current_query(self) -> GameQuery:
        """Translate the filter controls into a single database query."""
        result_map = {
            "Wins": RESULT_WIN,
            "Losses": RESULT_LOSS,
            "Draws": RESULT_DRAW,
        }
        source_map = {"Chess.com": "chesscom", "Lichess": "lichess", "File": "file"}
        sort_map = {
            "Newest First": "newest",
            "Oldest First": "oldest",
            "Most Moves": "most_moves",
            "Fewest Moves": "fewest_moves",
        }
        type_text = self.type_filter.currentText()
        return GameQuery(
            search=self.search_input.text().strip().lower(),
            result=result_map.get(self.result_filter.currentText(), ""),
            speed="" if type_text == "All" else type_text,
            source=source_map.get(self.source_filter.currentText(), ""),
            sort=sort_map.get(self.sort_dropdown.currentText(), "newest"),
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
            self._offset = 0
            self.game_list.reset(total, self.usernames)

            games = self._fetch_page(query)
            self._offset = len(games)
            self.games = games
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
                    self.game_list.append_rows(extra)
                    pages += 1
            self._schedule_prefetch()
        except Exception as e:
            logger.error(f"Failed to load history: {e}")

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
                return
            self._offset += len(games)
            self.games.extend(games)
            self.game_list.append_rows(games)
        except Exception as e:
            logger.error(f"Failed to load more history: {e}")
        finally:
            self._loading_more = False

    def _on_game_deleted(self, game_id: str):
        """Keep paging state in sync after an in-place delete."""
        self._offset = max(0, self._offset - 1)
        self._total = max(0, self._total - 1)
        self.games = [g for g in self.games if getattr(g, "game_id", None) != game_id]
        self.game_deleted.emit(game_id)
        if self._offset < self._total:
            self._load_more()

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
            "Clear History",
            "Are you sure you want to clear all game history? This cannot be undone.",
            confirm_label="Clear All",
        ):
            self.history_manager.clear_history()
            logger.info("Cleared all game history via UI")
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
        if hasattr(self, "header_lbl"):
            self.header_lbl.setStyleSheet(
                Styles.get_label_style(size=22, color=Styles.COLOR_TEXT_PRIMARY, bold=True)
                + " "
                + Styles.get_transparent_label_style()
            )
        if hasattr(self, "content_widget"):
            self.content_widget.setStyleSheet(Styles.get_background_style())
        if hasattr(self, "search_input"):
            self.search_input.refresh_styles()
        if hasattr(self, "result_label"):
            self.result_label.setStyleSheet(
                Styles.get_label_style(size=12, color=Styles.COLOR_TEXT_PRIMARY, weight=600)
            )
        if hasattr(self, "type_label"):
            self.type_label.setStyleSheet(
                Styles.get_label_style(size=12, color=Styles.COLOR_TEXT_PRIMARY, weight=600)
            )
        if hasattr(self, "source_label"):
            self.source_label.setStyleSheet(
                Styles.get_label_style(size=12, color=Styles.COLOR_TEXT_PRIMARY, weight=600)
            )
        if hasattr(self, "sort_label"):
            self.sort_label.setStyleSheet(
                Styles.get_label_style(size=12, color=Styles.COLOR_TEXT_PRIMARY, weight=600)
            )
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

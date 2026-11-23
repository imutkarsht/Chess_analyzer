# SPDX-License-Identifier: GPL-3.0-only
"""Game ingestion, PGN parsing, history hydration, and drag/drop handling."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QDialog

from src.backend.storage.pgn_parser import PGNParser, looks_like_pgn
from src.constants import MAX_PGN_TEXT_CHARS, PAGE_ANALYSIS, PAGE_HISTORY
from src.gui.dialogs.load_game_dialog import LoadGameDialog
from src.gui.styles import Styles
from src.gui.theme.typography import TextTone
from src.gui.utils.clock import compute_clock_times
from src.gui.utils.worker_registry import (
    register_worker,
    remove_worker,
)
from src.utils.logger import logger
from src.workers.imports import PgnIndexWorker

if TYPE_CHECKING:
    from src.gui.main_window.window import MainWindow


class GameLoadingController(QObject):
    """Owns game ingestion, PGN parsing, history hydration, and drag/drop."""

    game_loaded = pyqtSignal(object)
    game_load_failed = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.host: MainWindow | None = None
        self._pgn_drop_worker: PgnIndexWorker | None = None

    def attach(self, host: MainWindow) -> None:
        self.host = host
        self.setParent(host)

    def shutdown(self) -> None:
        worker, self._pgn_drop_worker = self._pgn_drop_worker, None
        if worker is None:
            return
        try:
            worker.cancel()
            if worker.isRunning():
                worker.wait()
        finally:
            remove_worker(worker)

    def load_game_from_history(self, game):
        if hasattr(self.host, "worker") and self.host.worker and self.host.worker.isRunning():
            if self.host.current_game and getattr(game, "game_id", None) == getattr(
                self.host.current_game, "game_id", None
            ):
                self.host.sidebar.set_active(0)
                self.host.switch_page(0)
                return
            else:
                self.host.show_toast(
                    "An analysis is currently in progress for another game. "
                    "Please stop the ongoing analysis first.",
                    "warning",
                )
                return

        self.load_game(game, from_history=True)
        self.host.sidebar.set_active(0)  # Switch to Analyze tab
        self.host.switch_page(0)

    def on_game_action_requested(self, game, action: str):
        """Handle action button requests from game cards ('reanalyze', 'resume', 'analyze', 'view_analysis')."""
        coordinator = getattr(self.host, "analysis_coordinator", None)
        if (
            coordinator is not None
            and coordinator.batch_running
            and action != "view_analysis"
        ):
            self.host.show_toast(
                "Pause or cancel the batch from History before analyzing another game.",
                "warning",
            )
            return

        if action == "view_analysis" or (
            hasattr(self.host, "worker")
            and self.host.worker
            and self.host.worker.isRunning()
            and self.host.current_game
            and getattr(game, "game_id", None) == getattr(self.host.current_game, "game_id", None)
        ):
            self.host.sidebar.set_active(0)
            self.host.switch_page(0)
            return

        if hasattr(self.host, "worker") and self.host.worker and self.host.worker.isRunning():
            self.host.show_toast(
                "An analysis is currently in progress for another game. "
                "Please stop the ongoing analysis first.",
                "warning",
            )
            return

        self.load_game_from_history(game)
        if action == "resume":
            self.host.start_analysis(resume=True)
        elif action in ("reanalyze", "analyze"):
            self.host.start_analysis(resume=False)

    def load_game_from_metrics(self, game, move_index: int = -1):
        target = game
        if isinstance(game, str):
            game = self.host.history_manager.get_game_analysis(game)
        if not game:
            logger.warning(f"Could not load game from metrics: {target}")
            return
        self.load_game(game, from_history=True)
        self.host.sidebar.set_active(0)  # Switch to Analyze tab
        self.host.switch_page(0)
        if move_index >= 0:
            self.host.on_move_selected(move_index)

    def _update_analysis_view_mode(self, has_game: bool):
        """Toggle between Hero focus landing (no game) and 3-column analysis workspace (game loaded)."""
        if hasattr(self.host, "analysis_header_bar"):
            self.host.analysis_header_bar.setVisible(has_game)
        if hasattr(self.host, "left_widget"):
            self.host.left_widget.setVisible(has_game)
        if hasattr(self.host, "analysis_panel"):
            self.host.analysis_panel.setVisible(has_game)
        if hasattr(self.host, "welcome_panel"):
            self.host.welcome_panel.setVisible(not has_game)
        if hasattr(self.host, "captured_black"):
            self.host.captured_black.setVisible(has_game)
        if hasattr(self.host, "captured_white"):
            self.host.captured_white.setVisible(has_game)
        if hasattr(self.host, "controls"):
            self.host.controls.setVisible(has_game)
        if hasattr(self.host, "empty_state_cta"):
            self.host.empty_state_cta.setVisible(not has_game)
        if hasattr(self.host, "historic_info_bar"):
            self.host.historic_info_bar.setVisible(not has_game)
        if hasattr(self.host, "game_info_label"):
            self.host.game_info_label.setVisible(has_game)
        if hasattr(self.host, "btn_explore"):
            self.host.btn_explore.setVisible(has_game)
        if hasattr(self.host, "btn_analyze"):
            self.host.btn_analyze.setVisible(has_game)
        if hasattr(self.host, "btn_follow"):
            self.host.btn_follow.setVisible(False)

        # Eval bar is only shown during game playback / analysis, and only
        # when the user has not disabled it in Appearance settings.
        if hasattr(self.host, "board_widget") and hasattr(self.host.board_widget, "set_eval_bar_visible"):
            self.host.board_widget.set_eval_bar_visible(has_game)
            if hasattr(self.host.board_widget, "_enforce_square_board"):
                self.host.board_widget._enforce_square_board()

        if hasattr(self.host, "splitter"):
            total_w = self.host.splitter.width()
            if total_w < 500:
                # The splitter has not been laid out yet; use the real window
                # width minus the sidebar instead of a fixed design width.
                sidebar_w = self.host.sidebar.width() if hasattr(self.host, "sidebar") else 0
                total_w = max(self.host.width() - sidebar_w, 1)
            if has_game:
                left_w = int(total_w * 0.25)
                center_w = int(total_w * 0.45)
                right_w = total_w - left_w - center_w
                self.host.splitter.setSizes([left_w, center_w, right_w, 0])
                self.host.splitter.setStretchFactor(0, 25)
                self.host.splitter.setStretchFactor(1, 45)
                self.host.splitter.setStretchFactor(2, 30)
                self.host.splitter.setStretchFactor(3, 0)
            else:
                left_w = int(total_w * 0.60)
                right_w = total_w - left_w
                self.host.splitter.setSizes([0, left_w, 0, right_w])
                self.host.splitter.setStretchFactor(0, 0)
                self.host.splitter.setStretchFactor(1, 6)
                self.host.splitter.setStretchFactor(2, 0)
                self.host.splitter.setStretchFactor(3, 4)

        if hasattr(self.host, "_update_game_info_placement"):
            self.host._update_game_info_placement()

    def _parse_and_load_game(self, pgn_text, source_data=None, status_msg=""):
        """
        Parse the first valid game, attach source data, and load it.
        Returns True on success, False on failure.
        """
        logger.debug("Parsing first game from %d PGN chars", len(pgn_text))
        try:
            game = PGNParser.parse_first_game(pgn_text)
        except Exception as exc:
            logger.error("Failed to parse PGN: %s", exc)
            game = None
        if game is None:
            self.host.show_toast(
                "Could not read this game. The PGN data may be empty or corrupted.",
                "error",
            )
            self.game_load_failed.emit("Could not read this game.")
            return False

        if source_data:
            game.source_data = source_data
        self.host.games = [game]
        self.load_game(game)
        if status_msg:
            self.host._set_status(status_msg, "success")
        return True

    def load_game(self, game, from_history: bool = False):
        # A new game must never inherit the previous game's open variation.
        self.host._exit_variation()
        if hasattr(self.host, "variation"):
            self.host.variation.reset_session()

        # History cards carry no moves/pgn by design; hydrate the one game being
        # opened rather than the whole list.
        if from_history and not game.moves and getattr(game, "game_id", None):
            full = self.host.history_manager.get_game_analysis(game.game_id)
            if full is not None:
                game = full

        # If game has no moves but has PGN content (loaded from history), parse it
        if not game.moves and game.pgn_content:
            try:
                parsed_games = PGNParser.parse_pgn_text(game.pgn_content)
                if parsed_games:
                    parsed = parsed_games[0]
                    game.moves = parsed.moves
                    game.metadata.chess960 = parsed.metadata.chess960
            except Exception as e:
                logger.error(f"Failed to parse PGN for history game: {e}")
                self.host.show_toast("Failed to load game moves.", "error")
                self.game_load_failed.emit("Failed to load game moves.")
                return

        # Metadata Enrichment from source data if available
        if hasattr(game, "source_data") and game.source_data:
            self.enrich_game_metadata(game, game.source_data)

        # If this game already exists in history and has more analyzed moves, hydrate from history
        if getattr(game, "game_id", None):
            existing = self.host.history_manager.get_game_analysis(game.game_id)
            if existing and existing.analyzed_moves_count > game.analyzed_moves_count:
                game = existing

        # Persist newly imported game to history immediately (only if not already from history and has moves)
        if (
            not from_history
            and getattr(game, "pgn_content", None)
            and getattr(game, "moves", None)
            and len(game.moves) > 0
        ):
            try:
                self.host.history_manager.save_game(game, game.pgn_content)
                if hasattr(self.host, "history_view"):
                    # New row belongs at the top of the active result set.
                    self.host.history_view.apply_filters()
            except Exception as e:
                logger.debug(f"Failed to auto-save loaded game to history: {e}")

        self.host._stop_replay()
        self.host.current_game = game
        self._update_analysis_view_mode(has_game=True)
        # Clear historic landing state so the move detector doesn't fire during game playback
        self.host._current_historic = None
        self.host._historic_move_found = False

        white = game.metadata.white
        black = game.metadata.black
        result = game.metadata.result
        w_elo = game.metadata.white_elo or game.metadata.headers.get("WhiteElo", "?")
        b_elo = game.metadata.black_elo or game.metadata.headers.get("BlackElo", "?")

        info_text = f"{white} ({w_elo}) vs {black} ({b_elo})  [{result}]"
        self.host.game_info_label.setText(info_text)
        if hasattr(self.host, "board_game_header"):
            self.host.board_game_header.set_info(white, w_elo, black, b_elo, result)
        logger.info(f"Loaded game: {white} vs {black} [{result}], {len(game.moves)} moves")

        self.host.board_widget.load_game(game)
        self.host._position_captured_pieces()
        self.host.move_list_panel.set_game(game)
        self.host.analysis_panel.set_game(game)
        if hasattr(self.host, "_refresh_variation_badges"):
            self.host._refresh_variation_badges()
        self.host.captured_white.update_captured(None)
        self.host.captured_black.update_captured(None)

        # Initialize clocks using linear enumerate lookup (Fix 3)
        white_time, black_time = compute_clock_times(game.moves, index=-1)
        self.host.captured_white.update_clock(white_time)
        self.host.captured_black.update_clock(black_time)

        # Wire graph click → board navigation.
        if getattr(self.host.analysis_panel, "graph_widget", None) is not None:
            try:
                self.host.analysis_panel.graph_widget.move_clicked.disconnect(
                    self.host.on_move_selected
                )
            except (RuntimeError, TypeError):
                pass
            self.host.analysis_panel.graph_widget.move_clicked.connect(self.host.on_move_selected)

        # Navigate to final position if game already has analysis data
        if game.moves and any(m.classification for m in game.moves):
            self.host.on_move_selected(len(game.moves) - 1)

        self.host._update_analyze_button(running=False)
        logger.info(f"Game loaded: {game.metadata.white} vs {game.metadata.black}")
        self.host.resource_manager.play_sound("notify")

        # Auto-start tour if user has not seen the analysis workspace tour yet
        if (
            hasattr(self.host, "tour_manager")
            and not self.host.tour_manager.has_seen_tour("analysis")
            and self.host.stack.currentIndex() == 0
        ):
            QTimer.singleShot(400, lambda: self.host._auto_start_tour(0))
        self.game_loaded.emit(game)

    def enrich_game_metadata(self, game, source_data):
        """
        Enriches game metadata with information from API source data
        if the PGN parsing yielded missing or placeholder values.
        """
        md = game.metadata

        def get_rating(data, color):
            if color in data and isinstance(data[color], dict):
                return data[color].get("rating")
            flat_key = f"{color}_rating"
            if flat_key in data:
                return data[flat_key]
            return None

        # White Elo
        if not md.white_elo or md.white_elo == "?" or md.white_elo == "None":
            r = get_rating(source_data, "white")
            if r:
                md.white_elo = str(r)
                md.headers["WhiteElo"] = str(r)

        # Black Elo
        if not md.black_elo or md.black_elo == "?" or md.black_elo == "None":
            r = get_rating(source_data, "black")
            if r:
                md.black_elo = str(r)
                md.headers["BlackElo"] = str(r)

        # Update source
        if not getattr(md, "source", None) or md.source == "file":
            if "url" in source_data and "chess.com" in source_data["url"]:
                md.source = "chesscom"
            elif (
                "url" in source_data
                and "lichess.org" in source_data["url"]
                or "white_rating" in source_data
            ):
                md.source = "lichess"

    def open_load_dialog(self, initial_source: int = 0, initial_text: str = None):
        """Open the unified Load Game dialog."""
        from src.constants import SRC_PGN_TEXT

        dialog = LoadGameDialog(self.host, initial_source=initial_source)
        try:
            if initial_text and initial_source == SRC_PGN_TEXT:
                panel = dialog._pgn_text_panel
                if panel.load_initial_text(initial_text):
                    panel._parse()

            if dialog.exec() == QDialog.DialogCode.Accepted:
                if dialog._navigate_to_settings:
                    self.host.sidebar.set_active(4)
                    QTimer.singleShot(0, lambda: self.host.switch_page(4))
                elif getattr(dialog, "_pending_batch", None):
                    self._open_import_batch(dialog._pending_batch)
        finally:
            dialog.deleteLater()

    def _open_import_batch(self, batch) -> None:
        """Single game goes to Analysis; a multi-game batch opens History import."""
        candidates = getattr(batch, "candidates", [])
        if not candidates:
            return
        if len(candidates) == 1:
            candidate = candidates[0]
            self.host.sidebar.set_active(PAGE_ANALYSIS)
            self.host.switch_page(PAGE_ANALYSIS)
            self._parse_and_load_game(
                candidate.pgn_text(),
                source_data=candidate.source_data,
                status_msg="Game loaded.",
            )
            return

        self.host.sidebar.set_active(PAGE_HISTORY)
        self.host.history_view.show_import_workspace(batch)
        self.host.switch_page(PAGE_HISTORY)

    def _on_imported_game_requested(self, pgn_text: str, source_data) -> None:
        """Open a game chosen in the History import workspace."""
        if hasattr(self.host, "history_view"):
            self.host.history_view.close_import_workspace()
        self.host.sidebar.set_active(PAGE_ANALYSIS)
        self.host.switch_page(PAGE_ANALYSIS)
        self._parse_and_load_game(
            pgn_text,
            source_data=source_data,
            status_msg="Game loaded.",
        )

    def paste_pgn_from_clipboard(self):
        """Landing quick action: load clipboard PGN, or open the dialog on its PGN tab."""
        text = QApplication.clipboard().text()
        if len(text) > MAX_PGN_TEXT_CHARS:
            self.host._set_status(
                "PGN text is too large to paste. Open it as a file instead.",
                "warning",
            )
            return
        text = text.strip()
        if looks_like_pgn(text):
            self._parse_and_load_game(text, status_msg="Game loaded from clipboard.")
            return
        self.open_load_dialog(initial_source=1, initial_text=text or None)

    def _set_drop_highlight(self, active: bool):
        """Show the hero card as a drop target while a valid drag is in progress."""
        self.host._drop_highlight_active = active
        if hasattr(self.host, "empty_state_cta"):
            self.host.empty_state_cta.setStyleSheet(Styles.get_empty_state_cta_style(active))
        if hasattr(self.host, "lbl_hero_hint"):
            self.host.lbl_hero_hint.setText(
                "Drop to load game" if active else self.host._hero_hint_default
            )
            self.host.lbl_hero_hint.set_tone(
                TextTone.ACCENT if active else TextTone.SECONDARY
            )
        if hasattr(self.host, "lbl_hero_keys"):
            self.host.lbl_hero_keys.setVisible(not active)

    def handle_drag_enter(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith((".pgn", ".txt")):
                    self._set_drop_highlight(True)
                    event.acceptProposedAction()
                    return
        elif event.mimeData().hasText():
            text = event.mimeData().text()
            if len(text) <= MAX_PGN_TEXT_CHARS and looks_like_pgn(text):
                self._set_drop_highlight(True)
                event.acceptProposedAction()
                return
        event.ignore()

    def handle_drag_leave(self, event):
        self._set_drop_highlight(False)
        event.accept()

    def handle_drop(self, event):
        self._set_drop_highlight(False)
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith((".pgn", ".txt")):
                    self._load_dropped_pgn(file_path)
                    event.acceptProposedAction()
                    return
        elif event.mimeData().hasText():
            text = event.mimeData().text()
            if len(text) > MAX_PGN_TEXT_CHARS:
                self.host._set_status(
                    "PGN text is too large. Open it as a file instead.",
                    "warning",
                )
                event.ignore()
                return
            if self._parse_and_load_game(
                text.strip(), status_msg="Game loaded from dropped text"
            ):
                event.acceptProposedAction()
                return
        event.ignore()

    def _load_dropped_pgn(self, file_path: str) -> None:
        """Index a dropped file off-thread and load its first game."""
        previous = getattr(self, "_pgn_drop_worker", None)
        if previous is not None and previous.isRunning():
            previous.cancel()

        worker = PgnIndexWorker(path=file_path)
        self._pgn_drop_worker = worker
        self.host._set_status("Loading PGN file…", "info")
        worker.completed.connect(
            lambda result, w=worker: self._on_dropped_pgn_indexed(result, w)
        )
        worker.failed.connect(lambda message: self.host._set_status(message, "error"))
        worker.cancelled.connect(
            lambda: self.host._set_status("PGN load cancelled", "info")
        )
        worker.finished.connect(
            lambda w=worker: self._release_drop_worker(w)
        )
        register_worker(worker)
        worker.start()

    def _release_drop_worker(self, worker: PgnIndexWorker) -> None:
        if getattr(self, "_pgn_drop_worker", None) is worker:
            self._pgn_drop_worker = None
        remove_worker(worker)

    def _on_dropped_pgn_indexed(self, index, worker: PgnIndexWorker) -> None:
        if getattr(self, "_pgn_drop_worker", None) is not worker:
            return
        if not index.games:
            self.host._set_status("No valid games found in this file.", "warning")
            return
        self._parse_and_load_game(
            index.game_text(0), status_msg="Game loaded from file"
        )

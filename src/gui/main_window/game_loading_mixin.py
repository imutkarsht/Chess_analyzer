from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QDialog, QMessageBox

from src.backend.storage.pgn_parser import PGNParser
from src.gui.dialogs.load_game_dialog import LoadGameDialog
from src.gui.main_window.navigation_mixin import compute_clock_times
from src.utils.logger import logger


class GameLoadingMixin:
    """Game ingestion, PGN parsing, history loading, and drag-and-drop support."""

    def load_game_from_history(self, game):
        if hasattr(self, "worker") and self.worker and self.worker.isRunning():
            if self.current_game and getattr(game, "game_id", None) == getattr(
                self.current_game, "game_id", None
            ):
                self.sidebar.set_active(0)
                self.switch_page(0)
                return
            else:
                QMessageBox.warning(
                    self,
                    "Analysis in Progress",
                    "An analysis is currently in progress for another game. Please stop the ongoing analysis first.",
                )
                return

        self.load_game(game, from_history=True)
        self.sidebar.set_active(0)  # Switch to Analyze tab
        self.switch_page(0)

    def on_game_action_requested(self, game, action: str):
        """Handle action button requests from game cards ('reanalyze', 'resume', 'analyze', 'view_analysis')."""
        if action == "view_analysis" or (
            hasattr(self, "worker")
            and self.worker
            and self.worker.isRunning()
            and self.current_game
            and getattr(game, "game_id", None) == getattr(self.current_game, "game_id", None)
        ):
            self.sidebar.set_active(0)
            self.switch_page(0)
            return

        if hasattr(self, "worker") and self.worker and self.worker.isRunning():
            QMessageBox.warning(
                self,
                "Analysis in Progress",
                "An analysis is currently in progress for another game. Please stop the ongoing analysis first.",
            )
            return

        self.load_game_from_history(game)
        if action == "resume":
            self.start_analysis(resume=True)
        elif action in ("reanalyze", "analyze"):
            self.start_analysis(resume=False)

    def load_game_from_metrics(self, game, move_index: int = -1):
        target = game
        if isinstance(game, str):
            game = self.history_manager.get_game_analysis(game)
        if not game:
            logger.warning(f"Could not load game from metrics: {target}")
            return
        self.load_game(game, from_history=True)
        self.sidebar.set_active(0)  # Switch to Analyze tab
        self.switch_page(0)
        if move_index >= 0:
            self.on_move_selected(move_index)

    def _update_analysis_view_mode(self, has_game: bool):
        """Toggle between Hero focus landing (no game) and 3-column analysis workspace (game loaded)."""
        if hasattr(self, "left_widget"):
            self.left_widget.setVisible(has_game)
        if hasattr(self, "analysis_panel"):
            self.analysis_panel.setVisible(has_game)
        if hasattr(self, "captured_black"):
            self.captured_black.setVisible(has_game)
        if hasattr(self, "captured_white"):
            self.captured_white.setVisible(has_game)
        if hasattr(self, "controls"):
            self.controls.setVisible(has_game)
        if hasattr(self, "empty_state_cta"):
            self.empty_state_cta.setVisible(not has_game)
        if hasattr(self, "game_info_label"):
            self.game_info_label.setVisible(has_game)
        if hasattr(self, "btn_explore"):
            self.btn_explore.setVisible(has_game)
        if hasattr(self, "btn_analyze"):
            self.btn_analyze.setVisible(has_game)

        # Eval bar is only shown during game playback / analysis
        if hasattr(self, "board_widget") and hasattr(self.board_widget, "eval_bar"):
            self.board_widget.eval_bar.setVisible(has_game)
            if hasattr(self.board_widget, "_enforce_square_board"):
                self.board_widget._enforce_square_board()

        if has_game and hasattr(self, "splitter"):
            total_w = self.splitter.width()
            if total_w < 500:
                total_w = max(self.width(), 1100)
            self.splitter.setSizes([int(total_w * 0.22), int(total_w * 0.52), int(total_w * 0.26)])

    def _parse_and_load_game(self, pgn_text, source_data=None, status_msg=""):
        """
        Common pattern: Parse PGN text, attach source data, load first game.
        Returns True on success, False on failure.
        """
        self.games = PGNParser.parse_pgn_text(pgn_text)
        if self.games:
            if source_data:
                for g in self.games:
                    g.source_data = source_data
            self.load_game(self.games[0])
            if status_msg:
                self._set_status(status_msg, "success")
            return True
        else:
            QMessageBox.warning(
                self, "Error", "Could not read this game.\nThe PGN data may be empty or corrupted."
            )
            return False

    def load_game(self, game, from_history: bool = False):
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
                QMessageBox.warning(self, "Error", "Failed to load game moves.")
                return

        # Metadata Enrichment from source data if available
        if hasattr(game, "source_data") and game.source_data:
            self.enrich_game_metadata(game, game.source_data)

        # If this game already exists in history and has more analyzed moves, hydrate from history
        if getattr(game, "game_id", None):
            existing = self.history_manager.get_game_analysis(game.game_id)
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
                self.history_manager.save_game(game, game.pgn_content)
                if hasattr(self, "history_view"):
                    self.history_view.load_history()
            except Exception as e:
                logger.debug(f"Failed to auto-save loaded game to history: {e}")

        self.current_game = game
        self._update_analysis_view_mode(has_game=True)

        white = game.metadata.white
        black = game.metadata.black
        result = game.metadata.result
        w_elo = game.metadata.white_elo or game.metadata.headers.get("WhiteElo", "?")
        b_elo = game.metadata.black_elo or game.metadata.headers.get("BlackElo", "?")

        info_text = f"{white} ({w_elo}) vs {black} ({b_elo})  [{result}]"
        self.game_info_label.setText(info_text)
        logger.info(f"Loaded game: {white} vs {black} [{result}], {len(game.moves)} moves")

        self.board_widget.load_game(game)
        self.move_list_panel.set_game(game)
        self.analysis_panel.set_game(game)
        self.captured_white.update_captured(None)
        self.captured_black.update_captured(None)

        # Initialize clocks using linear enumerate lookup (Fix 3)
        white_time, black_time = compute_clock_times(game.moves, index=-1)
        self.captured_white.update_clock(white_time)
        self.captured_black.update_clock(black_time)

        # Wire graph click → board navigation.
        try:
            self.analysis_panel.graph_widget.move_clicked.disconnect(self.on_move_selected)
        except (RuntimeError, TypeError):
            pass
        self.analysis_panel.graph_widget.move_clicked.connect(self.on_move_selected)

        # Navigate to final position if game already has analysis data
        if game.moves and any(m.classification for m in game.moves):
            self.on_move_selected(len(game.moves) - 1)

        self._update_analyze_button(running=False)
        logger.info(f"Game loaded: {game.metadata.white} vs {game.metadata.black}")
        self.resource_manager.play_sound("notify")

        # Auto-start tour if user has not seen the analysis workspace tour yet
        if (
            hasattr(self, "tour_manager")
            and not self.tour_manager.has_seen_tour(0)
            and self.stack.currentIndex() == 0
        ):
            QTimer.singleShot(400, lambda: self._auto_start_tour(0))

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
        dialog = LoadGameDialog(self, initial_source=initial_source)
        if initial_text and initial_source == 1:
            dialog._pgn_text_panel._text_edit.setPlainText(initial_text)
            dialog._pgn_text_panel._parse()

        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog._navigate_to_settings:
                self.sidebar.set_active(4)
                QTimer.singleShot(0, lambda: self.switch_page(4))
            elif dialog._pending_pgn:
                pgn = dialog._pending_pgn
                sd = dialog._pending_source_data
                QTimer.singleShot(
                    0,
                    lambda: self._parse_and_load_game(
                        pgn, source_data=sd, status_msg="Game loaded."
                    ),
                )

    def _on_game_ready(self, pgn_text: str, source_data):
        """Deprecated: Kept for compatibility. Called by LoadGameDialog when the user confirms a game selection."""
        self._parse_and_load_game(pgn_text, source_data=source_data, status_msg="Game loaded.")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith((".pgn", ".txt")):
                    event.acceptProposedAction()
                    return
        elif event.mimeData().hasText():
            text = event.mimeData().text()
            if "[Event" in text or "1." in text:
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith((".pgn", ".txt")):
                    try:
                        with open(file_path, encoding="utf-8", errors="replace") as f:
                            content = f.read()
                        if self._parse_and_load_game(content, status_msg="Game loaded from file"):
                            event.acceptProposedAction()
                            return
                    except Exception as e:
                        logger.error(f"Failed to load dropped PGN file: {e}")
        elif event.mimeData().hasText():
            text = event.mimeData().text().strip()
            if self._parse_and_load_game(text, status_msg="Game loaded from dropped text"):
                event.acceptProposedAction()
                return
        event.ignore()

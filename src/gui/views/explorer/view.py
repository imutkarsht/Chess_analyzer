"""
Explorer View - composition root for the Opening Explorer.

Page chrome lives in :mod:`src.gui.views.explorer.ui_mixin`, book rendering in
:mod:`src.gui.views.explorer.book_mixin`, online lookup in
:mod:`src.gui.views.explorer.online_mixin`, and engine/classification in
:mod:`src.gui.views.explorer.engine_mixin`. This module keeps the
board/navigation state that ties those slices together.
"""

import os
from datetime import date

import chess
import chess.pgn
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QWidget

from src.backend.analysis.engine import resolve_engine_path
from src.backend.analysis.opening_db import OpeningDB, _normalize_fen
from src.backend.analysis.polyglot_book import PolyglotBookManager
from src.gui.engine_lines import LiveEngineSession
from src.gui.styles import Styles
from src.gui.views.explorer.book_mixin import ExplorerBookMixin
from src.gui.views.explorer.engine_mixin import ExplorerEngineMixin
from src.gui.views.explorer.online_mixin import ExplorerOnlineMixin
from src.gui.views.explorer.ui_mixin import ExplorerUiMixin
from src.utils.logger import logger
from src.utils.path_utils import get_resource_path, get_user_data_dir


class ExplorerView(
    ExplorerUiMixin,
    ExplorerBookMixin,
    ExplorerOnlineMixin,
    ExplorerEngineMixin,
    QWidget,
):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        engine_path = resolve_engine_path(self.config_manager) or self.config_manager.get(
            "engine_path", "stockfish"
        )
        self.session = LiveEngineSession(
            engine_path,
            config_manager=self.config_manager,
            parent=self,
        )
        self.session.lines_changed.connect(self._on_lines_changed)
        self.session.state_changed.connect(self._on_engine_state)
        self.session.error.connect(self._on_engine_error)

        # Board / move state
        self.is_chess960 = False
        self.starting_fen = chess.STARTING_FEN
        self.board = chess.Board()
        self.move_history = []  # (Move, FEN before, FEN after, SAN)

        # Classification state
        self.last_eval = None
        self.pending_classification_index = -1
        self.pending_before_eval = None
        self._classify_queue: list[int] = []
        self._classify_before_eval: dict | None = None
        self.classify_enabled = False

        # Book panel state
        self._book_row_widgets: list[QWidget] = []
        self._current_book_count = 0
        self._book_skeleton = None
        self._piece_pixmap_cache: dict = {}

        self._init_opening_sources()
        self.setup_ui()
        self._init_online_explorer()

        # The engine worker starts lazily on the first engine-lines request:
        # the toggle is off by default, so an eager search would heat the
        # machine on every launch.
        self.update_opening_db(self.board.fen())

    def _init_opening_sources(self) -> None:
        tsv_dir = get_resource_path("assets/openings")
        db_path = os.path.join(get_user_data_dir(), "openings.db")
        self.opening_db = OpeningDB(db_path)
        try:
            self.opening_db.initialize(tsv_dir)
        except Exception as e:
            logger.warning(f"Failed to initialize opening DB: {e}")
        self.opening_db.connect()

        # Polyglot book (loaded from config, optional — opened lazily)
        polyglot_path = self.config_manager.get("polyglot_book_path", "")
        self.polyglot_manager = PolyglotBookManager(
            polyglot_path if polyglot_path else None
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        # Resume only when the user has engine lines enabled; cached lines
        # stay visible otherwise.
        if self.chk_engine.isChecked():
            self.session.resume()

    def hideEvent(self, event):
        # Leaving the Explorer (or minimising the window) must not leave a
        # Stockfish search running out of sight. Lines stay on screen.
        self.session.pause()
        super().hideEvent(event)

    def closeEvent(self, event):
        self.session.shutdown()
        self._explorer_debounce.stop()
        for worker in list(self._explorer_workers):
            try:
                worker.wait(1500)
            except RuntimeError:
                pass
        if hasattr(self, "opening_db") and self.opening_db:
            try:
                self.opening_db.close()
            except Exception:
                pass
        if hasattr(self, "polyglot_manager") and self.polyglot_manager:
            try:
                self.polyglot_manager.close()
            except Exception:
                pass
        super().closeEvent(event)

    def update_engine_path(self, path):
        """Swap the engine binary without restarting the application."""
        self.session.set_engine_path(path)

    # ------------------------------------------------------------------
    # Position loading
    # ------------------------------------------------------------------

    def load_fen(self, fen):
        """Loads a starting position into the explorer."""
        castling = fen.split()[2]
        self.is_chess960 = castling != "-" and any(
            c not in "KQkq" for c in castling
        )
        self.starting_fen = fen
        try:
            test_board = chess.Board(fen, chess960=self.is_chess960)
        except ValueError as e:
            logger.error(f"Invalid FEN: {fen} — {e}")
            return

        self.board = test_board
        self.move_history = []
        self.move_list_widget.clear()
        self.pending_classification_index = -1
        self.last_eval = None
        self.pending_before_eval = None

        self.board_widget.load_fen(fen, chess960=self.is_chess960)
        self.update_opening_db(fen)

        self._refresh_engine(fen)
        self._update_material()

    def load_board_state(
        self,
        source_board,
        source_moves=None,
        *,
        chess960=None,
        starting_fen=None,
        move_index=None,
    ):
        """Loads a full board state including its move stack history.

        Parameters
        ----------
        source_board : chess.Board
            Board at the displayed position. After navigation the main board
            only carries the current ply on its move stack, so ``move_index``
            (with ``source_moves``) is the authoritative replay length.
        source_moves : list[MoveAnalysis] | None
            Move-level metadata with classifications.
        chess960 : bool | None
            Authoritative chess960 flag from game metadata.
        starting_fen : str | None
            Authoritative starting FEN from game metadata.
        move_index : int | None
            Zero-based ply currently displayed by the main board.
        """
        self.is_chess960 = (
            chess960
            if chess960 is not None
            else getattr(source_board, "chess960", False)
        )
        if starting_fen:
            self.starting_fen = starting_fen
        elif source_moves and source_moves[0].fen_before:
            self.starting_fen = source_moves[0].fen_before
        else:
            self.starting_fen = source_board.starting_fen

        # Board.set_position() rebuilds the main board from the current move's
        # fen_before, so source_board.move_stack holds only that one ply. Use
        # the authoritative MoveAnalysis list plus the displayed ply instead.
        if source_moves and move_index is not None:
            target = max(-1, min(move_index, len(source_moves) - 1))
            replay_moves = [
                chess.Move.from_uci(source_moves[i].uci) for i in range(target + 1)
            ]
        else:
            num_moves = len(source_board.move_stack)
            if self.is_chess960 and source_moves and len(source_moves) >= num_moves:
                replay_moves = [
                    chess.Move.from_uci(source_moves[i].uci) for i in range(num_moves)
                ]
            else:
                replay_moves = list(source_board.move_stack)

        self.board = chess.Board(self.starting_fen, chess960=self.is_chess960)
        self.move_history = []
        self.move_list_widget.clear()
        self.pending_classification_index = -1
        self.last_eval = None

        # Temporarily disconnect move_made so replaying does not classify.
        try:
            self.board_widget.move_made.disconnect(self.on_move_made)
        except TypeError:
            pass
        self.board_widget.load_fen(fen=self.starting_fen, chess960=self.is_chess960)

        # A corrupted or mismatched start position must never crash the app:
        # resync from the recorded fen_before, then stop.
        for i, move in enumerate(replay_moves):
            if not self.board.is_pseudo_legal(move):
                expected = (
                    source_moves[i].fen_before
                    if source_moves and i < len(source_moves)
                    else None
                )
                if expected:
                    self.board = chess.Board(expected, chess960=self.is_chess960)
                    self.board_widget.board = chess.Board(
                        expected, chess960=self.is_chess960
                    )
                if not self.board.is_pseudo_legal(move):
                    logger.warning(
                        "Explorer replay stopped at ply %s: illegal move %s",
                        i + 1,
                        move.uci(),
                    )
                    break

            fen_before = self.board.fen()
            try:
                san = self.board.san(move)
            except (AssertionError, ValueError):
                san = move.uci()
            self.board.push(move)
            fen_after = self.board.fen()

            self.board_widget.board.push(move)
            self.move_history.append((move, fen_before, fen_after, san))
            self.move_list_widget.add_move(san)

            if (
                source_moves
                and i < len(source_moves)
                and source_moves[i].classification
            ):
                self.move_list_widget.update_classification(
                    i, source_moves[i].classification
                )

        self.board_widget.set_best_move(None)
        self.board_widget.set_last_move_classification(None)
        self.board_widget.move_made.connect(self.on_move_made)
        self.board_widget.update_board()

        fen = self.board.fen()
        self.update_opening_db(fen)
        self._update_material()
        self._refresh_engine(fen)

        if self.classify_enabled and self.chk_engine.isChecked():
            self._start_backlog_classification()

    def on_move_made(self, fen):
        # Clear backlog classification when the user makes a manual move.
        self._classify_queue = []
        self._classify_before_eval = None

        self._update_material()
        if not self.board_widget.board.move_stack:
            return

        move = self.board_widget.board.peek()
        try:
            san = self.board.san(move)
        except (AssertionError, ValueError):
            san = move.uci()

        fen_before = self.board.fen()
        self.board.push(move)
        fen_after = self.board.fen()

        if self.move_list_widget.current_index < len(self.move_history) - 1:
            self.move_history = self.move_history[
                : self.move_list_widget.current_index + 1
            ]

        self.move_history.append((move, fen_before, fen_after, san))
        self.move_list_widget.add_move(san)

        self.pending_classification_index = len(self.move_history) - 1
        self.pending_before_eval = dict(self.last_eval) if self.last_eval else None

        if self.classify_enabled:
            self.move_list_widget.set_pending_classification(
                self.pending_classification_index, True
            )

        # Instant book check by UCI to avoid SAN ambiguity.
        node_id = self.opening_db.get_node_by_fen(_normalize_fen(fen_before))
        if self._is_book_move(node_id, move.uci(), fen_before) and self.classify_enabled:
            self.move_list_widget.update_classification(
                self.pending_classification_index, "Book"
            )
            self.pending_classification_index = -1
            self.board_widget.last_move_classification = "Book"

        self._refresh_engine(fen_after)
        self.update_opening_db(fen_after)

    def on_move_list_clicked(self, index):
        if index < -1 or index >= len(self.move_history):
            return

        current_idx = self.move_list_widget.current_index
        is_step_forward = index == current_idx + 1
        is_step_back = index == current_idx - 1

        # Step forward/back by one move instead of replaying the whole game.
        if is_step_forward and current_idx >= -1 and index < len(self.move_history):
            self.board.push(self.move_history[index][0])
        elif is_step_back and current_idx >= 0:
            self.board.pop()
        else:
            self.board = chess.Board(self.starting_fen, chess960=self.is_chess960)
            for i in range(index + 1):
                self.board.push(self.move_history[i][0])

        self.board_widget.set_board(self.board.copy())
        self.move_list_widget.set_index(index)

        fen = self.board.fen()
        self._refresh_engine(fen)
        self.update_opening_db(fen)

        if is_step_forward:
            if not self.move_list_widget.moves[index].get("classification"):
                self.pending_classification_index = index
                self.pending_before_eval = (
                    dict(self.last_eval) if self.last_eval else None
                )
            else:
                self.pending_classification_index = -1
                self.pending_before_eval = None
        else:
            self.pending_classification_index = -1
            self.pending_before_eval = None

    # ------------------------------------------------------------------
    # Shared board helpers
    # ------------------------------------------------------------------

    def _update_material(self):
        """Update captured pieces and material advantage."""
        fen = self.board_widget.board.fen()
        self.captured_white.update_captured(fen)
        self.captured_black.update_captured(fen)

    # ------------------------------------------------------------------
    # Board interactions
    # ------------------------------------------------------------------

    def _play_move(self, move, label: str) -> None:
        try:
            self.board_widget.attempt_move(
                move.from_square, move.to_square, promotion=move.promotion
            )
        except Exception as e:
            logger.warning(f"Failed to play {label}: {e}")

    def on_book_move_clicked(self, san):
        if not san:
            return
        try:
            move = self.board_widget.board.parse_san(san)
        except Exception as e:
            logger.warning(f"Failed to play book move {san}: {e}")
            return
        self._play_move(move, f"book move {san}")

    def on_engine_line_clicked(self, uci_move):
        try:
            move = chess.Move.from_uci(uci_move)
        except ValueError as e:
            logger.warning(f"Failed to play engine line move {uci_move}: {e}")
            return
        self._play_move(move, f"engine line move {uci_move}")

    def _normalize_san(self, text):
        """Uppercase a lowercase piece letter for standard SAN parsing."""
        if not text:
            return text
        if text[0] in "kqrbn" and text[0].islower():
            text = text[0].upper() + text[1:]
        return text

    def _on_move_text_entered(self):
        """Play a move typed as SAN text (e.g. 'e4', 'Nf3', 'O-O')."""
        text = self.move_input.text().strip()
        if not text:
            return
        fen_before = self.board_widget.board.fen()
        try:
            text = self._normalize_san(text)
            move = self.board_widget.board.parse_san(text)
            self.board_widget.attempt_move(
                move.from_square, move.to_square, promotion=move.promotion
            )
            if self.board_widget.board.fen() == fen_before:
                raise ValueError(f"Illegal move: {text}")
            self.move_input.clear()
        except Exception:
            self.move_input.set_invalid()
            QTimer.singleShot(1000, self._reset_move_input_style)

    def _reset_move_input_style(self):
        self.move_input.clear_invalid()

    def _flip_board(self):
        self.board_widget.flip_board()
        self.board_widget.draw_interactive_overlays()

        self.left_layout.removeWidget(self.white_header_widget)
        self.left_layout.removeWidget(self.black_header_widget)
        if self.board_widget.is_flipped:
            self.left_layout.insertWidget(0, self.white_header_widget)
            self.left_layout.insertWidget(2, self.black_header_widget)
        else:
            self.left_layout.insertWidget(0, self.black_header_widget)
            self.left_layout.insertWidget(2, self.white_header_widget)

    def _copy_to_clipboard(self, text: str, label: str) -> None:
        QApplication.clipboard().setText(text)
        self._set_engine_status(
            f"✓ {label} copied", Styles.COLOR_ENGINE_READY
        )
        QTimer.singleShot(2000, self._restore_engine_status)

    def _copy_fen(self):
        self._copy_to_clipboard(self.board_widget.board.fen(), "FEN")

    def _copy_pgn(self):
        game = chess.pgn.Game()
        game.headers["Event"] = "Chess Analyzer Pro"
        game.headers["Site"] = "Opening Explorer"
        game.headers["Date"] = date.today().strftime("%Y.%m.%d")
        game.headers["Round"] = "-"
        game.headers["White"] = "-"
        game.headers["Black"] = "-"
        game.headers["Result"] = "*"
        if self.starting_fen != chess.STARTING_FEN:
            game.headers["FEN"] = self.starting_fen
            game.headers["SetUp"] = "1"
        node = game
        for move, _before, _after, _san in self.move_history:
            node = node.add_variation(move)
        exporter = chess.pgn.StringExporter(
            headers=True, comments=False, variations=False
        )
        self._copy_to_clipboard(game.accept(exporter), "PGN")

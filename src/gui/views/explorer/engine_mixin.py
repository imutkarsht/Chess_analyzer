"""Live engine lines, eval status and move classification for the explorer."""

import chess

from src.backend.analysis.math_utils import get_win_probability
from src.backend.analysis.move_classifier import classify_move
from src.backend.analysis.opening_db import _normalize_fen
from src.gui.styles import Styles
from src.gui.views.explorer.types import ClassificationContext
from src.utils.logger import logger


class ExplorerEngineMixin:
    """Drives the shared engine session and the classification backlog."""

    # ------------------------------------------------------------------
    # Engine panel
    # ------------------------------------------------------------------

    def _refresh_engine(self, fen):
        """Request live lines for ``fen``, or clear the panel when disabled.

        The shared session owns the sequence counter, so any result that
        arrives for a position we already left is discarded for us.
        """
        if self.chk_engine.isChecked():
            self.lines_widget.set_empty_text("Analysing position…")
            self.session.request(fen, chess960=self.is_chess960, emit_empty=True)
            return
        self.session.clear(emit=False)
        self._clear_engine_panel()

    def _clear_engine_panel(self) -> None:
        self.lines_widget.set_empty_text("Enable Engine Lines to see analysis")
        self.lines_widget.clear()
        self.board_widget.set_best_move(None)
        self.board_widget.eval_bar.set_eval(0.0, None)

    def on_engine_toggled(self, enabled):
        self.lines_widget.setVisible(enabled)
        self.session.set_enabled(enabled)
        if enabled:
            self._refresh_engine(self.board_widget.board.fen())
            return
        self._clear_engine_panel()

    def on_legal_moves_toggled(self, checked):
        self.board_widget.set_show_legal_moves(checked)

    def _set_engine_status(self, text: str, color: str) -> None:
        self.engine_status_label.setText(text)
        self.engine_status_label.setStyleSheet(Styles.get_engine_status_style(color))

    def _restore_engine_status(self) -> None:
        """Return the status pill to the shared session's current state."""
        state = getattr(self.session, "state", "ready")
        if state == "thinking":
            self._set_engine_status("⬤ Analyzing...", Styles.COLOR_ENGINE_BUSY)
        elif state == "error":
            self._set_engine_status("⬤ Engine error", Styles.COLOR_ENGINE_BUSY)
        else:
            self._set_engine_status("⬤ Ready", Styles.COLOR_ENGINE_READY)

    def _on_engine_state(self, state):
        """Map the shared session's lifecycle to the status pill."""
        if state == "thinking":
            self._set_engine_status("⬤ Analyzing...", Styles.COLOR_ENGINE_BUSY)
        elif state == "error":
            self._set_engine_status("⬤ Engine error", Styles.COLOR_ENGINE_BUSY)
        else:
            self._set_engine_status("⬤ Ready", Styles.COLOR_ENGINE_READY)

    def _on_engine_error(self, message):
        logger.warning("Explorer live engine error: %s", message)

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _is_book_move(self, node_id, uci, fen_before):
        """Check if a move (by UCI) is a book move at the given node.

        Checks both the SQLite opening DB and the Polyglot book.
        """
        try:
            board = chess.Board(fen_before, chess960=self.is_chess960)
        except ValueError:
            return False

        if node_id is not None:
            try:
                for candidate_san in self.opening_db.get_children(node_id):
                    if board.parse_san(candidate_san).uci() == uci:
                        return True
            except Exception as e:
                logger.warning(f"Error checking SQLite book move: {e}")

        if self.polyglot_manager.is_available():
            try:
                for entry in self.polyglot_manager.reader.find_all(board):
                    if entry.move.uci() == uci:
                        return True
            except Exception as e:
                logger.warning(f"Error checking polyglot book move: {e}")

        return False

    def _start_backlog_classification(self):
        """Queue all unclassified moves for sequential classification.

        Moves are classified one at a time: for each move, we first get
        the engine eval for the position BEFORE the move, then step
        forward to the position AFTER the move and run classification.
        """
        self._classify_queue = []
        for i, _move in enumerate(self.move_history):
            if not self.move_list_view.entries[i].classification:
                self._classify_queue.append(i)
        if not self._classify_queue:
            return
        if not self.classify_enabled or not self.chk_engine.isChecked():
            return
        self._classify_before_eval = None
        self.on_move_list_clicked(self._classify_queue[0] - 1)

    def _process_backlog_step(self):
        """Called after classification completes — advance to next backlog move."""
        if not self._classify_queue or self.pending_classification_index >= 0:
            return
        if not self.classify_enabled or not self.chk_engine.isChecked():
            self._classify_queue = []
            return
        # We're at the after-position of the classified move = before-position
        # of the next; wait for its eval in _on_lines_changed.
        self._classify_before_eval = None
        self._refresh_engine(self.board.fen())

    def on_classify_toggled(self, checked):
        self.classify_enabled = checked
        if not checked:
            if self.pending_classification_index >= 0:
                self.move_list_view.set_pending(
                    self.pending_classification_index, False
                )
            self.pending_classification_index = -1
            self.pending_before_eval = None
            self._classify_queue = []
            self._classify_before_eval = None
            return

        # Classification depends on engine evals.
        if not self.chk_engine.isChecked():
            self.chk_engine.setChecked(True)
        self._start_backlog_classification()

    def _on_lines_changed(self, lines):
        """Render White-perspective lines and drive eval + classification.

        ``EngineLine`` scores are already White perspective, so no
        side-to-move conversion happens here (doing it twice was what made
        the eval bar flip when Black was to move).
        """
        self.lines_widget.set_lines(lines)
        if not lines:
            self.board_widget.set_best_move(None)
            return

        best = lines[0]
        if best.first_move:
            self.board_widget.set_best_move(best.first_move)

        if best.cp is None and best.mate is None:
            return

        self.board_widget.eval_bar.set_eval(best.cp, best.mate)
        depth = best.depth or 0
        if depth < 10:
            return

        # Cache the eval for the next move (White perspective, centipawns).
        self.last_eval = {
            "cp": best.cp,
            "mate": best.mate,
            "best_move": best.first_move,
        }

        # Backlog classification: step forward once the before-eval is ready.
        if (
            self._classify_queue
            and self.pending_classification_index < 0
            and self._classify_before_eval is None
        ):
            idx = self._classify_queue.pop(0)
            before_eval = dict(self.last_eval)
            self._classify_before_eval = before_eval
            move = self.move_history[idx][0]
            self.board.push(move)
            self.board_widget.board.push(move)
            self.board_widget.update_board()
            self.board_widget.draw_interactive_overlays()
            self.move_list_view.set_current_index(idx)
            self.pending_classification_index = idx
            self.pending_before_eval = before_eval
            self._refresh_engine(self.board.fen())
            return

        if (
            self.classify_enabled
            and self.pending_classification_index >= 0
            and depth >= 12
            and self.pending_before_eval is not None
        ):
            self._run_classification(best.cp, best.mate)
            if self._classify_queue:
                self._process_backlog_step()

    def _run_classification(self, after_cp, after_mate):
        if self.pending_classification_index < 0:
            return

        move_obj, fen_before, _fen_after, san = self.move_history[
            self.pending_classification_index
        ]

        # Check book status first (UCI avoids SAN ambiguity).
        norm_fen = _normalize_fen(fen_before)
        node_id = self.opening_db.get_node_by_fen(norm_fen)
        if self._is_book_move(node_id, move_obj.uci(), fen_before):
            self.move_list_view.set_classification(
                self.pending_classification_index, "Book"
            )
            self.board_widget.set_last_move_classification("Book")
            self.pending_classification_index = -1
            return

        turn_color = chess.Board(
            fen_before, chess960=self.is_chess960
        ).turn
        side_str = "white" if turn_color == chess.WHITE else "black"

        before_eval = self.pending_before_eval or {}
        ctx = ClassificationContext(
            san=san,
            uci=move_obj.uci(),
            best_move=before_eval.get("best_move"),
            eval_before_cp=before_eval.get("cp"),
            eval_before_mate=before_eval.get("mate"),
            eval_after_cp=after_cp,
            eval_after_mate=after_mate,
        )
        ctx.win_chance_before = get_win_probability(
            ctx.eval_before_cp, ctx.eval_before_mate
        )
        ctx.win_chance_after = get_win_probability(
            ctx.eval_after_cp, ctx.eval_after_mate
        )

        wpl = abs(ctx.win_chance_before - ctx.win_chance_after)
        classify_move(ctx, wpl, side_str)

        if ctx.classification:
            self.move_list_view.set_classification(
                self.pending_classification_index, ctx.classification
            )
            self.board_widget.set_last_move_classification(ctx.classification)

        self.pending_classification_index = -1

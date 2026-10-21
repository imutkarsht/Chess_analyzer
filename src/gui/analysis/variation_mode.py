"""
Variation mode — a playable, engine-backed branch on the main analysis board.

The controller is deliberately FEN-based: a variation is "this position plus
whatever moves the user plays from it". Entry points (best move, refutation,
engine line) all hand it a FEN, so it never guesses an index from the game.
"""

import chess
from PyQt6.QtCore import QObject, pyqtSignal

from src.utils.logger import logger


class VariationMode(QObject):
    """Owns the board's analysis state while a variation is being explored."""

    entered = pyqtSignal()
    exited = pyqtSignal(int)  # game move index to restore
    position_changed = pyqtSignal(str)  # current variation FEN

    def __init__(self, board_widget, move_list_panel, bar, parent=None):
        super().__init__(parent)
        self.board_widget = board_widget
        self.move_list_panel = move_list_panel
        self.bar = bar

        self.return_index = -1
        self.base_fen: str | None = None
        self.suggestion_uci: str | None = None
        self.sans: list[str] = []
        # Moves undone from the tip, kept so the arrows can step back *and*
        # forward through the line that has already been explored.
        self._future: list[chess.Move] = []
        self._replaying = False
        self._best_uci: str | None = None
        self._active = False

        bar.play_best_requested.connect(self.play_best)
        bar.undo_requested.connect(self.undo)
        bar.reset_requested.connect(self.reset)
        bar.exit_requested.connect(self.exit)

        board_widget.move_made.connect(self._on_move_made)
        move_list_panel.lines_updated.connect(self._on_lines_updated)

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def can_go_back(self) -> bool:
        """True while there is an explored move to step back over."""
        return bool(self.sans)

    @property
    def can_go_forward(self) -> bool:
        """True while there is an undone move to replay or a best move to play."""
        return bool(self._future) or bool(self._best_uci)

    def enter(
        self,
        fen: str,
        suggestion_uci: str | None,
        return_index: int,
        chess960: bool = False,
    ) -> bool:
        """Show ``fen`` as an explorable position, optionally hinting a move."""
        if not fen:
            return False
        try:
            board = chess.Board(fen, chess960=chess960)
        except ValueError as e:
            logger.warning("Cannot explore invalid FEN %s: %s", fen, e)
            return False

        # Re-entering from inside a variation keeps the original return point.
        if not self._active:
            self.return_index = return_index
        self._active = True
        self.base_fen = fen
        self.suggestion_uci = self._legal_uci(board, suggestion_uci)
        self.sans = []
        self._future = []
        self._replaying = False
        self._best_uci = self.suggestion_uci

        self.board_widget.load_analysis_position(fen, chess960=chess960)
        self.board_widget.set_dimmed(True)
        self.board_widget.set_best_move(self.suggestion_uci)
        # Hold the last known eval until the engine reports on this position;
        # a forced 0.0 reads as a real evaluation change.

        self.bar.setVisible(True)
        self._update_bar()
        self.move_list_panel.begin_variation(fen, board.turn == chess.WHITE)
        self.position_changed.emit(fen)
        self.entered.emit()
        return True

    def exit(self, notify: bool = True) -> None:
        """Leave the variation.

        ``notify=True`` asks the window to restore the game position (Esc/Exit
        button). ``notify=False`` is used when the caller is already navigating
        or loading another game and will set the board itself.
        """
        if not self._active:
            return
        self._active = False
        self.bar.setVisible(False)
        self.move_list_panel.end_variation()
        self.board_widget.set_best_move(None)
        self.board_widget.set_dimmed(False)
        self.board_widget.interactive = False
        self.sans = []
        self._future = []
        self._replaying = False
        self._best_uci = None
        self.base_fen = None
        self.suggestion_uci = None
        if notify:
            self.exited.emit(self.return_index)

    def play_best(self) -> None:
        if self._best_uci:
            self.play_uci(self._best_uci)

    def play_uci(self, uci: str) -> bool:
        """Play a UCI move on the variation board (promotion-aware)."""
        if not self._active or not uci:
            return False
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return False
        if move not in self.board_widget.board.legal_moves:
            return False
        self.board_widget.attempt_move(move.from_square, move.to_square, move.promotion)
        return True

    def undo(self) -> None:
        """Step back one explored move, keeping it for ``forward`` to replay."""
        if not self._active or not self.sans:
            return
        board = self.board_widget.board
        if not board.move_stack:
            return
        move = board.peek()
        if not self.board_widget.undo_move():
            return
        self.sans.pop()
        self._future.insert(0, move)
        self._refresh_after_position_change()
        if not self.sans:
            # Back at the branch point: restore the entry suggestion immediately.
            self._best_uci = self.suggestion_uci
            self.board_widget.set_best_move(self.suggestion_uci)
            self._update_bar()

    def forward(self) -> None:
        """Replay an undone move, otherwise play the engine's best continuation."""
        if not self._active:
            return
        if self._future:
            move = self._future.pop(0)
            self._replaying = True
            try:
                self.board_widget.attempt_move(
                    move.from_square, move.to_square, move.promotion
                )
            finally:
                self._replaying = False
            return
        self.play_best()

    def go_to_start(self) -> None:
        """Rewind to the branch point without discarding the explored line."""
        if not self._active or not self.sans:
            return
        board = self.board_widget.board
        while board.move_stack:
            self._future.insert(0, board.pop())
        self.sans.clear()
        self.board_widget.update_board()
        self.board_widget.draw_interactive_overlays()
        self._refresh_after_position_change()
        self._best_uci = self.suggestion_uci
        self.board_widget.set_best_move(self.suggestion_uci)
        self._update_bar()

    def go_to_end(self) -> None:
        """Replay every undone move to reach the tip of the explored line."""
        if not self._active or not self._future:
            return
        board = self.board_widget.board
        while self._future:
            move = self._future.pop(0)
            self.sans.append(self._san_for(board, move))
            board.push(move)
        self.board_widget.update_board()
        self.board_widget.draw_interactive_overlays()
        self._refresh_after_position_change()

    def reset(self) -> None:
        if not self._active or not self.base_fen:
            return
        self.board_widget.load_analysis_position(
            self.base_fen, chess960=self.board_widget.is_chess960
        )
        self.sans.clear()
        self._future = []
        self._refresh_after_position_change()
        self._best_uci = self.suggestion_uci
        self.board_widget.set_best_move(self.suggestion_uci)
        self._update_bar()

    # ------------------------------------------------------------------ internals
    @staticmethod
    def _legal_uci(board: chess.Board, uci: str | None) -> str | None:
        if not uci:
            return None
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return None
        return uci if move in board.legal_moves else None

    @staticmethod
    def _san_for(board: chess.Board, move: chess.Move) -> str:
        """SAN for ``move`` played from ``board``; falls back to UCI."""
        try:
            return board.san(move)
        except (AssertionError, ValueError):
            return move.uci()

    def _on_move_made(self, fen: str) -> None:
        if not self._active:
            return
        # A freshly played move forks a new branch: anything undone is stale.
        if not self._replaying:
            self._future.clear()
        board = self.board_widget.board
        if board.move_stack:
            move = board.peek()
            probe = board.copy()
            probe.pop()
            self.sans.append(self._san_for(probe, move))

        self._refresh_after_position_change(fen)

    def _refresh_after_position_change(self, fen: str | None = None) -> None:
        board = self.board_widget.board
        fen = fen or board.fen()
        self._best_uci = None
        self.board_widget.set_best_move(None)
        # Keep the last eval while the engine re-analyses the new position.
        # Resetting to 0 here made the bar dive to the middle and climb back
        # after every explored move.
        self._update_bar()
        self.move_list_panel.begin_variation(fen, board.turn == chess.WHITE)
        self.position_changed.emit(fen)

    def _on_lines_updated(self, lines: list, is_white: bool, fen: str) -> None:
        """Track the engine's current best move/eval for the variation board."""
        if not self._active or not lines:
            return
        top = lines[0]
        pv = top.get("pv_uci") or top.get("pv") or []
        first = pv[0] if pv else None
        uci = first if isinstance(first, str) else (first.uci() if first else None)
        if uci:
            self._best_uci = uci
            self.board_widget.set_best_move(uci)
        self._update_bar()

        cp = top.get("cp")
        mate = top.get("mate")
        if cp is not None or mate is not None:
            # Engine scores are side-to-move relative; the eval bar wants White.
            white_cp = cp if is_white else (-cp if cp is not None else None)
            white_mate = mate if is_white else (-mate if mate is not None else None)
            self.board_widget.eval_bar.set_eval(white_cp, white_mate)

    def _update_bar(self) -> None:
        self.bar.set_state(
            " ".join(self.sans),
            can_undo=bool(self.sans),
            can_play_best=bool(self._best_uci),
        )

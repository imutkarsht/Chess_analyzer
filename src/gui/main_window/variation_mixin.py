"""Variation-mode request handling for the main window."""

import chess
from PyQt6.QtCore import QTimer

from src.backend.analysis.variation_tree import canonical_fen
from src.constants import COACH_LINE_INTERVAL_MS
from src.utils.logger import logger


class VariationMixin:
    """Glue between analysis requests, the variation controller, and badges."""

    def _on_variation_requested(self, fen: str, uci: str) -> None:
        if not self.current_game:
            return
        if getattr(self, "_full_analysis_running", False):
            self._set_status("Finish the running analysis before exploring variations", "warning")
            return

        chess960 = bool(getattr(self.current_game.metadata, "chess960", False))

        # Clicking another engine line while already inside a tree should extend
        # or select a node in that same tree rather than resetting exploration.
        if self.variation.is_active and self.variation.tree is not None:
            node = self.variation.tree.find_node_by_fen(fen)
            if node is not None:
                self.variation.select_node(node.node_id)
                if uci:
                    self.variation.play_uci(uci)
                self._finish_variation_ui()
                return

        root_index = self._game_index_for_fen(fen)
        started = self.variation.enter(
            fen,
            uci,
            return_index=self.board_widget.current_move_index,
            chess960=chess960,
            auto_play=True,
            root_label=self._variation_root_label(root_index),
        )
        if not started:
            logger.warning("Could not enter variation mode for FEN %s", fen)
            return
        self._finish_variation_ui()

    def _ensure_coach_line_timer(self) -> None:
        if getattr(self, "_coach_line_timer", None) is not None:
            return
        timer = QTimer(self)
        timer.setInterval(COACH_LINE_INTERVAL_MS)
        timer.timeout.connect(self._coach_line_tick)
        self._coach_line_timer = timer
        self._coach_line_moves: list[str] = []
        self._coach_line_index = 0

    def _on_coach_line_requested(self, fen: str, uci_moves: list[str]) -> None:
        """Open the Coach line and animate it move-by-move on the board."""
        if not self.current_game or not uci_moves:
            return
        if getattr(self, "_full_analysis_running", False):
            self._set_status("Finish the running analysis before replaying a line", "warning")
            return
        chess960 = bool(getattr(self.current_game.metadata, "chess960", False))
        self._stop_coach_line_autoplay()
        self._exit_variation()
        started = self.variation.enter(
            fen,
            None,
            return_index=self.board_widget.current_move_index,
            chess960=chess960,
            auto_play=False,
            root_label="Coach line",
        )
        if not started:
            return
        self._ensure_coach_line_timer()
        self._coach_line_moves = list(uci_moves)
        self._coach_line_index = 0
        self._finish_variation_ui()
        self._coach_line_timer.start()

    def _coach_line_tick(self) -> None:
        if not self.variation.is_active or self._coach_line_index >= len(
            self._coach_line_moves
        ):
            self._stop_coach_line_autoplay()
            return
        uci = self._coach_line_moves[self._coach_line_index]
        self._coach_line_index += 1
        if not self.variation.play_uci(uci):
            self._stop_coach_line_autoplay()

    def _stop_coach_line_autoplay(self) -> None:
        timer = getattr(self, "_coach_line_timer", None)
        if timer is not None:
            timer.stop()
        self._coach_line_moves = []
        self._coach_line_index = 0

    def _finish_variation_ui(self) -> None:
        if not self.variation.is_active:
            return
        self._update_explore_controls()

    def _on_variation_exited(self, index: int) -> None:
        self._stop_coach_line_autoplay()
        self.analysis_panel.toggle_checkbox.setEnabled(True)
        self.analysis_panel.toggle_checkbox.setToolTip("")
        self._update_explore_controls()
        # Silent: returning from a variation should not replay move sounds.
        self.on_move_selected(index, silent=True)

    def _update_explore_controls(self) -> None:
        """Board navigation is redundant inside Explore and wastes vertical space."""
        if hasattr(self, "controls"):
            self.controls.setVisible(self.current_game is not None and not self.variation.is_active)
        self._update_game_info_placement()

    def _update_game_info_placement(self) -> None:
        """Show game info above the board in normal mode, in the header while exploring."""
        has_game = getattr(self, "current_game", None) is not None
        exploring = bool(
            getattr(self, "variation", None) is not None and self.variation.is_active
        )
        if hasattr(self, "board_panel"):
            self.board_panel.set_compact(exploring)
        if hasattr(self, "board_game_header"):
            self.board_game_header.setVisible(has_game and not exploring)
        if hasattr(self, "game_info_label"):
            self.game_info_label.setVisible(has_game and exploring)

    def _on_variation_position_changed(self, fen: str) -> None:
        if hasattr(self, "captured_white") and hasattr(self, "captured_black"):
            self.captured_white.update_captured(fen)
            self.captured_black.update_captured(fen)

    def _on_variation_tree_changed(self) -> None:
        self._refresh_variation_badges()

    def _on_variation_message(self, text: str, kind: str) -> None:
        if hasattr(self, "show_toast"):
            self.show_toast(text, kind)
        else:
            self._set_status(text, kind)

    def _exit_variation(self) -> None:
        """Tear the variation down without restoring (caller sets the board)."""
        self._stop_coach_line_autoplay()
        variation = getattr(self, "variation", None)
        if variation is None or not variation.is_active:
            return
        variation.exit(notify=False)
        self._update_explore_controls()
        if hasattr(self, "analysis_panel"):
            self.analysis_panel.toggle_checkbox.setEnabled(True)
            self.analysis_panel.toggle_checkbox.setToolTip("")

    def _open_variation_tree_for_index(self, index: int) -> None:
        """Reopen a saved tree from the move-list branch badge."""
        if not self.current_game:
            return
        if getattr(self, "_full_analysis_running", False):
            self._set_status("Finish the running analysis before exploring variations", "warning")
            return
        positions = self._game_position_fens()
        fen = positions.get(index)
        if not fen:
            return
        self._exit_variation()
        chess960 = bool(getattr(self.current_game.metadata, "chess960", False))
        started = self.variation.open_tree(
            fen,
            return_index=index,
            chess960=chess960,
            root_label=self._variation_root_label(index),
        )
        if started:
            self._finish_variation_ui()

    def _refresh_variation_badges(self) -> None:
        if not hasattr(self, "move_list_panel") or not hasattr(self, "variation"):
            return
        if not self.current_game:
            self.move_list_panel.set_variation_counts({})
            return
        positions = self._game_position_fens()
        counts: dict[int, int] = {}
        for fen, branch_count in self.variation.tree_counts().items():
            for index, position_fen in positions.items():
                if position_fen == fen:
                    counts[index] = max(counts.get(index, 0), branch_count)
        self.move_list_panel.set_variation_counts(counts)

    def _game_position_fens(self) -> dict[int, str]:
        """Map each game move index to the canonical FEN *after* that move."""
        moves = getattr(self.current_game, "moves", None) or []
        if not moves:
            return {}
        chess960 = bool(getattr(self.current_game.metadata, "chess960", False))
        start = moves[0].fen_before or chess.STARTING_FEN
        board = chess.Board(start, chess960=chess960)
        positions: dict[int, str] = {}
        for index, move in enumerate(moves):
            try:
                board.push_uci(move.uci)
            except ValueError:
                break
            positions[index] = canonical_fen(board.fen(), chess960)
        return positions

    def _game_index_for_fen(self, fen: str) -> int:
        try:
            target = canonical_fen(fen, self._is_variation_chess960())
        except ValueError:
            return -1
        for index, position_fen in self._game_position_fens().items():
            if position_fen == target:
                return index
        return -1

    def _is_variation_chess960(self) -> bool:
        return bool(getattr(self.current_game.metadata, "chess960", False))

    def _variation_root_label(self, index: int) -> str:
        if index < 0:
            return "Start"
        moves = getattr(self.current_game, "moves", None) or []
        if index >= len(moves):
            return "this position"
        move = moves[index]
        prefix = (
            f"{move.move_number}. " if move.ply % 2 == 1 else f"{move.move_number}… "
        )
        return prefix + move.san

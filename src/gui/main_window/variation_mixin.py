"""Variation-mode request handling for the main window."""

from src.utils.logger import logger


class VariationMixin:
    """Glue between the analysis panel's requests and the variation controller."""

    def _on_variation_requested(self, fen: str, uci: str) -> None:
        if not self.current_game:
            return
        if getattr(self, "_full_analysis_running", False):
            self._set_status("Finish the running analysis before exploring variations", "warning")
            return

        chess960 = bool(getattr(self.current_game.metadata, "chess960", False))
        started = self.variation.enter(
            fen,
            uci,
            return_index=self.board_widget.current_move_index,
            chess960=chess960,
        )
        if not started:
            logger.warning("Could not enter variation mode for FEN %s", fen)
            return

        # The shared live worker now belongs to the variation; a toggle would
        # silently move it back to the game position.
        self.analysis_panel.toggle_checkbox.setEnabled(False)
        self.analysis_panel.toggle_checkbox.setToolTip("Exit the variation to change engine lines")

    def _on_variation_exited(self, index: int) -> None:
        self.analysis_panel.toggle_checkbox.setEnabled(True)
        self.analysis_panel.toggle_checkbox.setToolTip("")
        # Silent: returning from a variation should not replay move sounds.
        self.on_move_selected(index, silent=True)

    def _on_variation_position_changed(self, fen: str) -> None:
        if hasattr(self, "captured_white") and hasattr(self, "captured_black"):
            self.captured_white.update_captured(fen)
            self.captured_black.update_captured(fen)

    def _exit_variation(self) -> None:
        """Tear the variation down without restoring (caller sets the board)."""
        variation = getattr(self, "variation", None)
        if variation is None or not variation.is_active:
            return
        variation.exit(notify=False)
        if hasattr(self, "analysis_panel"):
            self.analysis_panel.toggle_checkbox.setEnabled(True)
            self.analysis_panel.toggle_checkbox.setToolTip("")

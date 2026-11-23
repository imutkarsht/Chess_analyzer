# SPDX-License-Identifier: GPL-3.0-only
"""MainWindow adapter for the game-loading controller.

The workflow lives in ``src.gui.app.game_loading_controller``. This mixin keeps
the window surface and the QWidget drag/drop overrides as thin delegates.
"""

from __future__ import annotations

from src.gui.app.game_loading_controller import GameLoadingController


class GameLoadingMixin:
    """Thin window adapter around :class:`GameLoadingController`."""

    @property
    def game_loading_controller(self) -> GameLoadingController:
        controller = getattr(self, "_game_loading_controller", None)
        if controller is None:
            controller = GameLoadingController()
            controller.attach(self)
            self._game_loading_controller = controller
        return controller

    # ------------------------------------------------------------------
    # Lifecycle delegates
    # ------------------------------------------------------------------

    def load_game_from_history(self, game):
        self.game_loading_controller.load_game_from_history(game)

    def on_game_action_requested(self, game, action: str):
        self.game_loading_controller.on_game_action_requested(game, action)

    def load_game_from_metrics(self, game, move_index: int = -1):
        self.game_loading_controller.load_game_from_metrics(game, move_index)

    def load_game(self, game, from_history: bool = False):
        self.game_loading_controller.load_game(game, from_history)

    def open_load_dialog(self, initial_source: int = 0, initial_text: str = None):
        self.game_loading_controller.open_load_dialog(initial_source, initial_text)

    def paste_pgn_from_clipboard(self):
        self.game_loading_controller.paste_pgn_from_clipboard()

    def _update_analysis_view_mode(self, has_game: bool):
        self.game_loading_controller._update_analysis_view_mode(has_game)

    def _set_drop_highlight(self, active: bool):
        self.game_loading_controller._set_drop_highlight(active)

    def _on_imported_game_requested(self, pgn_text: str, source_data) -> None:
        self.game_loading_controller._on_imported_game_requested(pgn_text, source_data)

    # ------------------------------------------------------------------
    # QWidget drag/drop hooks (must stay on the window)
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event):
        self.game_loading_controller.handle_drag_enter(event)

    def dragLeaveEvent(self, event):
        self.game_loading_controller.handle_drag_leave(event)

    def dropEvent(self, event):
        self.game_loading_controller.handle_drop(event)

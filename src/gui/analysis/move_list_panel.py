"""
Move List Panel - game-domain wrapper around the shared move-list table.
"""

import contextlib

import chess
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from src.gui.analysis.line_utils import lines_for_index
from src.gui.analysis.move_list_view import MoveListEntry, MoveListView
from src.gui.engine_lines import LiveEngineSession
from src.gui.styles import Styles
from src.utils.logger import logger


class MoveListPanel(QWidget):
    move_selected = pyqtSignal(int)
    lines_updated = pyqtSignal(list, str)  # White-POV EngineLines, analysed FEN
    variation_requested = pyqtSignal(int)

    def __init__(self, engine_path="stockfish", config_manager=None):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.current_game = None

        # Live Analysis — one shared session owns the worker, the sequence
        # counter and the coalesced line updates. The worker is started
        # lazily on the first request, not at app launch.
        self.engine_path = engine_path
        self.session = LiveEngineSession(
            self.engine_path,
            config_manager=config_manager,
            parent=self,
            debounce_ms=1000,
        )
        self.session.lines_changed.connect(self._on_session_lines)

        self.engine_lines_enabled = (
            bool(config_manager.get("engine_lines_enabled", False))
            if config_manager is not None
            else False
        )
        self._analysed_fen: str | None = None
        self._variation_active = False
        self.is_chess960 = False
        self.starting_fen = chess.STARTING_FEN
        self._variation_counts: dict[int, int] = {}
        self._max_seconds = 30.0
        self._selected_index: int | None = None

        self.move_list = MoveListView(
            variant="analysis",
            forward_navigation_keys=True,
        )
        self.move_list.move_selected.connect(self.move_selected.emit)
        self.move_list.variation_requested.connect(self.variation_requested.emit)
        self.layout.addWidget(self.move_list)

        # Stable compatibility alias for tests and older call sites.
        self.table = self.move_list.table

        self.refresh_styles()

    @property
    def _move_widgets(self):
        return self.move_list.move_widgets

    @property
    def _think_bars(self):
        return self.move_list.think_bars

    def set_game(self, game_analysis):
        self.current_game = game_analysis
        self._variation_counts = {}
        self._selected_index = None
        self.is_chess960 = bool(getattr(game_analysis.metadata, "chess960", False))
        moves = game_analysis.moves or []
        self.starting_fen = (
            getattr(game_analysis.metadata, "starting_fen", None)
            or (moves[0].fen_before if moves else chess.STARTING_FEN)
        )
        self.move_list.set_current_index(-1)
        self.session.clear(emit=False)
        self.refresh()

    def clear(self) -> None:
        """Drop the loaded game and its live-engine session."""
        self.current_game = None
        self._variation_counts = {}
        self._selected_index = None
        self.session.clear(emit=False)
        self.move_list.clear_entries()

    def refresh(self):
        if not self.current_game:
            self.move_list.clear_entries()
            return

        try:
            num_rows = (len(self.current_game.moves) + 1) // 2
            if num_rows == 0:
                self.move_list.clear_entries()
                return

            # Calculate max_seconds based on TimeControl.
            tc = ""
            if hasattr(self.current_game, "metadata") and self.current_game.metadata:
                tc = getattr(
                    self.current_game.metadata, "time_control", None
                ) or self.current_game.metadata.headers.get("TimeControl", "")

            base_time = 0
            if tc and tc not in ("-", "?", ""):
                for period in tc.split(":"):
                    base_part = period.split("+")[0]
                    sec_part = base_part.split("/")[-1]
                    with contextlib.suppress(ValueError):
                        base_time += int(sec_part)

            max_seconds = 30.0
            if base_time > 0:
                max_seconds = max(10.0, min(600.0, base_time * 0.1))
            self._max_seconds = max_seconds

            entries = [
                MoveListEntry(
                    san=move.san,
                    classification=move.classification,
                    move_number=move.move_number,
                    time_spent=move.time_spent,
                    variation_count=self._variation_counts.get(index, 0),
                )
                for index, move in enumerate(self.current_game.moves)
            ]
            self.move_list.set_entries(entries, max_seconds=max_seconds)
            if self._selected_index is not None:
                self.move_list.set_current_index(self._selected_index)
        except Exception as e:
            logger.error(f"Error refreshing move list: {e}", exc_info=True)

    def update_move_cell(
        self, move_index: int, classification: str = None, eval_after_cp=None, eval_after_mate=None
    ):
        """Update a single move cell's classification and eval display during analysis."""
        if move_index < 0 or move_index >= len(self.current_game.moves):
            return
        move = self.current_game.moves[move_index]
        if classification is not None:
            move.classification = classification
        if eval_after_cp is not None:
            move.eval_after_cp = eval_after_cp
        if eval_after_mate is not None:
            move.eval_after_mate = eval_after_mate

        self.move_list.update_entry(
            move_index,
            classification=move.classification,
            time_spent=move.time_spent,
            variation_count=self._variation_counts.get(move_index, 0),
        )

    def _update_compact_mode(self) -> None:
        """Compatibility delegate for earlier tests/call sites."""
        self.move_list.update_compact_mode()

    def set_variation_counts(self, counts: dict[int, int]) -> None:
        """Attach branch badges to game positions that own saved variation trees."""
        self._variation_counts = {
            int(k): int(v) for k, v in counts.items() if v > 0
        }
        self.move_list.set_variation_counts(self._variation_counts)

    def refresh_styles(self):
        """Refresh styles for dynamic theme updates."""
        self.setStyleSheet(Styles.get_background_style())
        self.move_list.refresh_styles()

    def select_move(self, index):
        if not self.current_game:
            return

        if index < 0:
            self._selected_index = None
            self.move_list.set_current_index(-1)
            lines, lines_fen = self._lines_for_index(-1)
            self._analysed_fen = lines_fen
            self.lines_updated.emit(lines, lines_fen)
            self._request_live(lines_fen, terminal=False)
            return

        if index >= len(self.current_game.moves):
            return

        self._selected_index = index
        self.move_list.set_current_index(index)

        move = self.current_game.moves[index]
        lines, lines_fen = self._lines_for_index(index)
        self._analysed_fen = lines_fen

        # Checkmate ends the game: the other MultiPV entries are alternatives
        # to the mating move, not continuations after it.
        self.lines_updated.emit(lines, lines_fen)
        self._request_live(lines_fen, terminal=move.is_checkmate)

    def _request_live(self, fen: str, terminal: bool = False) -> None:
        """Ask the shared session for live lines, or cancel when disabled."""
        if self._variation_active or not self.engine_lines_enabled or terminal or not fen:
            self.session.clear(emit=False)
            return
        self.session.request(fen, chess960=self.is_chess960, emit_empty=False)

    def _lines_for_index(self, index: int) -> tuple[list, str]:
        """White-POV lines matching the position the board shows after ``index``."""
        return lines_for_index(
            self.current_game.moves, index, self.is_chess960
        )

    def _stop_live_analysis(self) -> None:
        """Cancel pending work and invalidate any in-flight results."""
        self.session.clear(emit=False)

    def begin_variation(self, fen: str, is_white: bool) -> None:
        """Analyse an arbitrary position while the board is in variation mode."""
        self._variation_active = True
        self._analysed_fen = fen
        self.lines_updated.emit([], fen)
        if self.engine_lines_enabled:
            self.session.request(fen, chess960=self.is_chess960, emit_empty=False)
        else:
            self.session.clear(emit=False)

    def end_variation(self) -> None:
        """Stop the variation analysis; the caller restores the game position."""
        self._variation_active = False
        self._analysed_fen = None
        self.session.clear(emit=False)

    def set_engine_lines_enabled(self, enabled):
        self.engine_lines_enabled = enabled
        if self._variation_active:
            self._apply_variation_lines()
            return
        if enabled:
            self.start_live_analysis()
            return

        self.session.clear(emit=False)
        if self.current_game and self.current_game.moves:
            index = self._selected_index if self._selected_index is not None else -1
            lines, lines_fen = self._lines_for_index(index)
            self._analysed_fen = lines_fen
            self.lines_updated.emit(lines, lines_fen)
            return
        self._analysed_fen = None
        self.lines_updated.emit([], "")

    def _apply_variation_lines(self) -> None:
        """Start or clear engine lines for the active variation position."""
        fen = self._analysed_fen
        self.session.clear(emit=False)
        if not fen:
            self.lines_updated.emit([], "")
            return
        if self.engine_lines_enabled:
            self.session.request(fen, chess960=self.is_chess960, emit_empty=False)
        else:
            self.lines_updated.emit([], fen)

    def start_live_analysis(self):
        if not self.current_game or self._variation_active or not self.engine_lines_enabled:
            return
        index = self._selected_index if self._selected_index is not None else -1
        if index >= len(self.current_game.moves):
            return
        if index >= 0 and self.current_game.moves[index].is_checkmate:
            self.session.clear(emit=False)
            return
        lines, lines_fen = self._lines_for_index(index)
        self._analysed_fen = lines_fen
        if lines_fen:
            self.session.request(lines_fen, chess960=self.is_chess960, emit_empty=False)

    def _on_session_lines(self, lines):
        """Publish lines for whichever position the session is analysing."""
        if not self.engine_lines_enabled:
            return
        self.lines_updated.emit(lines, self._analysed_fen or "")

    def closeEvent(self, event):
        self.session.shutdown()
        super().closeEvent(event)

    def update_engine_path(self, path):
        self.engine_path = path
        self.session.set_engine_path(path)

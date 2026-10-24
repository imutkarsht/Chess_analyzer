from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
)

from src.backend.analysis.navigation import find_critical_move
from src.backend.storage.pgn_parser import looks_like_pgn
from src.constants import (
    CRITICAL_CLASSIFICATIONS,
    DEFAULT_SHORTCUT_PRESET,
    PAGE_ANALYSIS,
    PAGE_EXPLORER,
    PAGE_NAMES,
    REPLAY_INTERVAL_MS,
)
from src.gui.dialogs import ShortcutHelpDialog
from src.gui.utils.shortcut_manager import ShortcutManager


def compute_clock_times(moves, index: int = -1) -> tuple[float | None, float | None]:
    """Calculate White and Black clock values at a given move index.

    Uses enumerate for linear lookup rather than moves.index(m).
    """
    has_clocks = any(m.time_left is not None for m in moves) if moves else False
    if not has_clocks:
        return None, None

    white_time = None
    black_time = None

    # Find the latest clock values at or before index
    if index >= 0:
        for i in range(index, -1, -1):
            if i % 2 == 0 and moves[i].time_left is not None:
                white_time = moves[i].time_left
                break
        for i in range(index, -1, -1):
            if i % 2 == 1 and moves[i].time_left is not None:
                black_time = moves[i].time_left
                break

    # Fall back to starting times if no move has been played yet on that side
    if white_time is None:
        for idx, m in enumerate(moves):
            if m.time_left is not None and idx % 2 == 0:
                white_time = m.time_left + (m.time_spent if m.time_spent is not None else 0.0)
                break
    if black_time is None:
        for idx, m in enumerate(moves):
            if m.time_left is not None and idx % 2 == 1:
                black_time = m.time_left + (m.time_spent if m.time_spent is not None else 0.0)
                break

    return white_time, black_time


class NavigationMixin:
    """Board move navigation, shortcuts, clipboard paste, and keyboard routing."""

    def _setup_shortcuts(self):
        sm = ShortcutManager(self)
        self.shortcut_manager = sm

        # File / analysis
        sm.register(
            "open_game",
            "Open / load game",
            "Ctrl+O",
            lambda: QTimer.singleShot(0, lambda: self.open_load_dialog(0)),
            category="File",
        )
        sm.register(
            "paste_game", "Paste PGN from clipboard", "Ctrl+V", self._handle_paste, category="File"
        )
        # Ctrl+A triggers analysis only when not typing inside a text field
        sm.register(
            "analyze", "Analyze game", "Ctrl+A", self._handle_analyze_shortcut, category="Analysis"
        )

        # Navigation
        sm.register(
            "nav_prev", "Previous move", ("Left", "K"), self._nav_prev, category="Navigation"
        )
        sm.register("nav_next", "Next move", ("Right", "J"), self._nav_next, category="Navigation")
        sm.register(
            "nav_first", "First move", ("Home", "Down"), self._nav_first, category="Navigation"
        )
        sm.register("nav_last", "Last move", ("End", "Up"), self._nav_last, category="Navigation")
        sm.register(
            "nav_next_critical",
            "Next mistake / blunder / miss",
            ("N", "Shift+Right"),
            lambda: self._nav_critical(1),
            category="Navigation",
        )
        sm.register(
            "nav_prev_critical",
            "Previous mistake / blunder / miss",
            ("P", "Shift+Left"),
            lambda: self._nav_critical(-1),
            category="Navigation",
        )

        # Board
        sm.register("flip_board", "Flip board", "F", self._handle_flip_shortcut, category="Board")
        sm.register(
            "toggle_replay",
            "Play / pause auto-replay",
            "Space",
            self._toggle_replay,
            category="Board",
        )

        # Variation mode
        sm.register(
            "prev_branch",
            "Previous sibling branch",
            "Alt+Up",
            lambda: self._cycle_variation_branch(-1),
            category="Variations",
        )
        sm.register(
            "next_branch",
            "Next sibling branch",
            "Alt+Down",
            lambda: self._cycle_variation_branch(1),
            category="Variations",
        )
        sm.register(
            "escape",
            "Exit variation / leave Explorer",
            "Escape",
            self._on_escape,
            category="Variations",
        )

        # Pages
        for index, name in enumerate(PAGE_NAMES):
            sm.register(
                f"page_{name.lower()}",
                f"Go to {name}",
                str(index + 1),
                lambda i=index: self._go_to_page(i),
                category="Pages",
            )

        # Help
        sm.register("start_tour", "Start page tour", "Ctrl+T", self.start_tour, category="Help")

        self._replay_timer = QTimer(self)
        self._replay_timer.setInterval(REPLAY_INTERVAL_MS)
        self._replay_timer.timeout.connect(self._replay_tick)

        shortcut_card = self.settings_view.shortcut_settings
        sm.bindings_changed.connect(lambda: shortcut_card.set_bindings(sm.get_bindings()))
        shortcut_card.preset_changed.connect(sm.apply_preset)
        sm.apply_preset(self.config_manager.get("shortcut_preset", DEFAULT_SHORTCUT_PRESET))

    def _go_to_page(self, index: int):
        self.sidebar.set_active(index)
        self.switch_page(index)

    def _variation_active(self) -> bool:
        variation = getattr(self, "variation", None)
        return variation is not None and variation.is_active

    def _nav_critical(self, step: int):
        """Jump to the nearest mistake/blunder/miss in the given direction (1 or -1)."""
        if self.stack.currentIndex() == PAGE_EXPLORER or not self.current_game:
            return
        moves = self.current_game.moves
        if not any(m.classification for m in moves):
            self._set_status("Analyze the game first to jump between mistakes", "warning")
            return
        idx = find_critical_move(
            moves, self.board_widget.current_move_index, step, CRITICAL_CLASSIFICATIONS
        )
        if idx is None:
            direction = "after" if step > 0 else "before"
            self._set_status(f"No mistakes, blunders or misses {direction} this move", "info")
            return
        self.on_move_selected(idx)

    def _toggle_replay(self):
        """Space: start/stop stepping through the main line every REPLAY_INTERVAL_MS."""
        if self._replay_timer.isActive():
            self._stop_replay()
            return

        game = self.current_game
        if self.stack.currentIndex() != PAGE_ANALYSIS or not game or not game.moves:
            # Nothing to replay: give Space back to a focused button/combo,
            # since the window-level shortcut swallows it before they see it.
            focus_widget = QApplication.focusWidget()
            if isinstance(focus_widget, QAbstractButton):
                focus_widget.animateClick()
            elif isinstance(focus_widget, QComboBox):
                focus_widget.showPopup()
            return
        if self._variation_active():
            self._set_status("Exit the variation (Esc) to replay the game", "info")
            return

        # Restart from the beginning when the game is already at its last move.
        if self.board_widget.current_move_index >= len(game.moves) - 1:
            self.on_move_selected(-1)
        self._replay_timer.start()
        self._set_status("Auto-replay started (Space to pause)", "info")

    def _stop_replay(self):
        if self._replay_timer.isActive():
            self._replay_timer.stop()
            self._set_status("Auto-replay paused", "info")

    def _replay_tick(self):
        game = self.current_game
        if (
            self.stack.currentIndex() != PAGE_ANALYSIS
            or not game
            or self._variation_active()
            or self.board_widget.current_move_index >= len(game.moves) - 1
        ):
            self._stop_replay()
            return
        self._nav_next()

    @staticmethod
    def _editing_text() -> bool:
        return isinstance(QApplication.focusWidget(), (QLineEdit, QTextEdit, QPlainTextEdit))

    def _cycle_variation_branch(self, direction: int) -> None:
        if self._editing_text():
            return
        variation = getattr(self, "variation", None)
        if variation is not None and variation.is_active:
            variation.cycle_sibling(direction)

    def _on_escape(self):
        """Esc leaves a variation, or the Explorer page; otherwise it is ignored."""
        variation = getattr(self, "variation", None)
        if variation is not None and variation.is_active:
            variation.exit()
            return
        if getattr(self, "stack", None) is not None and self.stack.currentIndex() == PAGE_EXPLORER:
            # The Explorer page is reached via "Explore from here"; Esc returns.
            self._go_to_page(PAGE_ANALYSIS)

    def _handle_analyze_shortcut(self):
        """Handle Ctrl+A shortcut without hijacking select-all in editable fields."""
        focus_widget = QApplication.focusWidget()
        if isinstance(focus_widget, (QLineEdit, QTextEdit, QPlainTextEdit)):
            focus_widget.selectAll()
            return
        self.start_analysis()

    def _handle_flip_shortcut(self):
        if self._editing_text():
            return
        if getattr(self, "stack", None) is not None and self.stack.currentIndex() == 1:
            self.explorer_view._flip_board()
            return
        self.flip_board()

    def _handle_paste(self):
        focus_widget = QApplication.focusWidget()
        if isinstance(focus_widget, (QLineEdit, QTextEdit, QPlainTextEdit)):
            focus_widget.paste()
            return

        text = QApplication.clipboard().text().strip()
        if looks_like_pgn(text):
            QTimer.singleShot(0, lambda: self.open_load_dialog(initial_source=1, initial_text=text))

    def _nav_prev(self):
        variation = getattr(self, "variation", None)
        if variation is not None and variation.is_active:
            variation.undo()
            return

        if self.stack.currentIndex() == 1:
            self.explorer_view.move_list_widget.nav_prev.emit()
            return

        if not self.current_game:
            return
        idx = max(-1, self.board_widget.current_move_index - 1)
        if idx != self.board_widget.current_move_index:
            self.on_move_selected(idx)

    def _nav_next(self):
        variation = getattr(self, "variation", None)
        if variation is not None and variation.is_active:
            variation.forward()
            return

        if self.stack.currentIndex() == 1:
            self.explorer_view.move_list_widget.nav_next.emit()
            return

        if not self.current_game:
            return
        idx = min(len(self.current_game.moves) - 1, self.board_widget.current_move_index + 1)
        if idx != self.board_widget.current_move_index:
            self.on_move_selected(idx)

    def _nav_last(self):
        variation = getattr(self, "variation", None)
        if variation is not None and variation.is_active:
            variation.go_to_end()
            return

        if self.stack.currentIndex() == 1:
            self.explorer_view.move_list_widget.nav_last.emit()
            return

        if not self.current_game:
            return
        idx = len(self.current_game.moves) - 1
        if idx != self.board_widget.current_move_index:
            self.on_move_selected(idx)

    def _nav_first(self):
        variation = getattr(self, "variation", None)
        if variation is not None and variation.is_active:
            variation.go_to_start()
            return

        if self.stack.currentIndex() == 1:
            self.explorer_view.move_list_widget.nav_first.emit()
            return

        if not self.current_game:
            return
        if self.board_widget.current_move_index != -1:
            self.on_move_selected(-1)

    def go_first(self):
        variation = getattr(self, "variation", None)
        if variation is not None and variation.is_active:
            variation.go_to_start()
            return
        if self.current_game:
            self.on_move_selected(-1)

    def go_prev(self):
        variation = getattr(self, "variation", None)
        if variation is not None and variation.is_active:
            variation.undo()
            return
        if self.current_game:
            current = self.board_widget.current_move_index
            new_index = max(-1, current - 1)
            self.on_move_selected(new_index)

    def go_next(self):
        variation = getattr(self, "variation", None)
        if variation is not None and variation.is_active:
            variation.forward()
            return
        if self.current_game:
            current = self.board_widget.current_move_index
            total = len(self.current_game.moves)
            new_index = min(total - 1, current + 1)
            self.on_move_selected(new_index)

    def go_last(self):
        variation = getattr(self, "variation", None)
        if variation is not None and variation.is_active:
            variation.go_to_end()
            return
        if self.current_game:
            total = len(self.current_game.moves)
            self.on_move_selected(total - 1)

    def flip_board(self):
        self.board_widget.flip_board()
        self._position_captured_pieces()

    def _position_captured_pieces(self):
        """Keep one captured-pieces card on each side of the board."""
        self.board_panel.set_flipped(self.board_widget.is_flipped)

    def _sync_board_chrome_widths(self, side: int) -> None:
        """Keep the matchup header and controls anchored to the board width."""
        if side <= 0:
            return
        if hasattr(self, "board_game_header"):
            self.board_game_header.setFixedWidth(side)
        if hasattr(self, "controls"):
            self.controls.setFixedWidth(side)

    def on_move_selected(self, index, silent: bool = False):
        # Any game navigation abandons an open variation first.
        self._exit_variation()

        self.board_widget.set_position(index)
        self.move_list_panel.select_move(index)
        self.move_changed.emit(index)

        if hasattr(self, "analysis_panel") and hasattr(self.analysis_panel, "graph_widget"):
            self.analysis_panel.graph_widget.set_current_move(index)

        if hasattr(self, "analysis_panel"):
            # Coach tab: deterministic facts for the newly selected move (no network).
            self.analysis_panel.set_selected_move(index)

        if self.current_game:
            moves = self.current_game.moves
            fen = None
            if index == -1:
                fen = None
            elif 0 <= index < len(moves):
                if index + 1 < len(moves):
                    fen = moves[index + 1].fen_before
                else:
                    if hasattr(self.board_widget, "board"):
                        fen = self.board_widget.board.fen()

            self.captured_white.update_captured(fen)
            self.captured_black.update_captured(fen)

            white_time, black_time = compute_clock_times(moves, index)
            self.captured_white.update_clock(white_time)
            self.captured_black.update_clock(black_time)

            if 0 <= index < len(moves) and not silent:
                move = moves[index]
                san = move.san
                if "#" in san or "mate" in san.lower():
                    self.resource_manager.play_sound("game_end")
                elif "+" in san:
                    self.resource_manager.play_sound("check")
                elif "x" in san:
                    self.resource_manager.play_sound("capture")
                elif "O-O" in san:
                    self.resource_manager.play_sound("castle")
                else:
                    self.resource_manager.play_sound("move")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F1 or (event.key() == Qt.Key.Key_Question):
            self.show_shortcuts_help()
            return

        if (
            event.key() == Qt.Key.Key_Slash
            and event.modifiers() == Qt.KeyboardModifier.ShiftModifier
        ):
            self.show_shortcuts_help()
            return

        super().keyPressEvent(event)

    def show_shortcuts_help(self):
        """Show the keyboard shortcuts help dialog."""
        dialog = ShortcutHelpDialog(self)
        dialog.exec()

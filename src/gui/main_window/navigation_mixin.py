from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication, QLineEdit, QPlainTextEdit, QTextEdit

from src.gui.dialogs import ShortcutHelpDialog


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
        # File Operations
        self.shortcut_open = QShortcut(QKeySequence("Ctrl+O"), self)
        self.shortcut_open.activated.connect(
            lambda: QTimer.singleShot(0, lambda: self.open_load_dialog(0))
        )

        self.shortcut_paste = QShortcut(QKeySequence("Ctrl+V"), self)
        self.shortcut_paste.activated.connect(self._handle_paste)

        # Ctrl+A triggers analysis only when not typing inside a text field
        self.shortcut_analyze = QShortcut(QKeySequence("Ctrl+A"), self)
        self.shortcut_analyze.activated.connect(self._handle_analyze_shortcut)

        # Navigation
        self.shortcut_left = QShortcut(QKeySequence("Left"), self)
        self.shortcut_left.activated.connect(self._nav_prev)

        self.shortcut_right = QShortcut(QKeySequence("Right"), self)
        self.shortcut_right.activated.connect(self._nav_next)

        self.shortcut_up = QShortcut(QKeySequence("Up"), self)
        self.shortcut_up.activated.connect(self._nav_last)

        self.shortcut_end = QShortcut(QKeySequence("End"), self)
        self.shortcut_end.activated.connect(self._nav_last)

        self.shortcut_down = QShortcut(QKeySequence("Down"), self)
        self.shortcut_down.activated.connect(self._nav_first)

        self.shortcut_home = QShortcut(QKeySequence("Home"), self)
        self.shortcut_home.activated.connect(self._nav_first)

        # Tour
        self.shortcut_tour = QShortcut(QKeySequence("Ctrl+T"), self)
        self.shortcut_tour.activated.connect(self.start_tour)

        self.shortcut_flip = QShortcut(QKeySequence("F"), self)
        self.shortcut_flip.activated.connect(self._handle_flip_shortcut)
        app = QApplication.instance()
        if app is not None:
            app.focusChanged.connect(self._update_flip_shortcut_state)
            self._update_flip_shortcut_state(None, QApplication.focusWidget())

        # Variation mode
        self.shortcut_exit_variation = QShortcut(QKeySequence("Escape"), self)
        self.shortcut_exit_variation.activated.connect(self._on_escape)

        self.shortcut_prev_branch = QShortcut(QKeySequence("Alt+Up"), self)
        self.shortcut_prev_branch.activated.connect(lambda: self._cycle_variation_branch(-1))
        self.shortcut_next_branch = QShortcut(QKeySequence("Alt+Down"), self)
        self.shortcut_next_branch.activated.connect(lambda: self._cycle_variation_branch(1))

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
        if getattr(self, "stack", None) is not None and self.stack.currentIndex() == 1:
            # The Explorer page is reached via "Explore from here"; Esc returns.
            self.sidebar.set_active(0)
            self.switch_page(0)

    def _handle_analyze_shortcut(self):
        """Handle Ctrl+A shortcut without hijacking select-all in editable fields."""
        focus_widget = QApplication.focusWidget()
        if isinstance(focus_widget, (QLineEdit, QTextEdit, QPlainTextEdit)):
            focus_widget.selectAll()
            return
        self.start_analysis()

    def _update_flip_shortcut_state(self, _old, new) -> None:
        """Disable plain-letter F while a text field has focus."""
        if hasattr(self, "shortcut_flip"):
            self.shortcut_flip.setEnabled(
                not isinstance(new, (QLineEdit, QTextEdit, QPlainTextEdit))
            )

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
        if text and ("[Event" in text or "1." in text):
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

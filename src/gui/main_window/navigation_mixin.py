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

    def _handle_analyze_shortcut(self):
        """Handle Ctrl+A shortcut without hijacking select-all in editable fields."""
        focus_widget = QApplication.focusWidget()
        if isinstance(focus_widget, (QLineEdit, QTextEdit, QPlainTextEdit)):
            focus_widget.selectAll()
            return
        self.start_analysis()

    def _handle_paste(self):
        focus_widget = QApplication.focusWidget()
        if isinstance(focus_widget, (QLineEdit, QTextEdit, QPlainTextEdit)):
            focus_widget.paste()
            return

        text = QApplication.clipboard().text().strip()
        if text and ("[Event" in text or "1." in text):
            QTimer.singleShot(0, lambda: self.open_load_dialog(initial_source=1, initial_text=text))

    def _nav_prev(self):
        if self.stack.currentIndex() == 1:
            self.explorer_view.move_list_widget.nav_prev.emit()
            return

        if not self.current_game:
            return
        idx = max(-1, self.board_widget.current_move_index - 1)
        if idx != self.board_widget.current_move_index:
            self.on_move_selected(idx)

    def _nav_next(self):
        if self.stack.currentIndex() == 1:
            self.explorer_view.move_list_widget.nav_next.emit()
            return

        if not self.current_game:
            return
        idx = min(len(self.current_game.moves) - 1, self.board_widget.current_move_index + 1)
        if idx != self.board_widget.current_move_index:
            self.on_move_selected(idx)

    def _nav_last(self):
        if self.stack.currentIndex() == 1:
            self.explorer_view.move_list_widget.nav_last.emit()
            return

        if not self.current_game:
            return
        idx = len(self.current_game.moves) - 1
        if idx != self.board_widget.current_move_index:
            self.on_move_selected(idx)

    def _nav_first(self):
        if self.stack.currentIndex() == 1:
            self.explorer_view.move_list_widget.nav_first.emit()
            return

        if not self.current_game:
            return
        if self.board_widget.current_move_index != -1:
            self.on_move_selected(-1)

    def go_first(self):
        if self.current_game:
            self.on_move_selected(-1)

    def go_prev(self):
        if self.current_game:
            current = self.board_widget.current_move_index
            new_index = max(-1, current - 1)
            self.on_move_selected(new_index)

    def go_next(self):
        if self.current_game:
            current = self.board_widget.current_move_index
            total = len(self.current_game.moves)
            new_index = min(total - 1, current + 1)
            self.on_move_selected(new_index)

    def go_last(self):
        if self.current_game:
            total = len(self.current_game.moves)
            self.on_move_selected(total - 1)

    def flip_board(self):
        self.board_widget.flip_board()
        self.center_layout.removeWidget(self.captured_white)
        self.center_layout.removeWidget(self.captured_black)
        if self.board_widget.is_flipped:
            self.center_layout.insertWidget(1, self.captured_white)
            self.center_layout.insertWidget(3, self.captured_black)
        else:
            self.center_layout.insertWidget(1, self.captured_black)
            self.center_layout.insertWidget(3, self.captured_white)

    def on_move_selected(self, index):
        self.board_widget.set_position(index)
        self.move_list_panel.select_move(index)

        if hasattr(self, "analysis_panel") and hasattr(self.analysis_panel, "graph_widget"):
            self.analysis_panel.graph_widget.set_current_move(index)

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

            if 0 <= index < len(moves):
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

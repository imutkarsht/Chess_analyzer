"""
Shared GUI utility functions and widget factories.
"""
import os
from typing import Callable, Optional, List
from PyQt6.QtWidgets import (QLayout, QPushButton, QComboBox, QLineEdit,
                             QLabel, QWidget, QHBoxLayout, QVBoxLayout)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPainter, QColor, QBrush, QLinearGradient, QIcon
from ..utils.path_utils import get_resource_path


class ThinkTimeBar(QWidget):
    """
    Horizontal bar visualising the time a side spent thinking on a move.

    Colour goes from green (fast, ≤5 s) through yellow (10–20 s) to red
    (very long, ≥30 s). The bar is rendered to a percentage of the
    configurable max_seconds; if the value is missing the widget shows
    an empty grey bar with no text.
    """

    def __init__(self, max_seconds: float = 30.0, parent: QWidget = None):
        super().__init__(parent)
        self._value: Optional[float] = None
        self._max = max(1.0, float(max_seconds))
        self.setMinimumWidth(50)
        self.setMinimumHeight(18)

    def set_value(self, seconds: Optional[float]) -> None:
        self._value = seconds
        self._update_tooltip()
        self.update()

    def _update_tooltip(self) -> None:
        if self._value is None:
            self.setToolTip("No clock data")
        else:
            self.setToolTip(f"Think time: {self._value:.1f}s")

    def _colour_for(self, ratio: float) -> QColor:
        """ratio ∈ [0, 1] → colour along green→yellow→red gradient."""
        ratio = max(0.0, min(1.0, ratio))
        # 0.0 → green, 0.5 → yellow, 1.0 → red
        if ratio < 0.5:
            t = ratio / 0.5
            r = int(76 + (255 - 76) * t)   # 76 → 255
            g = int(175 + (193 - 175) * t)  # 175 → 193
            b = int(80 + 7 * t)             # 80 → 7
            return QColor(r, g, b)
        else:
            t = (ratio - 0.5) / 0.5
            r = int(255 + (231 - 255) * t)  # 255 → 231
            g = int(193 + (76 - 193) * t)   # 193 → 76
            b = int(7 + (60 - 7) * t)       # 7 → 60
            return QColor(r, g, b)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()

        # Background (empty track)
        p.setBrush(QBrush(QColor(60, 60, 60)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect.adjusted(2, 4, -2, -4), 4, 4)

        if self._value is None:
            p.end()
            return

        ratio = min(1.0, self._value / self._max)
        fill_width = int(rect.width() * ratio) - 4
        if fill_width < 1:
            p.end()
            return

        colour = self._colour_for(ratio)
        # Gradient for a softer look
        gradient = QLinearGradient(0, 0, fill_width, 0)
        gradient.setColorAt(0.0, colour.darker(110))
        gradient.setColorAt(1.0, colour)
        p.setBrush(QBrush(gradient))
        p.drawRoundedRect(rect.adjusted(2, 4, -2, -4), 4, 4)

        # Numeric label inside (or beside) the bar
        p.setPen(QColor(255, 255, 255))
        font = p.font()
        font.setPointSize(9)
        font.setBold(True)
        p.setFont(font)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{self._value:.1f}s")
        p.end()


class MoveCellWidget(QWidget):
    """
    Compact move cell that packs the classification icon, the SAN, an
    optional think-time label, and a thin coloured think-time bar in a
    single column. This keeps the move list at 3 columns (#, White, Black)
    while still surfacing the clock information visually.

    The widget emits ``clicked`` when the user clicks anywhere in it, so
    a single ``setCellWidget`` replacement keeps the existing
    cellClicked-style handlers working.
    """

    from PyQt6.QtCore import pyqtSignal as _pyqtSignal
    clicked = _pyqtSignal(int)  # carries the move index

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        # Main horizontal layout: [icon] [SAN + bar]  [think-time label]
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 2, 4, 2)
        outer.setSpacing(0)

        # Top row: icon + SAN + time label
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(4)

        self._icon_label = QLabel(self)
        self._icon_label.setFixedSize(20, 20)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self._san_label = QLabel(self)
        self._san_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        font = self._san_label.font()
        font.setPointSize(13)
        self._san_label.setFont(font)
        top_row.addWidget(self._san_label, 1, Qt.AlignmentFlag.AlignVCenter)

        self._time_label = QLabel(self)
        self._time_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
        )
        self._time_label.setStyleSheet(
            "color: rgba(255,255,255,140); font-size: 10px;"
        )
        top_row.addWidget(self._time_label, 0, Qt.AlignmentFlag.AlignVCenter)

        outer.addLayout(top_row)

        # Bottom row: a 3-pixel-tall coloured think-time bar (full width).
        # We use a plain QLabel with a stylesheet background so we don't
        # need a second custom widget for such a simple thing.
        self._bar = QLabel(self)
        self._bar.setFixedHeight(3)
        self._bar.setStyleSheet("background: rgba(255,255,255,20); border: none;")
        outer.addWidget(self._bar)

        # Track the move index so clicks can re-emit it.
        self._move_index: int = -1
        self._san_text: str = ""
        self._classification_color: str = ""
        self._classification_name: str = ""

        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ----- public API -------------------------------------------------
    def set_move(self, move, move_index: int, icon: QIcon = None,
                 san_color: str = "") -> None:
        self._move_index = move_index
        self._san_text = move.san
        self._san_label.setText(move.san)
        self._classification_name = move.classification or ""
        self._classification_color = san_color

        if san_color:
            self._san_label.setStyleSheet(
                f"color: {san_color}; font-size: 13px; background: transparent;"
            )
        else:
            self._san_label.setStyleSheet(
                "color: white; font-size: 13px; background: transparent;"
            )

        if move.classification in ("Brilliant", "Blunder", "Mistake", "Miss"):
            f = self._san_label.font()
            f.setBold(True)
            self._san_label.setFont(f)
        else:
            f = self._san_label.font()
            f.setBold(False)
            self._san_label.setFont(f)

        if icon is not None and not icon.isNull():
            self._icon_label.setPixmap(icon.pixmap(20, 20))
        else:
            self._icon_label.clear()

        # Think-time text + bar
        if move.time_spent is not None:
            self._time_label.setText(f"{move.time_spent:.1f}s")
            ratio = min(1.0, move.time_spent / 30.0)
            colour = self._bar_colour(ratio)
            # Render as left-to-right fill: 100% of the cell width for the
            # coloured portion, plus a faded track for the remainder.
            self._bar.setStyleSheet(
                f"""
                QLabel {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 {colour},
                        stop:{ratio:.4f} {colour},
                        stop:{ratio:.4f} rgba(255,255,255,18),
                        stop:1 rgba(255,255,255,18)
                    );
                    border: none;
                }}
                """
            )
            self.setToolTip(
                f"{move.classification + ': ' if move.classification else ''}"
                f"{move.san}  —  Think time: {move.time_spent:.1f}s"
            )
        else:
            self._time_label.setText("")
            self._bar.setStyleSheet("background: rgba(255,255,255,12); border: none;")
            self.setToolTip(
                f"{move.classification + ': ' if move.classification else ''}"
                f"{move.san}"
            )

    # ----- helpers ----------------------------------------------------
    def _bar_colour(self, ratio: float) -> str:
        ratio = max(0.0, min(1.0, ratio))
        if ratio < 0.5:
            t = ratio / 0.5
            r = int(76 + (255 - 76) * t)
            g = int(175 + (193 - 175) * t)
            b = int(80 + 7 * t)
        else:
            t = (ratio - 0.5) / 0.5
            r = int(255 + (231 - 255) * t)
            g = int(193 + (76 - 193) * t)
            b = int(7 + (60 - 7) * t)
        return f"rgb({r},{g},{b})"

    # ----- mouse handling so a click on the cell still selects the move
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._move_index)
            event.accept()
            return
        super().mousePressEvent(event)



def clear_layout(layout: QLayout) -> None:
    """
    Removes all widgets and sub-layouts from a QLayout.
    
    Args:
        layout: The QLayout to clear
    """
    if layout is None:
        return
        
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()
        elif item.layout():
            clear_layout(item.layout())


def resolve_asset(filename: str) -> str:
    """
    Robustly find assets using the project's standard resource resolver.
    
    Args:
        filename: Asset filename (with or without extension)
        
    Returns:
        Absolute path to asset, or None if not found
    """
    candidates = [
        os.path.join("assets", "images", filename),
        os.path.join("assets", "icons", filename),
        os.path.join("assets", filename)
    ]
    
    for rel_path in candidates:
        full_path = get_resource_path(rel_path)
        if os.path.exists(full_path):
            return full_path
    return None


def get_user_color(game: dict, usernames: list) -> str:
    """
    Determines the user's color in a game based on configured usernames.
    
    Args:
        game: Game dictionary with 'white' and 'black' keys
        usernames: List of usernames to check against
        
    Returns:
        'white' or 'black' depending on which player matches usernames
    """
    white = game.get('white', '').lower()
    if white in [u.lower() for u in usernames]:
        return 'white'
    return 'black'


# ============== Widget Factory Functions ==============

def create_button(
    text: str, 
    style: str = "primary",
    on_click: Optional[Callable] = None,
    cursor: bool = True
) -> QPushButton:
    """
    Factory function to create styled buttons.
    
    Args:
        text: Button text
        style: Style type - "primary", "secondary", "export", "import"
        on_click: Click handler callback
        cursor: Whether to show pointer cursor on hover
        
    Returns:
        Configured QPushButton
    """
    from .styles import Styles  # Import here to avoid circular imports
    
    btn = QPushButton(text)
    
    style_map = {
        "primary": Styles.get_button_style,
        "secondary": Styles.get_control_button_style,
        "export": Styles.get_export_button_style,
        "import": Styles.get_import_button_style,
    }
    
    style_func = style_map.get(style, Styles.get_button_style)
    btn.setStyleSheet(style_func())
    
    if cursor:
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
    
    if on_click:
        btn.clicked.connect(on_click)
    
    return btn


def create_combobox(
    items: List[str],
    current: Optional[str] = None,
    on_change: Optional[Callable] = None
) -> QComboBox:
    """
    Factory function to create styled comboboxes.
    
    Args:
        items: List of items to add
        current: Currently selected item
        on_change: Callback for selection changes
        
    Returns:
        Configured QComboBox
    """
    from .styles import Styles
    
    combo = QComboBox()
    combo.addItems(items)
    combo.setStyleSheet(Styles.get_combobox_style())
    
    if current:
        combo.setCurrentText(current)
    
    if on_change:
        combo.currentTextChanged.connect(on_change)
    
    return combo


def create_labeled_input(
    label_text: str,
    placeholder: str = "",
    password: bool = False,
    initial_value: str = ""
) -> tuple:
    """
    Factory function to create a labeled input field.
    
    Args:
        label_text: Text for the label
        placeholder: Placeholder text for input
        password: Whether to mask input
        initial_value: Initial value for the input
        
    Returns:
        Tuple of (QLabel, QLineEdit)
    """
    from .styles import Styles
    
    label = QLabel(label_text)
    label.setStyleSheet(Styles.get_secondary_label_style())
    
    input_field = QLineEdit()
    input_field.setStyleSheet(Styles.get_input_style())
    input_field.setPlaceholderText(placeholder)
    
    if password:
        input_field.setEchoMode(QLineEdit.EchoMode.Password)
    
    if initial_value:
        input_field.setText(initial_value)
    
    return label, input_field


def create_section_header(
    title: str,
    action_button: Optional[tuple] = None
) -> QWidget:
    """
    Factory function to create a section header with optional action button.
    
    Args:
        title: Header title text
        action_button: Optional tuple of (button_text, callback, style)
        
    Returns:
        QWidget containing the header layout
    """
    from .styles import Styles
    
    header = QWidget()
    layout = QHBoxLayout(header)
    layout.setContentsMargins(0, 0, 0, 0)
    
    title_label = QLabel(title)
    title_label.setStyleSheet(Styles.get_label_style(size=18, bold=True))
    layout.addWidget(title_label)
    
    layout.addStretch()
    
    if action_button:
        btn_text, callback, btn_style = action_button
        btn = create_button(btn_text, style=btn_style or "secondary", on_click=callback)
        layout.addWidget(btn)

    return header


def show_error_dialog(parent, title: str, message: str, details: str = "") -> None:
    """
    Show a modal error dialog with selectable/copyable text.

    The full error message goes into the "Show Details" section so users
    can copy it for bug reports. The visible message stays short.

    Defensive: if the parent widget has already been destroyed (e.g. the
    caller was a thread that outlived its view), this falls back to a
    top-level dialog and never raises.
    """
    from PyQt6.QtWidgets import QMessageBox
    from PyQt6.QtCore import Qt

    # Drop a dead parent rather than letting QMessageBox crash on it.
    try:
        from PyQt6.QtCore import QObject
        if parent is not None and not isinstance(parent, QObject):
            parent = None
    except Exception:
        pass

    try:
        box = QMessageBox(parent)
    except Exception:
        # Parent is in an unusable state — fall back to a top-level box.
        box = QMessageBox()

    try:
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(title)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(message)

        if details:
            box.setDetailedText(details)

        # Allow copying the visible message as well.
        # Note: QMessageBox.textLabel() exists in PyQt5 / PySide but NOT in
        # PyQt6 — find the label widget in the layout instead.
        try:
            from PyQt6.QtWidgets import QLabel
            for label in box.findChildren(QLabel):
                label.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                    | Qt.TextInteractionFlag.TextSelectableByKeyboard
                )
        except Exception:
            pass

        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()
    except Exception:
        # Last-resort: don't let a dialog failure propagate into the
        # caller (which may be a worker thread).
        import traceback
        from ..utils.logger import logger
        logger.error("show_error_dialog failed: %s", traceback.format_exc())


def is_error_message(text: str) -> bool:
    """True if a worker returned a backend error string (prefixed with 'Error')."""
    return bool(text) and text.lstrip().startswith("Error")


def format_clock_duration(seconds: float) -> str:
    """Format a clock duration in a compact human-readable form, e.g. 0:09:56."""
    if seconds is None:
        return "-"
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - h * 3600 - m * 60
    if h > 0:
        return f"{h}:{m:02d}:{s:04.1f}"
    return f"{m}:{s:04.1f}"


def format_time_stats_for_llm(moves) -> str:
    """
    Build a compact, LLM-friendly summary of the move clocks.

    Format:
        Avg think time  — White: 7.4s, Black: 12.2s
        Longest thinks  — 22.a6 (White, 133.2s), 8.e3 (Black, 21.0s)
        Fastest blunders — 22.a6 (White, 1.0s, eval -12), …
        Final clock     — White: 6:46.9, Black: 4:25.7

    Note on ply: chess.Board.ply() returns the number of half-moves ALREADY
    made, BEFORE the move being recorded is pushed. So an even ply means
    it's White's turn (this is the next move White will play); an odd ply
    means it's Black's turn. The MoveAnalysis records ply before push, so:
        even ply  = this is a White move
        odd  ply  = this is a Black move
    """
    if not moves:
        return ""

    def is_white(m) -> bool:
        return m.ply % 2 == 0

    whites = [m for m in moves if is_white(m) and m.time_spent is not None]
    blacks = [m for m in moves if not is_white(m) and m.time_spent is not None]

    def avg(lst):
        return (sum(m.time_spent for m in lst) / len(lst)) if lst else 0.0

    def fmt_move(m) -> str:
        side = "W" if is_white(m) else "B"
        sep = "." if is_white(m) else "..."
        return f"{m.move_number}{sep} {m.san} ({side}, {m.time_spent:.1f}s)"

    lines = [f"Avg think time — White: {avg(whites):.1f}s, Black: {avg(blacks):.1f}s"]

    by_spent = sorted(
        [m for m in moves if m.time_spent is not None],
        key=lambda m: m.time_spent, reverse=True,
    )
    if by_spent:
        top = ", ".join(fmt_move(m) for m in by_spent[:5])
        lines.append(f"Longest thinks — {top}")

    # Fast moves that swung the eval a lot — heuristic for time-trouble blunders
    quick_swings = []
    for m in moves:
        if m.time_spent is None or m.time_spent > 5.0:
            continue
        e_before = m.eval_before_cp
        e_after = m.eval_after_cp
        if e_before is None or e_after is None:
            continue
        if abs(e_after - e_before) < 150:   # < 1.5 pawns
            continue
        side = "W" if is_white(m) else "B"
        sep = "." if is_white(m) else "..."
        quick_swings.append(
            f"{m.move_number}{sep} {m.san} ({side}, {m.time_spent:.1f}s, "
            f"swing {(m.eval_after_cp - m.eval_before_cp)/100:+.1f})"
        )
    if quick_swings:
        lines.append(f"Fastest large eval swings — {', '.join(quick_swings[:3])}")

    def last_time(is_white_side: bool):
        want = 0 if is_white_side else 1
        for m in reversed(moves):
            if (m.ply % 2) == want and m.time_left is not None:
                return m.time_left
        return None

    lines.append(
        "Final clock — "
        f"White: {format_clock_duration(last_time(True))}, "
        f"Black: {format_clock_duration(last_time(False))}"
    )

    return "\n".join(lines)

"""
Shared GUI utility functions and widget factories.
"""
import os
from typing import Callable, Optional, List
from PyQt6.QtWidgets import (QLayout, QPushButton, QComboBox, QLineEdit,
                             QLabel, QWidget, QHBoxLayout, QVBoxLayout)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPainter, QColor, QBrush, QLinearGradient, QIcon
from src.utils.path_utils import get_resource_path



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
    cursor: bool = True,
    icon_name: Optional[str] = None
) -> QPushButton:
    """
    Factory function to create styled buttons.
    
    Args:
        text: Button text
        style: Style type - "primary", "secondary", "export", "import"
        on_click: Click handler callback
        cursor: Whether to show pointer cursor on hover
        icon_name: Optional icon name from qtawesome (e.g. "fa5s.save")
        
    Returns:
        Configured QPushButton
    """
    from src.gui.styles import Styles  # Import here to avoid circular imports
    
    btn = QPushButton(f"  {text}" if icon_name else text)
    
    style_map = {
        "primary": Styles.get_button_style,
        "secondary": Styles.get_control_button_style,
        "export": Styles.get_export_button_style,
        "import": Styles.get_import_button_style,
    }
    
    style_func = style_map.get(style, Styles.get_button_style)
    btn.setStyleSheet(style_func())
    
    if icon_name:
        try:
            import qtawesome as qta
            icon_color = "#ffffff" if style == "primary" else Styles.COLOR_TEXT_SECONDARY
            btn.setIcon(qta.icon(icon_name, color=icon_color))
            btn.setIconSize(QSize(16, 16))
        except ImportError:
            pass
    
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
    from src.gui.styles import Styles
    
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
    from src.gui.styles import Styles
    
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
    from src.gui.styles import Styles
    
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
        from src.utils.logger import logger
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


from src.gui.analysis.think_time_bar import ThinkTimeBar
from src.gui.analysis.move_cell_widget import MoveCellWidget

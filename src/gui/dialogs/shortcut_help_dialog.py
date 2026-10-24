"""
Keyboard Shortcuts Help Dialog for Chess Analyzer Pro.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..styles import Styles

try:
    import qtawesome as qta

    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False


class ShortcutHelpDialog(QDialog):
    """Dialog showing the keyboard shortcuts that are currently active.

    Bindings come from the main window's ShortcutManager so the list follows
    the selected preset. Pass ``bindings`` explicitly to override that lookup.
    """

    def __init__(self, parent=None, bindings: list[dict] | None = None):
        super().__init__(parent)
        self._bindings = bindings if bindings is not None else self._lookup_bindings(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.resize(520, 620)
        self.setMinimumSize(480, 540)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Styles.COLOR_BACKGROUND};
            }}
            QLabel {{
                background: transparent;
            }}
        """)

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header with icon
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        if HAS_QTAWESOME:
            icon_label = QLabel()
            icon_label.setPixmap(
                qta.icon("fa5s.keyboard", color=Styles.COLOR_ACCENT).pixmap(28, 28)
            )
            header_layout.addWidget(icon_label)

        title = QLabel("Keyboard Shortcuts")
        title.setStyleSheet(f"""
            font-size: 20px;
            font-weight: bold;
            color: {Styles.COLOR_TEXT_PRIMARY};
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Subtitle
        subtitle = QLabel("Master these shortcuts to analyze games faster")
        subtitle.setStyleSheet(f"""
            font-size: 12px;
            color: {Styles.COLOR_TEXT_SECONDARY};
            background: transparent;
            margin-bottom: 8px;
        """)
        layout.addWidget(subtitle)

        # Scroll Area for shortcuts
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND}; border: none;")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)
        content_layout.setContentsMargins(0, 0, 0, 0)

        shortcuts = self._group_bindings(self._bindings)

        for category, items in shortcuts.items():
            # Category Header
            cat_layout = QHBoxLayout()
            cat_layout.setSpacing(8)

            if HAS_QTAWESOME:
                cat_icons = {
                    "File": "fa5s.folder-open",
                    "Analysis": "fa5s.bolt",
                    "Navigation": "fa5s.arrows-alt",
                    "Board": "fa5s.chess-board",
                    "Variations": "fa5s.code-branch",
                    "Pages": "fa5s.columns",
                    "Help": "fa5s.question-circle",
                    "General": "fa5s.cog",
                }
                cat_icon = QLabel()
                cat_icon.setPixmap(
                    qta.icon(
                        cat_icons.get(category, "fa5s.circle"), color=Styles.COLOR_ACCENT
                    ).pixmap(14, 14)
                )
                cat_layout.addWidget(cat_icon)

            category_label = QLabel(category)
            category_label.setStyleSheet(f"""
                font-size: 13px;
                font-weight: 600;
                color: {Styles.COLOR_ACCENT};
            """)
            cat_layout.addWidget(category_label)
            cat_layout.addStretch()

            content_layout.addLayout(cat_layout)

            # Shortcut items
            for key, description in items:
                row = self._create_shortcut_row(key, description)
                content_layout.addWidget(row)

            # Add spacing between categories
            spacer = QWidget()
            spacer.setFixedHeight(4)
            content_layout.addWidget(spacer)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Footer buttons
        btn_feedback = QPushButton("  Report Bug / Feedback")
        btn_feedback.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_SECONDARY};
                border: 1px solid {Styles.COLOR_BORDER};
                padding: 9px 18px;
                border-radius: 6px;
                font-weight: 500;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_SURFACE};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border-color: {Styles.COLOR_ACCENT};
            }}
        """)
        btn_feedback.setCursor(Qt.CursorShape.PointingHandCursor)
        if HAS_QTAWESOME:
            btn_feedback.setIcon(qta.icon("fa5s.comment-dots", color=Styles.COLOR_TEXT_SECONDARY))
        btn_feedback.clicked.connect(self._open_feedback)

        # Close button
        btn_close = QPushButton("Got it")
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {Styles.COLOR_ACCENT};
                color: white;
                border: none;
                padding: 9px 24px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_ACCENT_HOVER};
            }}
        """)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.accept)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(btn_feedback)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    @staticmethod
    def _lookup_bindings(parent) -> list[dict]:
        window = parent.window() if parent is not None else None
        manager = getattr(window, "shortcut_manager", None)
        return manager.get_bindings() if manager is not None else []

    @staticmethod
    def _group_bindings(bindings: list[dict]) -> dict[str, list[tuple[str, str]]]:
        """Group ``ShortcutManager.get_bindings()`` output by category, in order."""
        grouped: dict[str, list[tuple[str, str]]] = {}
        for binding in bindings:
            if binding["keys"]:
                keys = "  /  ".join(binding["keys"])
                grouped.setdefault(binding["category"], []).append((keys, binding["description"]))
        # F1/? and dialog Esc are handled outside ShortcutManager (keyPressEvent / QDialog).
        grouped.setdefault("General", []).extend(
            [
                ("F1  /  ?", "Show this help"),
                ("Esc", "Close dialogs"),
            ]
        )
        return grouped

    def _open_feedback(self):
        from .feedback_dialog import FeedbackDialog

        dialog = FeedbackDialog(self, initial_tab="bug")
        dialog.exec()

    def _create_shortcut_row(self, key, description):
        """Create a row with key badge and description."""
        row = QFrame()
        row.setStyleSheet(f"""
            QFrame {{
                background-color: {Styles.COLOR_SURFACE};
                border-radius: 6px;
            }}
            QFrame QLabel {{
                background: transparent;
            }}
        """)

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 8, 12, 8)

        # Key badge
        key_label = QLabel(key)
        key_label.setStyleSheet(f"""
            background-color: {Styles.COLOR_SURFACE_LIGHT};
            color: {Styles.COLOR_TEXT_PRIMARY};
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            border: 1px solid {Styles.COLOR_BORDER};
        """)
        key_label.setMinimumWidth(80)
        key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row_layout.addWidget(key_label)

        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet(f"""
            color: {Styles.COLOR_TEXT_SECONDARY};
            font-size: 12px;
            padding-left: 8px;
        """)
        row_layout.addWidget(desc_label)
        row_layout.addStretch()

        return row

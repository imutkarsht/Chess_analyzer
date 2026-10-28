"""
Drop zone component for the Load Game dialog.
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

from ...styles import Styles
from ...theme import ThemeManager

try:
    import qtawesome as qta
except ImportError:  # pragma: no cover - QtAwesome ships with the app
    qta = None


class DropZone(QFrame):
    """Dashed drop target for .pgn files, also clickable and keyboard-focusable."""

    file_dropped = pyqtSignal(str)
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(190)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon = QLabel()
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._title = QLabel("Drop a PGN file here")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle = QLabel("or click to browse  ·  .pgn files")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for label in (self._title, self._subtitle):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout.addWidget(self._icon)
        layout.addWidget(self._title)
        layout.addWidget(self._subtitle)

        manager = ThemeManager.instance()
        manager.theme_changed.connect(self._on_theme_changed)
        manager.accent_changed.connect(self._on_theme_changed)
        self._hovering = False
        self.refresh_styles()

    def _set_idle(self) -> None:
        self._hovering = False
        self.refresh_styles()

    def _set_hovering(self) -> None:
        self._hovering = True
        self.refresh_styles()

    def refresh_styles(self) -> None:
        p = ThemeManager.palette()
        accent = Styles.COLOR_ACCENT
        if self._hovering:
            background = p.accent_subtle
            border = accent
            title = Styles.COLOR_TEXT_PRIMARY
        else:
            background = p.surface
            border = p.border
            title = Styles.COLOR_TEXT_PRIMARY

        self.setStyleSheet(
            f"""
            QFrame#DropZone {{
                background-color: {background};
                border: 1px dashed {border};
                border-radius: 12px;
            }}
            QFrame#DropZone:hover {{
                border-color: {accent};
            }}
            QFrame#DropZone:focus {{
                border: 2px solid {accent};
            }}
            """
        )
        self._title.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {title};"
            " background: transparent; border: none;"
        )
        self._subtitle.setStyleSheet(
            f"font-size: 11px; color: {Styles.COLOR_TEXT_SECONDARY};"
            " background: transparent; border: none;"
        )
        if qta is not None:
            self._icon.setPixmap(
                qta.icon("fa5s.file-upload", color=accent).pixmap(28, 28)
            )
        else:  # pragma: no cover - QtAwesome ships with the app
            self._icon.setText("PGN")

    def _on_theme_changed(self, *_args) -> None:
        self.refresh_styles()

    # -- Interaction ------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self.clicked.emit()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            return
        super().keyPressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(u.toLocalFile().lower().endswith(".pgn") for u in urls):
                event.acceptProposedAction()
                self._set_hovering()
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._set_idle()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        self._set_idle()
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".pgn"):
                self.file_dropped.emit(path)
                break

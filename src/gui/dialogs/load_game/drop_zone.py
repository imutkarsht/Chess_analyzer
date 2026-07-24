"""
Drop zone component for the Load Game dialog.
"""
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from ...styles import Styles

class DropZone(QLabel):
    """Dashed-border drop target for .pgn files. Emits file_dropped(path)."""
    file_dropped = pyqtSignal(str)
    clicked       = pyqtSignal()      # for keyboard / click-to-browse

    @property
    def _STYLE_IDLE(self):
        return f"""
            QLabel {{
                background-color: {Styles.COLOR_SURFACE};
                border: 2px dashed {Styles.COLOR_BORDER};
                border-radius: 12px;
                color: {Styles.COLOR_TEXT_SECONDARY};
            }}
        """

    @property
    def _STYLE_HOVER(self):
        return f"""
            QLabel {{
                background-color: {Styles.COLOR_ACCENT_SUBTLE};
                border: 2px dashed {Styles.COLOR_ACCENT};
                border-radius: 12px;
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
        """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(160)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._set_idle()

    def _set_idle(self):
        self.setStyleSheet(self._STYLE_IDLE)
        self.setText(
            "<div style='text-align:center; line-height:2'>"
            "<span style='font-size:36px'>📂</span><br>"
            "<span style='font-size:14px; font-weight:600'>Drop a .pgn file here</span><br>"
            "<span style='font-size:12px'>or click to browse</span>"
            "</div>"
        )
        self.setTextFormat(Qt.TextFormat.RichText)

    def _set_hovering(self):
        self.setStyleSheet(self._STYLE_HOVER)
        self.setText(
            "<div style='text-align:center; line-height:2'>"
            "<span style='font-size:36px'>⬇️</span><br>"
            "<span style='font-size:14px; font-weight:600'>Release to load</span>"
            "</div>"
        )

    # ── Mouse click → open browse ───────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    # ── Drag & drop events ──────────────────────────────────────────────────
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

"""
PGN Text panel for the Load Game dialog.
"""
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget

from src.backend.storage.game_history import GameHistoryManager
from src.backend.storage.pgn_parser import PGNIndex
from src.constants import MAX_PGN_TEXT_CHARS
from src.gui.components import (
    Button,
    ButtonSize,
    ButtonVariant,
    Label,
    TextArea,
    TextRole,
    TextTone,
)
from src.gui.components.feedback.toast import ToastManager
from src.gui.import_workspace import GameBatch

from .pgn_worker import PgnIndexWorker
from .worker_registry import register_worker, remove_worker


class PgnTextPanel(QWidget):
    """Source page for pasted PGN text; indexing runs off the UI thread."""

    batch_ready = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._index: PGNIndex | None = None
        self._worker: PgnIndexWorker | None = None
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        self._input_widget = QWidget()
        input_layout = QVBoxLayout(self._input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        label = Label("PGN text", role=TextRole.CAPTION, weight=500)
        self._paste_btn = Button(
            "Paste from clipboard",
            ButtonVariant.GHOST,
            ButtonSize.XS,
            icon="fa5s.paste",
            on_click=self._paste_clipboard,
        )
        header.addWidget(label)
        header.addStretch(1)
        header.addWidget(self._paste_btn)
        input_layout.addLayout(header)

        self._text_edit = TextArea(
            placeholder="Paste a game's PGN here — headers and moves are both fine.",
            variant="code",
        )
        input_layout.addWidget(self._text_edit, 1)

        parse_btn = Button(
            "Parse PGN",
            ButtonVariant.PRIMARY,
            ButtonSize.MD,
            icon="fa5s.check",
            on_click=self._parse,
        )
        parse_row = QHBoxLayout()
        parse_row.addStretch(1)
        parse_row.addWidget(parse_btn)
        input_layout.addLayout(parse_row)

        root.addWidget(self._input_widget, stretch=1)

        self._loading_row = QWidget()
        loading_layout = QHBoxLayout(self._loading_row)
        loading_layout.setContentsMargins(0, 0, 0, 0)
        self._loading_label = Label(
            "Reading PGN…",
            role=TextRole.CAPTION,
            tone=TextTone.SECONDARY,
        )
        self._cancel_btn = Button(
            "Cancel",
            ButtonVariant.GHOST,
            ButtonSize.SM,
            on_click=self._cancel_index,
        )
        loading_layout.addWidget(self._loading_label)
        loading_layout.addStretch(1)
        loading_layout.addWidget(self._cancel_btn)
        self._loading_row.setVisible(False)
        root.addWidget(self._loading_row)

    def _paste_clipboard(self) -> None:
        text = QApplication.clipboard().text()
        if len(text) > MAX_PGN_TEXT_CHARS:
            ToastManager.warning(
                self,
                "This PGN is too large to paste. Open it as a file instead.",
            )
            return
        text = text.strip()
        if text:
            self._text_edit.setPlainText(text)

    def load_initial_text(self, text: str) -> bool:
        """Load text supplied by the caller, respecting the paste limit."""
        if len(text) > MAX_PGN_TEXT_CHARS:
            return False
        self._text_edit.setPlainText(text)
        return True

    # ── Text parsing ────────────────────────────────────────────────────────
    def _parse(self):
        text = self._text_edit.toPlainText().strip()
        if not text:
            ToastManager.warning(self, "Please paste some PGN text first.")
            return
        if len(text) > MAX_PGN_TEXT_CHARS:
            ToastManager.error(
                self,
                "This PGN is too large to paste. Open it as a file instead.",
            )
            return

        self._cancel_index()
        self._show_loading()

        worker = PgnIndexWorker(text=text)
        self._worker = worker
        worker.completed.connect(
            lambda result, w=worker: self._on_indexed(result, w)
        )
        worker.failed.connect(
            lambda message, w=worker: self._on_failed(message, w)
        )
        worker.cancelled.connect(lambda w=worker: self._on_cancelled(w))
        worker.finished.connect(lambda w=worker: remove_worker(w))
        register_worker(worker)
        worker.start()

    def _finish_worker(self, worker: PgnIndexWorker) -> None:
        if worker is self._worker:
            self._worker = None

    def _on_indexed(self, index: PGNIndex, worker: PgnIndexWorker) -> None:
        if worker is not self._worker:
            return
        self._finish_worker(worker)

        if not index.games:
            ToastManager.warning(self, "No valid games found in this text.")
            self._show_input()
            return

        self._index = index
        self._text_edit.clear()
        batch = GameBatch.from_pgn_index(
            index,
            GameHistoryManager().get_game_identity_keys(),
            "Pasted PGN",
        )
        self._show_input()
        self.batch_ready.emit(batch)

    def _on_failed(self, message: str, worker: PgnIndexWorker) -> None:
        if worker is not self._worker:
            return
        self._finish_worker(worker)
        self._show_input()
        ToastManager.error(self, message)

    def _on_cancelled(self, worker: PgnIndexWorker) -> None:
        if worker is not self._worker:
            return
        self._finish_worker(worker)
        self._show_input()

    def _cancel_index(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._worker = None

    def _show_loading(self) -> None:
        self._input_widget.setVisible(False)
        self._loading_row.setVisible(True)

    def _show_input(self) -> None:
        self._loading_row.setVisible(False)
        self._input_widget.setVisible(True)

    def _clear(self):
        self._cancel_index()
        self._index = None
        self._text_edit.clear()
        self._show_input()

    def reset(self):
        """Called when the user switches away from this source tab."""
        self._clear()

    def shutdown(self) -> None:
        """Cancel work when the dialog is closing."""
        self._cancel_index()
        self._index = None

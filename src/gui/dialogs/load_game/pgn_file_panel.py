"""
PGN File panel for the Load Game dialog.
"""
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget

from src.backend.storage.pgn_parser import PGNIndex
from src.gui.components import (
    Button,
    ButtonSize,
    ButtonVariant,
    Label,
    TextRole,
    TextTone,
)
from src.gui.components.feedback.toast import ToastManager

from .drop_zone import DropZone
from .helpers import classify_time_control, game_row
from .inline_game_list import InlineGameList
from .pgn_worker import PgnIndexWorker
from .worker_registry import register_worker, remove_worker


class PgnFilePanel(QWidget):
    """
    Right-panel page for 'PGN File' source.
    Handles drag & drop and browse. Files are indexed off the UI thread;
    selecting a card emits only that game's raw PGN.
    """
    pgn_ready     = pyqtSignal(str, object)   # (pgn_text, None)
    pending_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._index: PGNIndex | None = None
        self._worker: PgnIndexWorker | None = None
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # ── Drop zone ───────────────────────────────────────────────────────
        self._drop_zone = DropZone()
        self._drop_zone.setMinimumHeight(190)
        self._drop_zone.setMaximumHeight(240)
        self._drop_zone.file_dropped.connect(self._load_file)
        self._drop_zone.clicked.connect(self._browse)
        root.addWidget(self._drop_zone)

        # ── Browse button ────────────────────────────────────────────────────
        self._browse_btn = Button(
            "Browse files",
            ButtonVariant.HOLLOW,
            ButtonSize.MD,
            icon="fa5s.folder-open",
            on_click=self._browse,
        )
        self._browse_btn.setMaximumWidth(180)
        browse_row = QHBoxLayout()
        browse_row.setContentsMargins(0, 0, 0, 0)
        browse_row.addStretch(1)
        browse_row.addWidget(self._browse_btn)
        browse_row.addStretch(1)
        root.addLayout(browse_row)

        # ── Indexing status ─────────────────────────────────────────────────
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

        # ── Inline game list (shown after load) ───────────────
        self._game_list = InlineGameList()
        self._game_list.setVisible(False)
        self._game_list.game_chosen.connect(self._on_game_chosen)
        self._game_list.cleared.connect(self._clear)
        root.addWidget(self._game_list, stretch=1)

    # ── File loading ────────────────────────────────────────────────────────
    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PGN File", "", "PGN Files (*.pgn);;All Files (*)"
        )
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        self._cancel_index()
        self.pending_cleared.emit()
        self._show_loading()

        worker = PgnIndexWorker(path=path)
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
            ToastManager.warning(self, "No valid games found in this file.")
            self._show_idle()
            return

        self._index = index
        rows = [
            game_row(
                date=game.date,
                time_class=classify_time_control(game.time_control),
                result=game.result,
                moves=None,
                white=game.white,
                black=game.black,
                white_elo=game.white_elo,
                black_elo=game.black_elo,
                opening=game.opening,
            )
            for game in index.games
        ]

        count = len(index.games)
        header_text = (
            "1 game ready to load:"
            if count == 1
            else f"Select a game ({count} found):"
        )
        self._loading_row.setVisible(False)
        self._drop_zone.setVisible(False)
        self._browse_btn.setVisible(False)
        self._game_list.populate(rows, header_text)
        self._game_list.setVisible(True)

    def _on_failed(self, message: str, worker: PgnIndexWorker) -> None:
        if worker is not self._worker:
            return
        self._finish_worker(worker)
        self._show_idle()
        ToastManager.error(self, message)

    def _on_cancelled(self, worker: PgnIndexWorker) -> None:
        if worker is not self._worker:
            return
        self._finish_worker(worker)
        self._show_idle()

    def _cancel_index(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._worker = None

    def _show_loading(self) -> None:
        self._drop_zone.setVisible(False)
        self._browse_btn.setVisible(False)
        self._game_list.setVisible(False)
        self._loading_row.setVisible(True)

    def _show_idle(self) -> None:
        self._loading_row.setVisible(False)
        self._game_list.setVisible(False)
        self._drop_zone.setVisible(True)
        self._browse_btn.setVisible(True)
        self._drop_zone._set_idle()

    def _on_game_chosen(self, index: int):
        if self._index is not None and 0 <= index < len(self._index.games):
            self.pgn_ready.emit(self._index.game_text(index), None)

    def _clear(self):
        self._cancel_index()
        self._index = None
        self._game_list.clear()
        self._game_list.setVisible(False)
        self._show_idle()
        self.pending_cleared.emit()

    def reset(self):
        """Called when the user switches away from this source tab."""
        self._clear()

    def shutdown(self) -> None:
        """Cancel work when the dialog is closing."""
        self._cancel_index()
        self._index = None

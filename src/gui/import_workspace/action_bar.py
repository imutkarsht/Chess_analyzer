"""Action bar for the import workspace."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QWidget

from src.gui.components import (
    Button,
    ButtonSize,
    ButtonVariant,
    Label,
    MiniBar,
    TextRole,
    TextTone,
)
from src.gui.styles import Styles


class ImportActionBar(QFrame):
    """Selection summary, import progress, and primary actions."""

    open_clicked = pyqtSignal()
    add_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("ImportActionBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(10)

        self.lbl_selection = Label(
            "0 of 0 row(s) selected.",
            role=TextRole.CAPTION,
            tone=TextTone.SECONDARY,
        )
        layout.addWidget(self.lbl_selection)

        self._import_label = Label(
            "",
            role=TextRole.CAPTION,
            tone=TextTone.SECONDARY,
        )
        self._import_progress = MiniBar(0)
        self._import_progress.setFixedWidth(180)
        self._import_label.setVisible(False)
        self._import_progress.setVisible(False)
        layout.addWidget(self._import_label)
        layout.addWidget(self._import_progress)
        layout.addStretch(1)

        self.btn_add = Button(
            "Add to history",
            ButtonVariant.HOLLOW,
            ButtonSize.MD,
            icon="fa5s.database",
            on_click=self.add_clicked.emit,
        )
        self.btn_add.setEnabled(False)
        layout.addWidget(self.btn_add)

        self.btn_open = Button(
            "Open game",
            ButtonVariant.PRIMARY,
            ButtonSize.MD,
            icon="fa5s.play",
            on_click=self.open_clicked.emit,
        )
        self.btn_open.setEnabled(False)
        layout.addWidget(self.btn_open)
        self.refresh_styles()

    def set_selection(
        self, count: int, total: int, can_open_current: bool
    ) -> None:
        self.lbl_selection.setText(
            f"{count} of {total} row(s) selected."
        )
        self.btn_open.setEnabled(count == 1 or (count == 0 and can_open_current))
        self.btn_add.setEnabled(count >= 1)
        self.btn_add.setText(
            f"Add {count} to history" if count > 1 else "Add to history"
        )
        if count >= 2:
            self.btn_open.set_variant(ButtonVariant.HOLLOW)
            self.btn_add.set_variant(ButtonVariant.PRIMARY)
        else:
            self.btn_open.set_variant(ButtonVariant.PRIMARY)
            self.btn_add.set_variant(ButtonVariant.HOLLOW)
        self.btn_open.refresh_styles()
        self.btn_add.refresh_styles()

    def begin_import(self, total: int) -> None:
        self._import_label.setText(f"Adding 0 / {total}…")
        self._import_label.setVisible(True)
        self._import_progress.setRange(0, total)
        self._import_progress.setValue(0)
        self._import_progress.setVisible(True)
        self.btn_add.setEnabled(False)
        self.btn_open.setEnabled(False)

    def update_progress(self, done: int, total: int) -> None:
        self._import_label.setText(f"Adding {done} / {total}…")
        self._import_progress.setValue(done)

    def finish_import(self) -> None:
        self._import_label.setVisible(False)
        self._import_progress.setVisible(False)

    def refresh_styles(self) -> None:
        self.setStyleSheet(Styles.get_import_action_bar_style())
        self.btn_open.refresh_styles()
        self.btn_add.refresh_styles()
        self._import_progress.refresh_styles()

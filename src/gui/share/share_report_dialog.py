# SPDX-License-Identifier: GPL-3.0-only
"""Preview and export actions for a shareable game report."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QBuffer, QIODevice, QMimeData, Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.backend.storage.models import GameAnalysis
from src.gui.components import Button, ButtonVariant, Label, TextRole, TextTone
from src.gui.components.feedback.toast import ToastManager

from .report_card import ShareReportRenderer


class ShareReportDialog(QDialog):
    """Show one report preview and provide image, PNG, and Markdown exports."""

    def __init__(self, game: GameAnalysis, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Share Game Report")
        self.setAccessibleName("Share Game Report")
        self._image = ShareReportRenderer.render(game)
        self._markdown = ShareReportRenderer.markdown_summary(game)
        self.setFixedSize(760, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(
            Label(
                "Share your game report",
                role=TextRole.DIALOG_TITLE,
                tone=TextTone.PRIMARY,
                weight=700,
            )
        )

        self.preview_label = QLabel(self)
        self.preview_label.setAccessibleName("Game report preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setPixmap(
            QPixmap.fromImage(self._image).scaled(
                680,
                383,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        layout.addWidget(self.preview_label, stretch=1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.copy_image_button = Button(
            "Copy image",
            variant=ButtonVariant.PRIMARY,
            on_click=self.copy_image,
        )
        self.copy_image_button.setAutoDefault(False)
        self.save_png_button = Button(
            "Save PNG",
            variant=ButtonVariant.OUTLINED,
            on_click=self.save_png,
        )
        self.save_png_button.setAutoDefault(False)
        self.copy_markdown_button = Button(
            "Copy Markdown",
            variant=ButtonVariant.OUTLINED,
            on_click=self.copy_markdown,
        )
        self.copy_markdown_button.setAutoDefault(False)
        self.close_button = Button(
            "Close",
            variant=ButtonVariant.GHOST,
            on_click=self.accept,
        )
        self.close_button.setDefault(True)
        for button in (
            self.copy_image_button,
            self.save_png_button,
            self.copy_markdown_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        actions.addWidget(self.close_button)
        layout.addLayout(actions)

    @property
    def image(self) -> QImage:
        """The already-rendered preview and export image."""
        return self._image

    def copy_image(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setImage(self._image)
        mime_data = QMimeData()
        mime_data.setImageData(self._image)
        mime_data.setData("image/png", self._png_bytes())
        clipboard.setMimeData(mime_data)
        ToastManager.success(self, "Report image copied to clipboard.")

    def save_png(self) -> None:
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save Game Report",
            "game-report.png",
            "PNG image (*.png)",
        )
        if not file_name:
            return

        path = Path(file_name)
        if path.suffix.lower() != ".png":
            path = path.with_suffix(".png") if path.suffix else path.with_name(
                f"{path.name}.png"
            )
        if not self._image.save(str(path), "PNG"):
            ToastManager.error(self, f"Could not save report image to {path}.")
            return
        ToastManager.success(self, f"Report saved to {path}.")

    def copy_markdown(self) -> None:
        QApplication.clipboard().setText(self._markdown)
        ToastManager.success(self, "Report summary copied to clipboard.")

    def _png_bytes(self) -> bytes:
        buffer = QBuffer()
        if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
            raise RuntimeError("Could not open an in-memory buffer for PNG export.")
        try:
            if not self._image.save(buffer, "PNG"):
                raise RuntimeError("Could not encode the report image as PNG.")
            return bytes(buffer.data())
        finally:
            buffer.close()

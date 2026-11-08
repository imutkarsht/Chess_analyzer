"""Shadcn-style delegates for the import table."""

from __future__ import annotations

import chess
import chess.svg
from PyQt6.QtCore import QByteArray, QEvent, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QPixmapCache
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QHeaderView, QStyledItemDelegate

from src.constants import DEFAULT_BOARD_THEME
from src.gui.styles import Styles
from src.gui.theme.typography import TextTone
from src.utils.config import ConfigManager

from .batch import GameCandidate


def _paint_checkbox(
    painter: QPainter, center, checked: bool, partial: bool = False
) -> None:
    size = 16
    box = QRectF(
        center.x() - size / 2,
        center.y() - size / 2,
        size,
        size,
    )
    fill = QColor(
        Styles.COLOR_ACCENT
        if checked or partial
        else Styles.COLOR_SURFACE
    )
    border = QColor(
        Styles.COLOR_ACCENT
        if checked or partial
        else Styles.COLOR_TEXT_MUTED
    )
    painter.setPen(QPen(border, 1.2))
    painter.setBrush(fill)
    painter.drawRoundedRect(box, 4, 4)
    if checked:
        painter.setPen(
            QPen(
                QColor(Styles.COLOR_ON_ACCENT),
                1.8,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.drawLine(
            int(box.left() + 4),
            int(box.center().y()),
            int(box.center().x() - 1),
            int(box.bottom() - 4),
        )
        painter.drawLine(
            int(box.center().x() - 1),
            int(box.bottom() - 4),
            int(box.right() - 4),
            int(box.top() + 4),
        )
    elif partial:
        painter.setPen(
            QPen(
                QColor(Styles.COLOR_ON_ACCENT),
                1.8,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
        )
        painter.drawLine(
            int(box.left() + 4),
            int(box.center().y()),
            int(box.right() - 4),
            int(box.center().y()),
        )


class CheckboxDelegate(QStyledItemDelegate):
    """Paints a compact rounded checkbox and toggles it on click."""

    def paint(self, painter, option, index):
        candidate: GameCandidate | None = index.data(
            Qt.ItemDataRole.UserRole
        )
        if candidate is not None and candidate.in_history:
            return
        checked = (
            index.data(Qt.ItemDataRole.CheckStateRole)
            == Qt.CheckState.Checked
        )
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        _paint_checkbox(painter, option.rect.center(), checked)
        painter.restore()

    def editorEvent(self, event, model, option, index):  # noqa: N802 - Qt override
        candidate: GameCandidate | None = index.data(
            Qt.ItemDataRole.UserRole
        )
        if candidate is None or candidate.in_history:
            return False
        if event.type() != QEvent.Type.MouseButtonRelease:
            return False
        if not option.rect.contains(event.position().toPoint()):
            return False
        checked = (
            index.data(Qt.ItemDataRole.CheckStateRole)
            == Qt.CheckState.Checked
        )
        model.setData(
            index,
            Qt.CheckState.Unchecked if checked else Qt.CheckState.Checked,
            Qt.ItemDataRole.CheckStateRole,
        )
        return True


class CheckboxHeader(QHeaderView):
    """Header with a select-all checkbox over the first column."""

    toggled = pyqtSignal(bool)

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._checked = False
        self._partial = False
        self.setSectionsClickable(True)

    def set_state(self, checked: bool, partial: bool = False) -> None:
        if checked == self._checked and partial == self._partial:
            return
        self._checked = checked
        self._partial = partial
        self.viewport().update()

    def paintSection(self, painter, rect, logicalIndex):  # noqa: N802 - Qt override
        super().paintSection(painter, rect, logicalIndex)
        if logicalIndex != 0:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        _paint_checkbox(
            painter, rect.center(), self._checked, self._partial
        )
        painter.restore()

    def mousePressEvent(self, event):  # noqa: N802 - Qt override
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.logicalIndexAt(event.position().toPoint()) == 0
        ):
            self.toggled.emit(not self._checked)
            return
        super().mousePressEvent(event)


class StatusPillDelegate(QStyledItemDelegate):
    """Paints Saved/New as a compact semantic pill."""

    def paint(self, painter, option, index):
        candidate: GameCandidate | None = index.data(
            Qt.ItemDataRole.UserRole
        )
        if candidate is None:
            return
        text = "Saved" if candidate.in_history else "New"
        tone = TextTone.GOOD if candidate.in_history else TextTone.MUTED
        color = QColor(Styles.get_tone_color(tone))
        background = QColor(color)
        background.setAlpha(28 if candidate.in_history else 20)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(option.font)
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        width = metrics.horizontalAdvance(text) + 18
        height = 22
        rect = QRectF(
            option.rect.center().x() - width / 2,
            option.rect.center().y() - height / 2,
            width,
            height,
        )
        painter.setPen(QPen(color, 1))
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 11, 11)
        painter.setPen(color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


class BoardDelegate(QStyledItemDelegate):
    """Paints a cached 44×44 board thumb; never creates one widget per row."""

    def __init__(self, parent=None, size: int = 72):
        super().__init__(parent)
        self._size = size

    def paint(self, painter, option, index):
        candidate: GameCandidate | None = index.data(
            Qt.ItemDataRole.UserRole
        )
        if candidate is None:
            return
        side = self._size
        rect = QRectF(
            option.rect.center().x() - side / 2,
            option.rect.center().y() - side / 2,
            side,
            side,
        )
        pixmap = None
        if candidate.last_fen:
            pixmap = self._render(candidate.last_fen)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if pixmap is not None:
            painter.drawPixmap(rect.toRect(), pixmap)
        else:
            painter.setBrush(QColor(Styles.COLOR_SURFACE_LIGHT))
            painter.setPen(QPen(QColor(Styles.COLOR_BORDER), 1))
            painter.drawRoundedRect(rect, 5, 5)
            font = QFont(option.font)
            font.setPixelSize(18)
            painter.setFont(font)
            painter.setPen(QColor(Styles.COLOR_TEXT_MUTED))
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignCenter, "♟"
            )
            painter.restore()
            return
        painter.setPen(QPen(QColor(Styles.COLOR_BORDER), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 5, 5)
        painter.restore()

    def _render(self, fen: str) -> QPixmap | None:
        theme_name = ConfigManager().get("board_theme", DEFAULT_BOARD_THEME)
        colors = Styles.get_board_colors(theme_name)
        key = f"import-board:{self._size}:{colors['dark']}:{colors['light']}:{fen}"
        cached = QPixmapCache.find(key)
        if cached is not None:
            return cached
        try:
            parts = fen.split(" ")
            castling = parts[2] if len(parts) > 2 else ""
            board = chess.Board(
                fen,
                chess960=any(c not in "KQkq-" for c in castling),
            )
            svg = chess.svg.board(
                board=board,
                size=self._size,
                coordinates=False,
                colors={
                    "square light": colors["light"],
                    "square dark": colors["dark"],
                },
            )
            renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
            pixmap = QPixmap(self._size, self._size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            QPixmapCache.insert(key, pixmap)
            return pixmap
        except Exception:
            return None

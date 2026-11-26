# SPDX-License-Identifier: GPL-3.0-only
"""Accessible theme preview card used by the Appearance gallery.

The card is a checkable button with a painted preview strip, the theme name,
and its light/dark label. Selection is announced by both an accent border and
a check badge so it never depends on colour alone.
"""

from __future__ import annotations

from collections.abc import Sequence

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from src.gui.components.controls.button import Button, ButtonSize, ButtonVariant
from src.gui.components.display.label import Label
from src.gui.theme import ThemeManager
from src.gui.theme.typography import TextRole, TextTone


class _ThemeSwatch(QWidget):
    """Three-part background/surface/accent preview strip."""

    def __init__(self, colors: Sequence[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._colors: list[str] = []
        self.setFixedSize(60, 24)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.set_colors(colors)

    @property
    def colors(self) -> tuple[str, ...]:
        return tuple(self._colors)

    def set_colors(self, colors: Sequence[str]) -> None:
        self._colors = [str(color) for color in colors if color]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        del event
        if not self._colors:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = min(7.0, rect.height() / 3.0)
        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        painter.setClipPath(clip)

        segment_width = rect.width() / len(self._colors)
        for index, color in enumerate(self._colors):
            left = rect.left() + index * segment_width
            right = (
                rect.right()
                if index == len(self._colors) - 1
                else left + segment_width
            )
            painter.fillRect(
                QRectF(left, rect.top(), right - left, rect.height()),
                QColor(color),
            )
        painter.end()


class _SelectedBadge(QWidget):
    """Small check badge drawn above the card chrome."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        del event
        palette = ThemeManager.palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        painter.setPen(QPen(QColor(palette.ui_accent), 1.5))
        painter.setBrush(QColor(palette.surface))
        painter.drawRoundedRect(rect, 5.0, 5.0)

        pen = QPen(QColor(palette.ui_accent), 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(QPointF(5.5, 10.0), QPointF(8.5, 13.0))
        painter.drawLine(QPointF(8.5, 13.0), QPointF(14.5, 7.0))
        painter.end()


class ThemeCard(Button):
    """One selectable theme card in the Appearance gallery."""

    def __init__(
        self,
        value: str,
        title: str,
        mode_label: str,
        description: str,
        swatches: Sequence[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            "",
            ButtonVariant.GHOST,
            ButtonSize.SM,
            checkable=True,
            parent=parent,
        )
        self._value = value
        self._title = title
        self._mode_label = mode_label
        self._description = description

        self.setObjectName("ThemeCard")
        self.setAutoDefault(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Button(size=SM) sets an explicit 28 px minimum, which overrides
        # minimumSizeHint() and lets tight settings layouts crush the card.
        self.setMinimumHeight(56)
        self.setAccessibleName(f"{title} theme")
        self.setAccessibleDescription(description)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        self.swatch = _ThemeSwatch(swatches, self)
        self.name_label = Label(
            title,
            role=TextRole.BODY_STRONG,
            parent=self,
        )
        self.mode_caption = Label(
            mode_label,
            role=TextRole.MICRO,
            tone=TextTone.SECONDARY,
            parent=self,
        )
        for child in (self.swatch, self.name_label, self.mode_caption):
            child.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
            )
            child.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        text_host = QWidget(self)
        text = QVBoxLayout(text_host)
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(2)
        text.addWidget(self.name_label)
        text.addWidget(self.mode_caption)

        layout.addWidget(self.swatch, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(text_host, 1, Qt.AlignmentFlag.AlignVCenter)

        self.badge = _SelectedBadge(self)
        self.badge.hide()
        self.badge.raise_()

        self.toggled.connect(self._sync_selected_state)
        self._sync_selected_state(False)

    @property
    def value(self) -> str:
        return self._value

    @property
    def mode_label(self) -> str:
        return self._mode_label

    @property
    def description(self) -> str:
        return self._description

    @property
    def swatch_colors(self) -> tuple[str, ...]:
        return self.swatch.colors

    def set_swatches(self, colors: Sequence[str]) -> None:
        self.swatch.set_colors(colors)

    def _sync_selected_state(self, checked: bool) -> None:
        self.badge.setVisible(bool(checked))
        description = self._description or f"{self._title} theme."
        if checked:
            description = f"{description} Selected."
        self.setAccessibleDescription(description)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt override
        layout = self.layout()
        hint = layout.sizeHint() if layout is not None else QSize(210, 56)
        return hint.expandedTo(QSize(210, 56))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt override
        return QSize(190, 56)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self.badge.move(self.width() - self.badge.width() - 6, 6)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        self._sync_selected_state(self.isChecked())

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            event.accept()
            return
        super().keyPressEvent(event)

    def refresh_styles(self) -> None:
        """Repolish chrome and repaint previews after a theme/accent change."""
        super().refresh_styles()
        if hasattr(self, "swatch"):
            self.swatch.update()
        if hasattr(self, "badge"):
            self.badge.update()


__all__ = ["ThemeCard"]

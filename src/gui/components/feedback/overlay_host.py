# SPDX-License-Identifier: GPL-3.0-only
"""Full-window host for in-window overlay dialogs.

The host owns the scrim, the optional blurred background snapshot and the card
geometry. It deliberately does not own dialog results or focus policy; those
belong to :class:`OverlayManager`.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import (
    QEvent,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QMainWindow, QWidget

from src.gui.components.feedback.overlay_card import OverlayCard
from src.gui.theme import Motion, MotionDuration, MotionEasing, ThemeManager


class _CardLayer(QWidget):
    """Animation/layout shell around one card and its painted shadow.

    The shadow is painted here rather than applied as a QGraphicsEffect: the
    layer also needs an opacity effect during enter/exit, and nesting graphics
    effects makes Qt paint a widget into two devices at once.
    """

    SHADOW_MARGIN = 32

    def __init__(self, card: OverlayCard, parent: QWidget) -> None:
        super().__init__(parent)
        self.card = card
        self._animating = False
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        card.setParent(self)
        card.show()

    def resizeEvent(self, event):
        bounds = self._card_bounds()
        self.card.setGeometry(bounds)
        super().resizeEvent(event)

    def _card_bounds(self) -> QRect:
        return self.rect().adjusted(
            self.SHADOW_MARGIN,
            self.SHADOW_MARGIN,
            -self.SHADOW_MARGIN,
            -self.SHADOW_MARGIN,
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        bounds = QRectF(self._card_bounds())
        ink = QColor(ThemeManager.palette().piece_black)
        # Draw from the outer, faint edge inward. The opaque card covers the
        # centre, leaving a soft elevation falloff around the border.
        for index in range(20, 0, -1):
            spread = index * 1.25
            alpha = 2 + int((20 - index) * 0.9)
            ink.setAlpha(min(alpha, 22))
            painter.setPen(QPen(ink, 2.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                bounds.adjusted(
                    -spread,
                    -spread + 5,
                    spread,
                    spread + 8,
                ),
                14 + spread,
                14 + spread,
            )
        painter.end()


class OverlayHost(QWidget):
    """Covers one top-level window and paints the dimmed backdrop."""

    backdrop_clicked = pyqtSignal()

    EDGE_MARGIN = 24
    BLUR_SCALE = 0.12
    REGRAB_DELAY_MS = 150

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self.setObjectName("OverlayHost")
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setGeometry(window.rect())
        self.hide()

        self._window = window
        self._layers: list[_CardLayer] = []
        self._background: QPixmap | None = None
        self._blur_enabled = True
        self._press_pos = None
        self._layout_scheduled = False

        self._regrab_timer = QTimer(self)
        self._regrab_timer.setSingleShot(True)
        self._regrab_timer.setInterval(self.REGRAB_DELAY_MS)
        self._regrab_timer.timeout.connect(self._refresh_background)

        window.installEventFilter(self)
        manager = ThemeManager.instance()
        manager.theme_changed.connect(self._on_theme_changed)
        manager.accent_changed.connect(self._on_theme_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_showing(self) -> bool:
        return bool(self._layers)

    @property
    def top_layer(self) -> _CardLayer | None:
        return self._layers[-1] if self._layers else None

    @property
    def top_card(self) -> OverlayCard | None:
        layer = self.top_layer
        return layer.card if layer is not None else None

    def push_card(self, card: OverlayCard) -> _CardLayer:
        previous = self.top_layer
        if previous is not None:
            previous.hide()

        layer = _CardLayer(card, self)
        card.size_hint_changed.connect(
            lambda layer=layer: self._schedule_layout(layer)
        )
        self._layers.append(layer)
        self.setGeometry(self._window.rect())
        if len(self._layers) == 1:
            self._capture_background()
        layer.show()
        self._layout_layer(layer)

        self.show()
        self.raise_()
        layer.raise_()
        self._animate_in(layer)
        return layer

    def pop_layer(
        self,
        layer: _CardLayer,
        *,
        animate: bool = True,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        if layer not in self._layers:
            return
        self._layers.remove(layer)

        previous = self.top_layer
        if previous is not None:
            previous.show()
            self._layout_layer(previous)
            # Keep the closing layer above the restored card while it fades.
            layer.raise_()

        self._animate_out(layer, animate=animate)
        if not self._layers:
            self._regrab_timer.stop()
            if not animate or not self._motion_enabled():
                self._background = None
                self.hide()
            # Otherwise hide after the exit animation finishes.
        if on_finished is not None:
            on_finished()

    def set_blur_enabled(self, enabled: bool) -> None:
        self._blur_enabled = bool(enabled)
        if self.is_showing:
            self._refresh_background()

    def refresh_background(self) -> None:
        """Force a fresh snapshot (used after large content changes)."""
        self._refresh_background()

    # ------------------------------------------------------------------
    # Card geometry
    # ------------------------------------------------------------------

    def _schedule_layout(self, layer: _CardLayer) -> None:
        if self._layout_scheduled:
            return
        self._layout_scheduled = True

        def run() -> None:
            self._layout_scheduled = False
            if layer in self._layers:
                self._layout_layer(layer)

        QTimer.singleShot(0, run)

    def _layout_layer(self, layer: _CardLayer) -> None:
        if layer._animating:
            return
        card = layer.card
        available_width = max(260, self.width() - 2 * self.EDGE_MARGIN)
        width = max(
            card.minimum_width,
            min(card.max_width, available_width),
        )
        width = min(width, available_width)
        card.setFixedWidth(width)

        preferred = card.preferred_height()
        min_height = card.minimumSizeHint().height()
        available_height = max(180, self.height() - 2 * self.EDGE_MARGIN)
        height = min(max(preferred, min_height), available_height)
        card.setFixedHeight(height)

        x = (self.width() - width) // 2
        y = (self.height() - height) // 2
        margin = _CardLayer.SHADOW_MARGIN
        layer.setGeometry(
            x - margin,
            y - margin,
            width + 2 * margin,
            height + 2 * margin,
        )

    def _target_geometry(self, layer: _CardLayer) -> QRect:
        return layer.geometry()

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------

    @staticmethod
    def _motion_enabled() -> bool:
        return Motion.enabled() and not Motion.prefers_reduced_motion()

    def _animate_in(self, layer: _CardLayer) -> None:
        target = self._target_geometry(layer)
        if not self._motion_enabled():
            layer.setGeometry(target)
            return

        effect = QGraphicsOpacityEffect(layer)
        effect.setOpacity(0.0)
        layer.setGraphicsEffect(effect)
        layer._animating = True

        start = target.translated(0, 10)
        layer.setGeometry(start)

        group = QParallelAnimationGroup(layer)
        geometry = QPropertyAnimation(layer, b"geometry", group)
        geometry.setDuration(MotionDuration.BASE)
        geometry.setEasingCurve(MotionEasing.ENTER)
        geometry.setStartValue(start)
        geometry.setEndValue(target)

        fade = QPropertyAnimation(effect, b"opacity", group)
        fade.setDuration(MotionDuration.BASE)
        fade.setEasingCurve(MotionEasing.ENTER)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)

        group.addAnimation(geometry)
        group.addAnimation(fade)

        def finish() -> None:
            layer.setGraphicsEffect(None)
            layer._animating = False
            if layer in self._layers:
                self._layout_layer(layer)
            group.deleteLater()

        group.finished.connect(finish)
        group.start()

    def _animate_out(self, layer: _CardLayer, *, animate: bool) -> None:
        if not animate or not self._motion_enabled():
            layer.hide()
            layer.deleteLater()
            if not self._layers:
                self._background = None
                self.hide()
            return

        effect = QGraphicsOpacityEffect(layer)
        effect.setOpacity(1.0)
        layer.setGraphicsEffect(effect)
        layer._animating = True

        start = layer.geometry()
        end = start.translated(0, 8)

        group = QParallelAnimationGroup(layer)
        geometry = QPropertyAnimation(layer, b"geometry", group)
        geometry.setDuration(MotionDuration.FAST)
        geometry.setEasingCurve(MotionEasing.EXIT)
        geometry.setStartValue(start)
        geometry.setEndValue(end)

        fade = QPropertyAnimation(effect, b"opacity", group)
        fade.setDuration(MotionDuration.FAST)
        fade.setEasingCurve(MotionEasing.EXIT)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)

        group.addAnimation(geometry)
        group.addAnimation(fade)

        def finish() -> None:
            layer.hide()
            layer.deleteLater()
            group.deleteLater()
            if not self._layers:
                self._background = None
                self.hide()

        group.finished.connect(finish)
        group.start()

    # ------------------------------------------------------------------
    # Painting and snapshots
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if self._background is not None and not self._background.isNull():
            painter.drawPixmap(self.rect(), self._background)

        palette = ThemeManager.palette()
        scrim = QColor(palette.overlay_scrim)
        scrim.setAlphaF(palette.overlay_scrim_alpha)
        painter.fillRect(self.rect(), scrim)
        super().paintEvent(event)

    def _capture_background(self) -> None:
        if not self._window.isVisible():
            self._background = None
            return
        source = self._snapshot_source()
        if source is None or source.width() <= 0 or source.height() <= 0:
            self._background = None
            return
        try:
            snapshot = source.grab()
            if snapshot.isNull():
                self._background = None
                return
            self._background = (
                self._blur_pixmap(snapshot) if self._blur_enabled else snapshot
            )
        except RuntimeError:
            self._background = None

    def _snapshot_source(self) -> QWidget | None:
        if isinstance(self._window, QMainWindow):
            central = self._window.centralWidget()
            if central is not None:
                return central
        return self._window

    @classmethod
    def _blur_pixmap(cls, pixmap: QPixmap) -> QPixmap:
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        if image.isNull():
            return pixmap

        width, height = image.width(), image.height()
        longest = max(width, height)
        target = max(48, int(longest * cls.BLUR_SCALE))
        if target >= longest:
            small = image
        elif width >= height:
            small = image.scaledToWidth(
                target,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            small = image.scaledToHeight(
                target,
                Qt.TransformationMode.SmoothTransformation,
            )

        blurred = small.scaled(
            width,
            height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        return QPixmap.fromImage(blurred)

    def _refresh_background(self) -> None:
        if not self.is_showing:
            return
        self._capture_background()
        self.update()

    def _schedule_background_refresh(self) -> None:
        if not self.is_showing:
            return
        self._regrab_timer.start()

    def _on_theme_changed(self, *_args) -> None:
        self._background = None
        self.update()
        if self.is_showing:
            # Let the global stylesheet repaint once before grabbing the new
            # palette; otherwise the snapshot captures the old theme.
            QTimer.singleShot(30, self._refresh_background)

    # ------------------------------------------------------------------
    # Input blocking
    # ------------------------------------------------------------------

    def _point_inside_top_card(self, pos: QPoint) -> bool:
        card = self.top_card
        if card is None or not card.isVisible():
            return False
        top_left = card.mapTo(self, QPoint(0, 0))
        return QRect(top_left, card.size()).contains(pos)

    def mousePressEvent(self, event):
        pos = event.position().toPoint()
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self._point_inside_top_card(pos)
        ):
            self._press_pos = pos
        else:
            self._press_pos = None
        event.accept()

    def mouseReleaseEvent(self, event):
        pos = event.position().toPoint()
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._press_pos is not None
            and not self._point_inside_top_card(pos)
            and (pos - self._press_pos).manhattanLength() <= 6
        ):
            self.backdrop_clicked.emit()
        self._press_pos = None
        event.accept()

    def mouseDoubleClickEvent(self, event):
        event.accept()

    def wheelEvent(self, event):
        event.accept()

    def contextMenuEvent(self, event):
        event.accept()

    def dragEnterEvent(self, event):
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        event.acceptProposedAction()

    # ------------------------------------------------------------------
    # Parent tracking
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event):
        if obj is self._window:
            event_type = event.type()
            if event_type == QEvent.Type.Resize:
                self.setGeometry(self._window.rect())
                if self._layers:
                    self._layout_layer(self._layers[-1])
                    self._schedule_background_refresh()
            elif event_type == QEvent.Type.Show and self.is_showing:
                self._schedule_background_refresh()
        return super().eventFilter(obj, event)

    def showEvent(self, event):
        self.setGeometry(self._window.rect())
        super().showEvent(event)

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QStackedWidget


class FadedStackedWidget(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._fade_out = None
        self._fade_in = None
        self._target_index = None

    def setCurrentIndex(self, index):
        if index < 0 or index >= self.count():
            return

        current_idx = self.currentIndex()
        if index == current_idx and self._target_index is None:
            return
        if self._target_index == index:
            return

        # Stop any active animation cleanly
        if self._fade_out and self._fade_out.state() == QPropertyAnimation.State.Running:
            self._fade_out.stop()
        if self._fade_in and self._fade_in.state() == QPropertyAnimation.State.Running:
            self._fade_in.stop()

        # Clean effects from any previous widgets
        for i in range(self.count()):
            w = self.widget(i)
            if w and w.graphicsEffect():
                w.setGraphicsEffect(None)

        current_widget = self.currentWidget()
        next_widget = self.widget(index)

        if current_widget is None or next_widget is None or current_widget == next_widget:
            super().setCurrentIndex(index)
            self._target_index = None
            return

        self._target_index = index

        opacity = QGraphicsOpacityEffect(current_widget)
        current_widget.setGraphicsEffect(opacity)
        self._fade_out = QPropertyAnimation(opacity, b"opacity")
        self._fade_out.setDuration(150)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.OutQuad)

        opacity_in = QGraphicsOpacityEffect(next_widget)
        next_widget.setGraphicsEffect(opacity_in)
        opacity_in.setOpacity(0.0)

        self._fade_in = QPropertyAnimation(opacity_in, b"opacity")
        self._fade_in.setDuration(150)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.Type.InQuad)

        def on_fade_out_finished():
            current_widget.setGraphicsEffect(None)
            super(FadedStackedWidget, self).setCurrentIndex(index)
            self._fade_in.start()

        def on_fade_in_finished():
            next_widget.setGraphicsEffect(None)
            self._target_index = None

        self._fade_out.finished.connect(on_fade_out_finished)
        self._fade_in.finished.connect(on_fade_in_finished)

        self._fade_out.start()

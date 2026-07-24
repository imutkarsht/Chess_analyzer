from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import QStackedWidget
from PyQt6.QtWidgets import QGraphicsOpacityEffect


class FadedStackedWidget(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current = 0

    def setCurrentIndex(self, index):
        if index == self._current:
            return

        current_widget = self.widget(self._current)
        next_widget = self.widget(index)

        if current_widget is None or next_widget is None:
            super().setCurrentIndex(index)
            self._current = index
            return

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

        _parent_set = QStackedWidget.setCurrentIndex
        _self = self
        _fade_in = self._fade_in

        def on_fade_out_finished():
            _parent_set(_self, index)
            _fade_in.start()

        def on_fade_in_finished():
            current_widget.setGraphicsEffect(None)
            next_widget.setGraphicsEffect(None)
            _self._current = index

        self._fade_out.finished.connect(on_fade_out_finished)
        self._fade_in.finished.connect(on_fade_in_finished)

        self._fade_out.start()

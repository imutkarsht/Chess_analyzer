"""
Modern, custom UI widgets for the settings panel.
"""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QSlider, QPushButton, QLabel, QLineEdit, QComboBox
from PyQt6.QtCore import Qt, pyqtSignal
from ...styles import Styles

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False


class ModernSliderCounter(QWidget):
    editingFinished = pyqtSignal()

    def __init__(self, min_val, max_val, step=1, value=0, is_float=False, parent=None):
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.is_float = is_float

        self._scale = 10 if is_float else 1

        self.setup_ui()
        self.setValue(value)

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # QSlider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(round(self.min_val * self._scale))
        self.slider.setMaximum(round(self.max_val * self._scale))
        self.slider.setSingleStep(round(self.step * self._scale))
        layout.addWidget(self.slider, stretch=1)

        # Counter layout: [-] [Value] [+]
        counter_layout = QHBoxLayout()
        counter_layout.setSpacing(4)
        counter_layout.setContentsMargins(0, 0, 0, 0)

        self.minus_btn = QPushButton("−")
        self.minus_btn.setFixedSize(26, 26)
        self.minus_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.value_label = QLabel("0")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setFixedWidth(40)

        self.plus_btn = QPushButton("+")
        self.plus_btn.setFixedSize(26, 26)
        self.plus_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        counter_layout.addWidget(self.minus_btn)
        counter_layout.addWidget(self.value_label)
        counter_layout.addWidget(self.plus_btn)

        layout.addLayout(counter_layout)

        # Signals
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.minus_btn.clicked.connect(self.decrement)
        self.plus_btn.clicked.connect(self.increment)

        self.slider.sliderReleased.connect(self.editingFinished.emit)
        self.minus_btn.clicked.connect(self.editingFinished.emit)
        self.plus_btn.clicked.connect(self.editingFinished.emit)

        self.refresh_styles()

    def _on_slider_changed(self, val):
        actual_val = val / self._scale
        self._raw_value = actual_val
        self._update_label(actual_val)

    def _update_label(self, val):
        if self.is_float:
            self.value_label.setText(f"{val:.1f}")
        else:
            self.value_label.setText(str(int(val)))

    def decrement(self):
        self.setValue(self.value() - self.step)

    def increment(self):
        self.setValue(self.value() + self.step)

    def value(self) -> float:
        return self.slider.value() / self._scale

    def setValue(self, val):
        try:
            fval = float(val)
        except (ValueError, TypeError):
            fval = self.min_val
        self._raw_value = fval
        clamped_val = max(self.min_val, min(self.max_val, fval))
        self.slider.blockSignals(True)
        self.slider.setValue(round(clamped_val * self._scale))
        self.slider.blockSignals(False)
        self._update_label(clamped_val)

    def text(self) -> str:
        val = getattr(self, "_raw_value", self.slider.value() / self._scale)
        if self.is_float:
            return f"{val:.1f}"
        else:
            return str(int(val))

    def setText(self, val_str: str):
        self.setValue(val_str)

    def setMaximumWidth(self, w: int):
        super().setMaximumWidth(w)

    def refresh_styles(self):
        slider_style = f"""
            QSlider::groove:horizontal {{
                height: 6px;
                background: {Styles.COLOR_BORDER};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {Styles.COLOR_ACCENT};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {Styles.COLOR_TEXT_PRIMARY};
                width: 16px;
                height: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {Styles.COLOR_ACCENT_HOVER};
            }}
        """
        self.slider.setStyleSheet(slider_style)

        btn_style = f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {Styles.COLOR_SURFACE};
                border-color: {Styles.COLOR_ACCENT};
                color: {Styles.COLOR_ACCENT};
            }}
            QPushButton:pressed {{
                background-color: {Styles.COLOR_ACCENT_SUBTLE};
                border-color: {Styles.COLOR_ACCENT};
            }}
        """
        self.minus_btn.setStyleSheet(btn_style)
        self.plus_btn.setStyleSheet(btn_style)

        self.value_label.setStyleSheet(f"""
            QLabel {{
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 13px;
                font-weight: bold;
                background: transparent;
            }}
        """)


class ModernHashComboBox(QComboBox):
    editingFinished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.addItems(["16", "32", "64", "128", "256", "512", "1024", "2048", "4096"])
        self.currentTextChanged.connect(lambda _: self.editingFinished.emit())

    def text(self) -> str:
        return self.currentText()

    def setText(self, val_str: str):
        val = val_str.strip()
        if val and self.findText(val) == -1:
            self.addItem(val)
        self.setCurrentText(val)

    def setMaximumWidth(self, w: int):
        super().setMaximumWidth(w)


class PasswordFieldWrapper(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("PasswordWrapper")
        self._visible = False
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 6, 0)
        layout.setSpacing(4)

        self.line_edit = QLineEdit()
        self.line_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.line_edit.setStyleSheet("border: none; background: transparent; padding: 10px 0px;")
        layout.addWidget(self.line_edit, stretch=1)

        self.toggle_btn = QPushButton()
        self.toggle_btn.setFixedSize(24, 24)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setStyleSheet("border: none; background: transparent; padding: 0px;")
        layout.addWidget(self.toggle_btn)

        self.toggle_btn.clicked.connect(self.toggle_visibility)

        self.line_edit.focusInEvent = lambda event: self._on_focus_changed(True, event)
        self.line_edit.focusOutEvent = lambda event: self._on_focus_changed(False, event)

        self.update_style(focused=False)
        self.update_icon()

    def _on_focus_changed(self, focused, event):
        if focused:
            QLineEdit.focusInEvent(self.line_edit, event)
        else:
            QLineEdit.focusOutEvent(self.line_edit, event)
        self.update_style(focused)

    @property
    def editingFinished(self):
        return self.line_edit.editingFinished

    def toggle_visibility(self):
        self._visible = not self._visible
        if self._visible:
            self.line_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.line_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.update_icon()

    def update_icon(self):
        if HAS_QTAWESOME:
            icon_name = "fa5s.eye-slash" if self._visible else "fa5s.eye"
            self.toggle_btn.setIcon(qta.icon(icon_name, color=Styles.COLOR_TEXT_SECONDARY))
        else:
            self.toggle_btn.setText("Hide" if self._visible else "Show")

    def update_style(self, focused=False):
        border_color = Styles.COLOR_ACCENT if focused else Styles.COLOR_BORDER
        super().setStyleSheet(f"""
            #PasswordWrapper {{
                border: 1px solid {border_color};
                border-radius: 4px;
                background-color: {Styles.COLOR_SURFACE_LIGHT};
            }}
        """)
        self.line_edit.setStyleSheet(f"""
            border: none;
            background: transparent;
            padding: 10px 0px;
            color: {Styles.COLOR_TEXT_PRIMARY};
        """)

    def text(self) -> str:
        return self.line_edit.text()

    def setText(self, t: str):
        self.line_edit.setText(t)

    def setPlaceholderText(self, t: str):
        self.line_edit.setPlaceholderText(t)

    def setEchoMode(self, mode):
        self.line_edit.setEchoMode(mode)

    def setEnabled(self, b: bool):
        self.line_edit.setEnabled(b)
        self.toggle_btn.setEnabled(b)

    def setStyleSheet(self, style: str):
        self.update_style(focused=self.line_edit.hasFocus())

    def setMaximumWidth(self, w: int):
        super().setMaximumWidth(w)

    def refresh_styles(self):
        self.update_style(focused=self.line_edit.hasFocus())
        self.update_icon()

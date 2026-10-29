"""
Modern, custom UI widgets for the settings panel.
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSlider, QWidget

from ...components import Button, ButtonSize, ButtonVariant
from ...styles import Styles


class ModernSliderCounter(QWidget):
    editingFinished = pyqtSignal()

    def __init__(
        self,
        min_val,
        max_val,
        step=1,
        value=0,
        is_float=False,
        parent=None,
        format_value=None,
    ):
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.is_float = is_float
        # Optional display formatter, e.g. thousands separators for large caps.
        self._format_value = format_value

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

        self.minus_btn = Button("−", ButtonVariant.FILLED, ButtonSize.SM, on_click=self.decrement)
        self.minus_btn.setFixedSize(26, 26)

        self.value_label = QLabel("0")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setFixedWidth(40)

        self.plus_btn = Button("+", ButtonVariant.FILLED, ButtonSize.SM, on_click=self.increment)
        self.plus_btn.setFixedSize(26, 26)

        counter_layout.addWidget(self.minus_btn)
        counter_layout.addWidget(self.value_label)
        counter_layout.addWidget(self.plus_btn)

        layout.addLayout(counter_layout)

        # Signals
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.minus_btn.clicked.connect(self.editingFinished.emit)
        self.plus_btn.clicked.connect(self.editingFinished.emit)

        self.refresh_styles()

    def _on_slider_changed(self, val):
        actual_val = val / self._scale
        self._raw_value = actual_val
        self._update_label(actual_val)

    def _update_label(self, val):
        if self._format_value is not None:
            self.value_label.setText(self._format_value(val))
        elif self.is_float:
            self.value_label.setText(f"{val:.1f}")
        else:
            self.value_label.setText(str(int(val)))

    def decrement(self):
        self.setValue(self.value() - self.step)

    def increment(self):
        self.setValue(self.value() + self.step)

    def value(self) -> float:
        return self.slider.value() / self._scale

    def set_maximum(self, max_val) -> None:
        """Change the upper bound (used when a token raises the import cap)."""
        self.max_val = max_val
        self.slider.setMaximum(round(max_val * self._scale))
        if self.value() > max_val:
            self.setValue(max_val)

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

        self.minus_btn.refresh_styles()
        self.plus_btn.refresh_styles()

        self.value_label.setStyleSheet(f"""
            QLabel {{
                color: {Styles.COLOR_TEXT_PRIMARY};
                font-size: 13px;
                font-weight: bold;
                background: transparent;
            }}
        """)




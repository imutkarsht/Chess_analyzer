"""Chess engine settings card."""

import os
import shutil
import subprocess

from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ...components.select import Select, SelectOption
from ...components.toast import ToastManager
from ...styles import Styles
from .components import PathField, SettingsBinder, SettingsForm
from .modern_widgets import ModernSliderCounter


class EngineSettings(QGroupBox):
    """Stockfish binary, thread count, and transposition-table size."""

    def __init__(self, config_manager, parent=None):
        super().__init__("Chess Engine", parent)
        self.config_manager = config_manager
        self.setStyleSheet(Styles.get_group_box_style())
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)

        self.form = SettingsForm(self)
        self.binder = SettingsBinder(self.config_manager, self.form, self)
        layout.addWidget(self.form)

        self._add_path_row()
        self._add_threads_row()
        self._add_hash_row()

        self.validate_engine_path()

    def _add_path_row(self):
        self.path_field = PathField(
            "Path to Stockfish executable...",
            browse_callback=self.browse_engine,
            parent=self,
        )
        self.path_input = self.path_field.line_edit
        self.browse_btn = self.path_field.browse_btn

        self.validation_label = QLabel()
        self.validation_label.setWordWrap(True)
        self.validation_label.setVisible(False)

        container = QWidget()
        box = QVBoxLayout(container)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(4)
        box.addWidget(self.path_field)
        box.addWidget(self.validation_label)

        self.binder.add("engine_path", self.path_field, container=container, hint="", width=None)
        self.path_input.editingFinished.connect(self.validate_engine_path)

    def _add_threads_row(self):
        max_threads = os.cpu_count() or 1
        recommended = min(max_threads, 4)
        self.threads_input = ModernSliderCounter(1, max_threads, step=1, parent=self)
        self.threads_input.setMaximumWidth(220)
        self.binder.add(
            "engine_threads",
            self.threads_input,
            hint=f"1–{max_threads} threads; recommended for this CPU: {recommended}",
            width=None,
        )

    def _add_hash_row(self):
        self.hash_input = Select(
            [
                SelectOption(str(size), size)
                for size in (16, 32, 64, 128, 256, 512, 1024, 2048, 4096)
            ],
            allow_custom=True,
            min_width=140,
        )
        self.binder.add(
            "engine_hash",
            self.hash_input,
            hint="16–4096 MB; 128 MB is the default.",
            width=140,
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate_engine_path(self):
        path = self.path_input.text().strip()
        if not path:
            self._set_validation("⚠️ No path specified", Styles.COLOR_MISTAKE)
            return

        is_in_path = shutil.which(path) is not None
        is_file = os.path.exists(path) and os.path.isfile(path)

        if not (is_in_path or is_file):
            self._set_validation(
                "❌ File does not exist or is not executable", Styles.COLOR_BLUNDER
            )
            return

        try:
            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            proc = subprocess.Popen(
                [path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creationflags,
            )

            stdout, _ = proc.communicate(input="uci\nquit\n", timeout=1.0)

            if "uciok" in stdout:
                name = "Stockfish"
                for line in stdout.split("\n"):
                    if line.startswith("id name "):
                        name = line[8:].strip()
                        break
                self._set_validation(f"✓ Valid UCI Engine: {name}", Styles.COLOR_BEST)
            else:
                self._set_validation(
                    "❌ Handshake failed (not a valid UCI engine)", Styles.COLOR_BLUNDER
                )
        except subprocess.TimeoutExpired:
            self._set_validation(
                "❌ Timeout: Engine failed to respond within 1s", Styles.COLOR_BLUNDER
            )
        except Exception as e:
            self._set_validation(f"❌ Failed to execute binary: {e}", Styles.COLOR_BLUNDER)

    def _set_validation(self, text: str, color: str) -> None:
        self.validation_label.setText(text)
        self.validation_label.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: bold; background: transparent;"
        )
        self.validation_label.setVisible(True)

    def browse_engine(self):
        filter_str = "Executables (*.exe);;All Files (*)" if os.name == "nt" else "All Files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Select Stockfish Binary", "", filter_str)
        if path:
            self.path_input.setText(path)
            self.path_input.editingFinished.emit()
            self.validate_engine_path()

    def _validated_threads(self):
        raw = self.threads_input.text().strip()
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = -1
        if value < 1:
            ToastManager.warning(
                self, "Engine Threads must be a positive integer (1 or more)."
            )
            return None, False
        return value, True

    def _validated_hash(self):
        raw = self.hash_input.settingValue()
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = -1
        if value < 16 or value > 4096:
            ToastManager.warning(
                self, "Engine Hash must be between 16 and 4096 MB."
            )
            return None, False
        return value, True

    # ------------------------------------------------------------------
    # Lifecycle hooks used by SettingsView
    # ------------------------------------------------------------------
    def reload_from_config(self):
        self.binder.load()
        self.validate_engine_path()

    def set_advanced_visible(self, visible):
        self.binder.set_advanced_visible(visible)

    def refresh_styles(self, *args, **kwargs):
        self.setStyleSheet(Styles.get_group_box_style())
        self.form.refresh_styles()
        self.path_input.setStyleSheet(Styles.get_input_style())
        self.browse_btn.refresh_styles()
        self.threads_input.refresh_styles()
        self.validate_engine_path()

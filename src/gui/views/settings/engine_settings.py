"""
Engine Settings group component.
"""
import os
import shutil
import subprocess
from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QFormLayout, QWidget, QComboBox, QFileDialog, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIntValidator, QDoubleValidator
from ...styles import Styles
from .helpers import create_icon_button

class EngineSettings(QGroupBox):
    def __init__(self, config_manager, parent=None):
        super().__init__("Chess Engine", parent)
        self.config_manager = config_manager
        self.setStyleSheet(Styles.get_group_box_style())
        
        self.setup_ui()

    def setup_ui(self):
        engine_layout = QVBoxLayout(self)
        engine_layout.setContentsMargins(20, 25, 20, 20)
        
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setText(self.config_manager.get("engine_path", ""))
        self.path_input.setPlaceholderText("Path to Stockfish executable...")
        self.path_input.setStyleSheet(Styles.get_input_style())
        path_layout.addWidget(self.path_input)
        
        self.browse_btn = create_icon_button("Browse", "fa5s.folder-open", self.browse_engine, self)
        path_layout.addWidget(self.browse_btn)
        
        engine_layout.addLayout(path_layout)

        # Validation status label
        self.validation_label = QLabel()
        self.validation_label.setStyleSheet("font-size: 12px; font-weight: bold; background: transparent; margin-top: 2px;")
        self.validation_label.setWordWrap(True)
        self.validation_label.setVisible(False)
        engine_layout.addWidget(self.validation_label)

        self.path_input.editingFinished.connect(self.validate_engine_path)
        
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.setContentsMargins(0, 0, 0, 0)

        field_label_style = (
            f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px; background: transparent;"
        )
        hint_style = (
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px; background: transparent;"
        )
        input_style = f"""
            QLineEdit {{
                padding: 6px 10px;
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 4px;
                background: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
            QLineEdit:focus {{
                border: 1px solid {Styles.COLOR_ACCENT};
            }}
        """
        combo_style = f"""
            QComboBox {{
                padding: 6px 12px;
                min-width: 80px;
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                font-size: 13px;
            }}
            QComboBox:hover {{
                border: 1px solid {Styles.COLOR_ACCENT};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
        """

        def _wrap(label_text, widget, hint_text):
            """Build a label + (input + hint) pair in form-layout style."""
            lbl = QLabel(label_text)
            lbl.setStyleSheet(field_label_style)

            wrapper = QWidget()
            wrapper.setStyleSheet("background: transparent; border: none;")
            box = QVBoxLayout(wrapper)
            box.setContentsMargins(0, 0, 0, 0)
            box.setSpacing(2)
            widget.setMaximumWidth(140)
            box.addWidget(widget)
            if hint_text:
                hint = QLabel(hint_text)
                hint.setStyleSheet(hint_style)
                box.addWidget(hint)
            return lbl, wrapper

        # --- Analysis Depth ---
        self.depth_combo = QComboBox()
        depth_values = [str(i) for i in range(10, 26)]
        self.depth_combo.addItems(depth_values)
        self.depth_combo.setCurrentText(str(self.config_manager.get("analysis_depth", 18)))
        self.depth_combo.setStyleSheet(combo_style)
        self.depth_combo.currentTextChanged.connect(self.change_analysis_depth)
        depth_lbl, depth_row = _wrap(
            "Analysis Depth:", self.depth_combo, "(Higher = more accurate but slower)"
        )
        form.addRow(depth_lbl, depth_row)

        # --- Multi-PV (alt lines per move) ---
        self.multi_pv_input = QLineEdit()
        self.multi_pv_input.setValidator(QIntValidator(1, 5, self.multi_pv_input))
        self.multi_pv_input.setText(str(self.config_manager.get("multi_pv", 1)))
        self.multi_pv_input.setStyleSheet(input_style)
        self.multi_pv_input.editingFinished.connect(self._on_multi_pv_committed)
        multi_pv_lbl, multi_pv_row = _wrap(
            "Multi-PV (alt lines):",
            self.multi_pv_input,
            "(1–5; 1 = best line only, recommended for laptops)",
        )
        form.addRow(multi_pv_lbl, multi_pv_row)

        # --- Live-Analysis time budget (seconds) ---
        self.live_time_input = QLineEdit()
        self.live_time_input.setValidator(QDoubleValidator(0.5, 10.0, 1, self.live_time_input))
        self.live_time_input.setText(str(self.config_manager.get("live_analysis_time", 2.0)))
        self.live_time_input.setStyleSheet(input_style)
        self.live_time_input.editingFinished.connect(self._on_live_time_committed)
        live_time_lbl, live_time_row = _wrap(
            "Live Analysis Time (s):",
            self.live_time_input,
            "(0.5–10.0; per-position CPU budget for the live panel)",
        )
        form.addRow(live_time_lbl, live_time_row)

        # --- Engine Threads ---
        cpu_count = os.cpu_count() or 1
        default_threads = min(cpu_count, 4)
        max_threads = max(32, cpu_count)

        self.threads_input = QLineEdit()
        self.threads_input.setValidator(QIntValidator(1, max_threads, self.threads_input))
        self.threads_input.setText(
            str(self.config_manager.get("engine_threads", default_threads))
        )
        self.threads_input.setStyleSheet(input_style)
        self.threads_input.editingFinished.connect(self._on_threads_committed)
        threads_lbl, threads_row = _wrap(
            "Engine Threads:",
            self.threads_input,
            f"(1–{max_threads} integer; recommended for this CPU: {default_threads})",
        )
        form.addRow(threads_lbl, threads_row)

        # --- Engine Hash ---
        self.hash_input = QLineEdit()
        self.hash_input.setValidator(QIntValidator(16, 4096, self.hash_input))
        self.hash_input.setText(str(self.config_manager.get("engine_hash", 64)))
        self.hash_input.setStyleSheet(input_style)
        self.hash_input.editingFinished.connect(self._on_hash_committed)
        hash_lbl, hash_row = _wrap(
            "Engine Hash (MB):",
            self.hash_input,
            "(16–4096 MB; 256 MB is a good default)",
        )
        form.addRow(hash_lbl, hash_row)

        engine_layout.addLayout(form)
        self.validate_engine_path()

    def validate_engine_path(self):
        path = self.path_input.text().strip()
        if not path:
            self.validation_label.setText("⚠️ No path specified")
            self.validation_label.setStyleSheet(f"color: {Styles.COLOR_MISTAKE}; font-size: 12px; font-weight: bold; background: transparent;")
            self.validation_label.setVisible(True)
            return
            
        is_in_path = shutil.which(path) is not None
        is_file = os.path.exists(path) and os.path.isfile(path)
        
        if not (is_in_path or is_file):
            self.validation_label.setText("❌ File does not exist or is not executable")
            self.validation_label.setStyleSheet(f"color: {Styles.COLOR_BLUNDER}; font-size: 12px; font-weight: bold; background: transparent;")
            self.validation_label.setVisible(True)
            return
            
        try:
            creationflags = 0
            if os.name == 'nt':
                creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
            proc = subprocess.Popen(
                [path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creationflags
            )
            
            stdout, _ = proc.communicate(input="uci\nquit\n", timeout=1.0)
            
            if "uciok" in stdout:
                name = "Stockfish"
                for line in stdout.split('\n'):
                    if line.startswith("id name "):
                        name = line[8:].strip()
                        break
                self.validation_label.setText(f"✓ Valid UCI Engine: {name}")
                self.validation_label.setStyleSheet(f"color: {Styles.COLOR_BEST}; font-size: 12px; font-weight: bold; background: transparent;")
            else:
                self.validation_label.setText("❌ Handshake failed (not a valid UCI engine)")
                self.validation_label.setStyleSheet(f"color: {Styles.COLOR_BLUNDER}; font-size: 12px; font-weight: bold; background: transparent;")
        except subprocess.TimeoutExpired:
            self.validation_label.setText("❌ Timeout: Engine failed to respond within 1s")
            self.validation_label.setStyleSheet(f"color: {Styles.COLOR_BLUNDER}; font-size: 12px; font-weight: bold; background: transparent;")
        except Exception as e:
            self.validation_label.setText(f"❌ Failed to execute binary: {str(e)}")
            self.validation_label.setStyleSheet(f"color: {Styles.COLOR_BLUNDER}; font-size: 12px; font-weight: bold; background: transparent;")
            
        self.validation_label.setVisible(True)

    def change_analysis_depth(self, depth_str):
        try:
            depth = int(depth_str)
            self.config_manager.config["analysis_depth"] = depth
        except ValueError:
            pass

    def _on_threads_committed(self):
        raw = self.threads_input.text().strip()
        if not raw:
            current = self.config_manager.get("engine_threads", min(os.cpu_count() or 1, 4))
            self.threads_input.setText(str(current))
            return
        threads, ok = self._validated_threads()
        if not ok:
            current = self.config_manager.get("engine_threads", 1)
            self.threads_input.setText(str(current))

    def _on_hash_committed(self):
        raw = self.hash_input.text().strip()
        if not raw:
            current = self.config_manager.get("engine_hash", 64)
            self.hash_input.setText(str(current))
            return
        hash_mb, ok = self._validated_hash()
        if not ok:
            current = self.config_manager.get("engine_hash", 64)
            self.hash_input.setText(str(current))

    def _on_multi_pv_committed(self):
        raw = self.multi_pv_input.text().strip()
        if not raw:
            current = self.config_manager.get("multi_pv", 1)
            self.multi_pv_input.setText(str(current))
            return
        try:
            value = int(raw)
        except ValueError:
            current = self.config_manager.get("multi_pv", 1)
            self.multi_pv_input.setText(str(current))
            return
        if not 1 <= value <= 5:
            current = self.config_manager.get("multi_pv", 1)
            self.multi_pv_input.setText(str(current))

    def _on_live_time_committed(self):
        raw = self.live_time_input.text().strip()
        if not raw:
            current = self.config_manager.get("live_analysis_time", 2.0)
            self.live_time_input.setText(str(current))
            return
        try:
            value = float(raw)
        except ValueError:
            current = self.config_manager.get("live_analysis_time", 2.0)
            self.live_time_input.setText(str(current))
            return
        if not 0.5 <= value <= 10.0:
            current = self.config_manager.get("live_analysis_time", 2.0)
            self.live_time_input.setText(str(current))

    def browse_engine(self):
        filter_str = "Executables (*.exe);;All Files (*)" if os.name == 'nt' else "All Files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Select Stockfish Binary", "", filter_str)
        if path:
            self.path_input.setText(path)
            self.validate_engine_path()

    def _validated_threads(self):
        raw = self.threads_input.text().strip()
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = -1
        if value < 1:
            QMessageBox.warning(
                self,
                "Invalid Threads",
                "Engine Threads must be a positive integer (1 or more).",
            )
            return None, False
        return value, True

    def _validated_hash(self):
        raw = self.hash_input.text().strip()
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = -1
        if value < 16 or value > 4096:
            QMessageBox.warning(
                self,
                "Invalid Hash",
                "Engine Hash must be between 16 and 4096 MB.",
            )
            return None, False
        return value, True

    def refresh_styles(self, combo_style, input_style, default_style):
        self.setStyleSheet(Styles.get_group_box_style())
        self.browse_btn.setStyleSheet(default_style)
        self.depth_combo.setStyleSheet(combo_style.replace("min-width: 150px;", "min-width: 80px;"))
        for widget in [self.multi_pv_input, self.live_time_input, self.threads_input, self.hash_input]:
            widget.setStyleSheet(input_style)
        self.path_input.setStyleSheet(input_style.replace("max-width: 140px;", ""))

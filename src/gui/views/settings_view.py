from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                             QLineEdit, QFileDialog, QGroupBox, QFormLayout, QMessageBox,
                             QScrollArea, QFrame, QComboBox, QGridLayout, QApplication, QLayout)
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QRect, QSize, QPoint
from PyQt6.QtGui import QIntValidator, QDoubleValidator
from ..styles import Styles
from ..gui_utils import create_button
from ...utils.config import ConfigManager
import os

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False


# ---------------------------------------------------------------------------
# MasonryLayout: Custom QLayout for dynamic, space-efficient column packing
# ---------------------------------------------------------------------------
class MasonryLayout(QLayout):
    def __init__(self, parent=None, margin=40, spacing=25):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def doLayout(self, rect, test_only):
        margins = self.contentsMargins()
        spacing = self._spacing
        
        available_width = rect.width() - margins.left() - margins.right()
        
        # We want columns to be at least 340px wide
        min_col_width = 340
        num_cols = max(1, available_width // min_col_width)
        num_cols = min(2, num_cols)
        
        if num_cols > 1:
            col_width = (available_width - (num_cols - 1) * spacing) // num_cols
        else:
            col_width = available_width

        col_heights = [rect.y() + margins.top()] * num_cols

        for item in self._items:
            widget = item.widget()
            if widget and not widget.isVisible():
                continue

            min_col_idx = col_heights.index(min(col_heights))
            
            x = rect.x() + margins.left() + min_col_idx * (col_width + spacing)
            y = col_heights[min_col_idx]
            
            h = item.heightForWidth(col_width) if item.hasHeightForWidth() else item.sizeHint().height()
            
            if not test_only:
                item.setGeometry(QRect(x, y, col_width, h))
                
            col_heights[min_col_idx] = y + h + spacing

        if col_heights:
            max_height = max(col_heights) - spacing + margins.bottom()
        else:
            max_height = rect.y() + margins.top() + margins.bottom()
            
        return max_height - rect.y()


# ---------------------------------------------------------------------------
# Pure (UI-free) helpers for the "Test LLM" workflow.
#
# Kept at module scope so they can be unit-tested without spinning up a
# QApplication. The QThread wrapper in SettingsView._test_llm_profile() is
# the only thing that actually blocks the UI on the network call.
# ---------------------------------------------------------------------------

def _test_llm_sync(profile: dict) -> tuple:
    """Run a one-shot chat completion against the given profile.

    Returns (success: bool, short_message: str, full_details: str).
    The 'short_message' is what the user sees inline in the status row;
    'full_details' is shown in the copyable error dialog on failure (and
    is empty on success).

    This function is intentionally Qt-free so it can be exercised by
    plain pytest tests; the GUI layer only adds threading on top.
    """
    try:
        from openai import OpenAI
    except ImportError:
        return (
            False,
            "✗ openai SDK missing",
            "The 'openai' package is not installed. Run "
            "'pip install openai' in your environment.",
        )

    # Local imports keep the module importable even when openai is missing.
    from ...backend.groq_service import PROVIDERS, GroqService

    p = profile or {}
    provider = GroqService._normalise_provider(p.get("provider", "groq"))
    preset = PROVIDERS.get(provider, PROVIDERS["custom"])
    base_url = GroqService._normalise_base_url(
        p.get("base_url") or preset.get("base_url", "")
    )
    api_key = (p.get("api_key") or "not-needed").strip()
    model = (p.get("model") or preset.get("default_model", "")).strip()

    requires_key = preset.get("requires_key", True)
    if requires_key and not p.get("api_key"):
        return (
            False,
            "✗ API key required",
            "Enter a real API key in the field above.",
        )
    if not base_url:
        return (
            False,
            "✗ No base URL set",
            "Set a base URL (preset or custom).",
        )
    if not model:
        return (False, "✗ No model set", "Set a model name.")

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user",
                       "content": "Reply with exactly: OK"}],
            max_tokens=10,
        )
        # We deliberately discard the response body — reasoning models can
        # leak chain-of-thought tokens (e.g. "<think>…") into the reply,
        # and a successful call returning content is the only signal we
        # need: the profile is wired correctly.
        return (True, "✓ Connected", "")
    except Exception as exc:
        exc_type = type(exc).__name__
        full = f"{exc_type}: {exc}"
        # Authentication errors are the most common cause of a 'Test LLM'
        # failure; the raw class+message is technically correct but
        # unhelpful for users who just want to know "is my key wrong?".
        try:
            from openai import AuthenticationError, PermissionDeniedError
            if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
                return (
                    False,
                    "✗ Authentication failed",
                    "The API key was rejected by the provider.\n\n"
                    f"Details: {full}\n\n"
                    "Check the key in the API Configuration above "
                    "and the provider's dashboard.",
                )
        except ImportError:
            pass
        return (False, f"✗ {full[:80]}", full)

class SettingsView(QWidget):
    engine_path_changed = pyqtSignal(str)
    engine_settings_changed = pyqtSignal()  # emitted when Threads/Hash change
    llm_config_changed = pyqtSignal()   # emitted after LLM settings are saved
    usernames_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        
        # Main layout for the widget itself (contains scroll area)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND}; border: none;")
        
        # Container for content inside scroll area
        self.content_container = QWidget()
        self.content_container.setStyleSheet(f"background-color: {Styles.COLOR_BACKGROUND};")
        
        # Use MasonryLayout for 2-column/3-column dynamic design
        self.container_layout = MasonryLayout(self.content_container, margin=40, spacing=25)
        
        self.scroll_area.setWidget(self.content_container)
        main_layout.addWidget(self.scroll_area)
        
        # Use centralized group box style
        self.group_style = Styles.get_group_box_style()

        # --- LEFT COLUMN (Column 0) ---

        # 1. Engine Settings
        engine_title = self._create_section_title("Chess Engine", "fa5s.cogs")
        self.engine_group = QGroupBox()
        self.engine_group.setTitle(engine_title)
        self.engine_group.setStyleSheet(self.group_style)
        engine_layout = QVBoxLayout(self.engine_group)
        engine_layout.setContentsMargins(20, 25, 20, 20)
        
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setText(self.config_manager.get("engine_path", ""))
        self.path_input.setPlaceholderText("Path to Stockfish executable...")
        self.path_input.setStyleSheet(Styles.get_input_style())
        path_layout.addWidget(self.path_input)
        
        self.browse_btn = self._create_icon_button("Browse", "fa5s.folder-open", self.browse_engine)
        path_layout.addWidget(self.browse_btn)
        
        engine_layout.addLayout(path_layout)
        
        # All three engine controls (Depth, Threads, Hash) live in a
        # single QFormLayout so the labels sit in one column on the
        # left and the inputs in one column on the right. The hint
        # text is rendered as a small secondary label below the
        # corresponding input via addRow(label, container) where the
        # container is a small QVBoxLayout.
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
        
        self.save_engine_btn = self._create_icon_button("Save Settings", "fa5s.save", self.save_engine_path, primary=True)
        engine_layout.addWidget(self.save_engine_btn, alignment=Qt.AlignmentFlag.AlignRight)
        
        self.container_layout.addWidget(self.engine_group)
        
        # 2. API Settings — profile-based LLM configuration
        from ...backend.groq_service import PROVIDERS as LLM_PROVIDERS
        self._llm_providers = LLM_PROVIDERS
        self._loading_profile = False   # suppresses feedback loops during load

        self.api_group = QGroupBox("API Configuration")
        self.api_group.setStyleSheet(self.group_style)
        api_layout = QVBoxLayout(self.api_group)
        api_layout.setContentsMargins(20, 25, 20, 20)
        api_layout.setSpacing(10)

        lbl_style = f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px; background: transparent;"
        _combo_style = f"""
            QComboBox {{
                padding: 6px 12px;
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px; font-size: 13px;
            }}
            QComboBox:hover {{ border: 1px solid {Styles.COLOR_ACCENT}; }}
            QComboBox::drop-down {{ border: none; padding-right: 8px; }}
        """
        _icon_btn_style = f"""
            QPushButton {{
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                font-size: 16px; font-weight: bold;
                min-width: 28px; max-width: 28px;
                min-height: 28px; max-height: 28px;
            }}
            QPushButton:hover {{ border-color: {Styles.COLOR_ACCENT}; }}
        """

        # --- Profile selector row ---
        prof_row = QHBoxLayout()
        lbl_prof = QLabel("LLM Profile:")
        lbl_prof.setStyleSheet(lbl_style)
        lbl_prof.setFixedWidth(88)
        prof_row.addWidget(lbl_prof)

        self.llm_profile_combo = QComboBox()
        self.llm_profile_combo.setStyleSheet(_combo_style)
        self.llm_profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        prof_row.addWidget(self.llm_profile_combo, stretch=1)

        self.llm_add_btn = QPushButton("+")
        self.llm_add_btn.setStyleSheet(_icon_btn_style)
        self.llm_add_btn.setToolTip("New profile")
        self.llm_add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.llm_add_btn.clicked.connect(self._new_llm_profile)
        prof_row.addWidget(self.llm_add_btn)

        self.llm_del_btn = QPushButton("−")
        self.llm_del_btn.setStyleSheet(_icon_btn_style.replace(
            Styles.COLOR_TEXT_PRIMARY, Styles.COLOR_BLUNDER))
        self.llm_del_btn.setToolTip("Delete profile")
        self.llm_del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.llm_del_btn.clicked.connect(self._delete_llm_profile)
        prof_row.addWidget(self.llm_del_btn)

        api_layout.addLayout(prof_row)

        # --- Thin divider ---
        _div = QFrame(); _div.setFrameShape(QFrame.Shape.HLine)
        _div.setStyleSheet(f"color: {Styles.COLOR_BORDER};")
        api_layout.addWidget(_div)

        # --- Profile editor form ---
        pf = QFormLayout()
        pf.setSpacing(10)
        pf.setContentsMargins(0, 0, 0, 0)
        pf.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)


        lbl_pname = QLabel("Name:"); lbl_pname.setStyleSheet(lbl_style)
        self.llm_profile_name = QLineEdit()
        self.llm_profile_name.setStyleSheet(Styles.get_input_style())
        pf.addRow(lbl_pname, self.llm_profile_name)

        lbl_prov = QLabel("Provider:"); lbl_prov.setStyleSheet(lbl_style)
        self.llm_provider_combo = QComboBox()
        for pkey, pmeta in LLM_PROVIDERS.items():
            self.llm_provider_combo.addItem(pmeta["label"], userData=pkey)
        self.llm_provider_combo.setStyleSheet(_combo_style)
        self.llm_provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        pf.addRow(lbl_prov, self.llm_provider_combo)

        self.lbl_llm_key = QLabel("API Key:"); self.lbl_llm_key.setStyleSheet(lbl_style)
        self.llm_key_input = QLineEdit()
        self.llm_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.llm_key_input.setStyleSheet(Styles.get_input_style())
        pf.addRow(self.lbl_llm_key, self.llm_key_input)

        lbl_model = QLabel("Model:"); lbl_model.setStyleSheet(lbl_style)
        self.llm_model_input = QLineEdit()
        self.llm_model_input.setStyleSheet(Styles.get_input_style())
        pf.addRow(lbl_model, self.llm_model_input)

        self.lbl_llm_url = QLabel("Base URL:"); self.lbl_llm_url.setStyleSheet(lbl_style)
        self.llm_url_input = QLineEdit()
        self.llm_url_input.setPlaceholderText("http://localhost:1234/v1")
        self.llm_url_input.setStyleSheet(Styles.get_input_style())
        pf.addRow(self.lbl_llm_url, self.llm_url_input)

        api_layout.addLayout(pf)

        # --- Save / Activate / Test buttons ---
        act_row = QHBoxLayout()
        self.llm_test_btn = self._create_icon_button(
            "Test LLM", "fa5s.plug", self._test_llm_profile)
        act_row.addWidget(self.llm_test_btn)
        act_row.addStretch()
        self.llm_save_profile_btn = self._create_icon_button(
            "Save Profile", "fa5s.save", self._save_llm_profile)
        act_row.addWidget(self.llm_save_profile_btn)
        self.llm_activate_btn = self._create_icon_button(
            "Set as Active", "fa5s.check-circle", self._activate_llm_profile, primary=True)
        act_row.addWidget(self.llm_activate_btn)
        api_layout.addLayout(act_row)

        # Status area: active-profile label + test result on the same row
        status_row = QHBoxLayout()
        self.llm_active_label = QLabel()
        self.llm_active_label.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px; background: transparent;")
        status_row.addWidget(self.llm_active_label)
        status_row.addStretch()
        self.llm_test_result = QLabel()
        self.llm_test_result.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px; background: transparent;")
        status_row.addWidget(self.llm_test_result)
        api_layout.addLayout(status_row)

        # --- Lichess token (separate section) ---
        _div2 = QFrame(); _div2.setFrameShape(QFrame.Shape.HLine)
        _div2.setStyleSheet(f"color: {Styles.COLOR_BORDER};")
        api_layout.addWidget(_div2)

        lf = QFormLayout(); lf.setSpacing(10); lf.setContentsMargins(0, 0, 0, 0)
        lf.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        lbl_lichess = QLabel("Lichess API Token:"); lbl_lichess.setStyleSheet(lbl_style)
        self.lichess_token_input = QLineEdit()
        self.lichess_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.lichess_token_input.setText(self.config_manager.get("lichess_token", ""))
        self.lichess_token_input.setStyleSheet(Styles.get_input_style())
        lf.addRow(lbl_lichess, self.lichess_token_input)
        api_layout.addLayout(lf)

        tok_row = QHBoxLayout(); tok_row.addStretch()
        self.save_api_btn = self._create_icon_button(
            "Save Token", "fa5s.key", self._save_lichess_token, primary=True)
        tok_row.addWidget(self.save_api_btn)
        api_layout.addLayout(tok_row)

        self.container_layout.addWidget(self.api_group)

        # Populate profiles and select the active one
        self._reload_profile_combo()

        # 3. Username Settings
        self.username_group = QGroupBox("Player Usernames")
        self.username_group.setStyleSheet(self.group_style)
        username_layout = QFormLayout(self.username_group)
        username_layout.setContentsMargins(20, 25, 20, 20)
        username_layout.setSpacing(15)
        username_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.chesscom_input = QLineEdit()
        self.chesscom_input.setText(self.config_manager.get("chesscom_username", ""))
        self.chesscom_input.setPlaceholderText("Chess.com Username")
        self.chesscom_input.setStyleSheet(Styles.get_input_style())
        
        self.lichess_input = QLineEdit()
        self.lichess_input.setText(self.config_manager.get("lichess_username", ""))
        self.lichess_input.setPlaceholderText("Lichess.org Username")
        self.lichess_input.setStyleSheet(Styles.get_input_style())

        lbl_chesscom = QLabel("Chess.com:")
        lbl_chesscom.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px; background: transparent;")
        
        lbl_lichess_user = QLabel("Lichess.org:")
        lbl_lichess_user.setStyleSheet(f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 13px; background: transparent;")

        username_layout.addRow(lbl_chesscom, self.chesscom_input)
        username_layout.addRow(lbl_lichess_user, self.lichess_input)

        self.save_usernames_btn = self._create_icon_button("Save Usernames", "fa5s.user-check", self.save_usernames, primary=True)

        btn_wrapper_user = QHBoxLayout()
        btn_wrapper_user.addStretch()
        btn_wrapper_user.addWidget(self.save_usernames_btn)
        username_layout.addRow(btn_wrapper_user)

        self.container_layout.addWidget(self.username_group)
        
        # --- RIGHT COLUMN (Column 1) ---
        
        # 4. Appearance Settings
        self.appearance_group = QGroupBox("Appearance")
        self.appearance_group.setStyleSheet(self.group_style)
        appearance_layout = QFormLayout(self.appearance_group)
        appearance_layout.setContentsMargins(20, 30, 20, 20)
        appearance_layout.setSpacing(16)
        appearance_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        appearance_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        appearance_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        
        # Common label style for this section
        label_style = f"color: {Styles.COLOR_TEXT_PRIMARY}; font-size: 14px; background: transparent;"
        combo_style = f"""
            QComboBox {{
                padding: 8px 12px;
                min-width: 120px;
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
                border: 1px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                font-size: 14px;
            }}
            QComboBox:hover {{
                border: 1px solid {Styles.COLOR_ACCENT};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
        """
        
        # Board Theme Selector
        theme_lbl = QLabel("Board Theme:")
        theme_lbl.setStyleSheet(label_style)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(Styles.BOARD_THEMES.keys()))
        current_theme = self.config_manager.get("board_theme", "Green")
        self.theme_combo.setCurrentText(current_theme)
        self.theme_combo.setStyleSheet(combo_style)
        self.theme_combo.currentTextChanged.connect(self.change_board_theme)
        
        appearance_layout.addRow(theme_lbl, self.theme_combo)

        # Piece Style Selector
        from ..board.piece_themes import get_piece_theme_names
        piece_lbl = QLabel("Piece Style:")
        piece_lbl.setStyleSheet(label_style)
        
        self.piece_combo = QComboBox()
        self.piece_combo.addItems(get_piece_theme_names())
        current_piece_theme = self.config_manager.get("piece_theme", "Standard")
        self.piece_combo.setCurrentText(current_piece_theme)
        self.piece_combo.setStyleSheet(combo_style)
        self.piece_combo.currentTextChanged.connect(self.change_piece_theme)
        
        appearance_layout.addRow(piece_lbl, self.piece_combo)

        # Accent Color
        color_lbl = QLabel("Accent Color:")
        color_lbl.setStyleSheet(label_style)
        
        self.color_btn = self._create_icon_button("Change Color", "fa5s.palette", self.change_accent_color)
        
        appearance_layout.addRow(color_lbl, self.color_btn)
        
        self.container_layout.addWidget(self.appearance_group)
        
        # 5. Data Management
        self.data_group = QGroupBox("Data Management")
        self.data_group.setStyleSheet(self.group_style)
        data_layout = QGridLayout(self.data_group)
        data_layout.setContentsMargins(20, 25, 20, 20)
        data_layout.setSpacing(12)
        
        self.clear_cache_btn = self._create_icon_button("Clear Cache", "fa5s.broom", self.clear_cache)
        data_layout.addWidget(self.clear_cache_btn, 0, 0)
        
        self.clear_data_btn = self._create_icon_button("Reset All Data", "fa5s.trash-alt", self.clear_all_data, danger=True)
        data_layout.addWidget(self.clear_data_btn, 0, 1)
        
        self.container_layout.addWidget(self.data_group)

        # 6. Official Website Section
        self.website_group = QGroupBox("Links")
        self.website_group.setStyleSheet(self.group_style)
        website_layout = QHBoxLayout(self.website_group)
        website_layout.setContentsMargins(20, 25, 20, 20)
        website_layout.setSpacing(12)

        self.website_btn = self._create_icon_button("Visit Website", "fa5s.globe", self.open_website)
        website_layout.addWidget(self.website_btn)

        self.feedback_btn = self._create_icon_button("Feedback", "fa5s.comment-dots", self.open_feedback)
        website_layout.addWidget(self.feedback_btn)
        
        self.update_btn = self._create_icon_button("Check for Updates", "fa5s.sync-alt", self.check_for_updates)
        website_layout.addWidget(self.update_btn)

        self.container_layout.addWidget(self.website_group)


    def refresh_styles(self):
        """Re-applies styles to all widgets."""
        self.group_style = f"""
            QGroupBox {{ 
                font-weight: bold; 
                font-size: 16px; 
                color: {Styles.COLOR_TEXT_PRIMARY}; 
                border: 1px solid {Styles.COLOR_BORDER}; 
                border-radius: 8px; 
                margin-top: 10px; 
                background-color: {Styles.COLOR_SURFACE};
            }} 
            QGroupBox::title {{ 
                subcontrol-origin: margin; 
                left: 15px; 
                padding: 0 5px; 
            }}
        """
        self.engine_group.setStyleSheet(self.group_style)
        self.api_group.setStyleSheet(self.group_style)
        self.username_group.setStyleSheet(self.group_style)
        self.appearance_group.setStyleSheet(self.group_style)
        self.data_group.setStyleSheet(self.group_style)
        self.website_group.setStyleSheet(self.group_style)
        
        self.browse_btn.setStyleSheet(Styles.get_control_button_style())
        self.save_engine_btn.setStyleSheet(Styles.get_button_style())
        self.save_api_btn.setStyleSheet(Styles.get_button_style())
        self.save_usernames_btn.setStyleSheet(Styles.get_button_style())
        self.color_btn.setStyleSheet(Styles.get_control_button_style())
        self.clear_cache_btn.setStyleSheet(Styles.get_control_button_style())
        self.clear_data_btn.setStyleSheet(Styles.get_control_button_style())
        self.website_btn.setStyleSheet(Styles.get_control_button_style())
        self.feedback_btn.setStyleSheet(Styles.get_control_button_style())

    def _create_section_title(self, text, icon_name):
        """Create a section title string (icons applied via button icons)."""
        return text  # Keep title simple, icons on buttons
    
    def _create_icon_button(self, text, icon_name, callback, danger=False, primary=False):
        """Create a styled button with qtawesome icon."""
        btn = QPushButton(f"  {text}")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        if HAS_QTAWESOME:
            if danger:
                icon_color = Styles.COLOR_BLUNDER
            elif primary:
                icon_color = "#ffffff"
            else:
                icon_color = Styles.COLOR_TEXT_SECONDARY
            btn.setIcon(qta.icon(icon_name, color=icon_color))
        
        if danger:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {Styles.COLOR_BLUNDER};
                    border: 1px solid {Styles.COLOR_BLUNDER};
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {Styles.COLOR_BLUNDER};
                    color: white;
                }}
            """)
        elif primary:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Styles.COLOR_ACCENT};
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-size: 13px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {Styles.COLOR_ACCENT_HOVER};
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Styles.COLOR_SURFACE_LIGHT};
                    color: {Styles.COLOR_TEXT_PRIMARY};
                    border: 1px solid {Styles.COLOR_BORDER};
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {Styles.COLOR_SURFACE};
                    border-color: {Styles.COLOR_ACCENT};
                }}
            """)
        
        btn.clicked.connect(callback)
        return btn

    def change_accent_color(self):
        from PyQt6.QtWidgets import QColorDialog
        color = QColorDialog.getColor(initial=QColor(Styles.COLOR_ACCENT), parent=self, title="Select Accent Color")
        
        if color.isValid():
            # Update Styles
            Styles.set_accent_color(color.name())
            
            # Save to config (optional, but good practice)
            self.config_manager.set("accent_color", color.name())
            
            # Trigger global refresh
            # We need to access the main window to refresh
            window = self.window()
            if hasattr(window, "refresh_theme"):
                window.refresh_theme()

    def _update_config_and_refresh(self, key, value):
        """Common helper for config updates that require theme refresh."""
        self.config_manager.set(key, value)
        window = self.window()
        if hasattr(window, "refresh_theme"):
            window.refresh_theme()

    def change_board_theme(self, theme_name):
        self._update_config_and_refresh("board_theme", theme_name)

    def change_piece_theme(self, theme_name):
        self._update_config_and_refresh("piece_theme", theme_name)

    def change_analysis_depth(self, depth_str):
        """Changes the analysis depth setting. Takes effect on next analysis."""
        try:
            depth = int(depth_str)
            self.config_manager.set("analysis_depth", depth)
        except ValueError:
            pass  # Ignore invalid values

    def _on_threads_committed(self):
        """Auto-commit Threads on Enter / focus loss. The line edit's
        QIntValidator already rejects non-digits, but we still defend
        against empty input here so the user gets a friendly message
        instead of a silent ignore."""
        raw = self.threads_input.text().strip()
        if not raw:
            # empty: revert to the previously persisted value
            current = self.config_manager.get("engine_threads", min(os.cpu_count() or 1, 4))
            self.threads_input.setText(str(current))
            return
        threads, ok = self._validated_threads()
        if not ok:
            # restore the last good value to keep the field consistent
            current = self.config_manager.get("engine_threads", 1)
            self.threads_input.setText(str(current))
            return
        if self.config_manager.get("engine_threads") != threads:
            self.config_manager.set("engine_threads", threads)
            self.engine_settings_changed.emit()

    def _on_hash_committed(self):
        """Auto-commit Hash on Enter / focus loss. See _on_threads_committed."""
        raw = self.hash_input.text().strip()
        if not raw:
            current = self.config_manager.get("engine_hash", 64)
            self.hash_input.setText(str(current))
            return
        hash_mb, ok = self._validated_hash()
        if not ok:
            current = self.config_manager.get("engine_hash", 64)
            self.hash_input.setText(str(current))
            return
        if self.config_manager.get("engine_hash") != hash_mb:
            self.config_manager.set("engine_hash", hash_mb)
            self.engine_settings_changed.emit()

    def _on_multi_pv_committed(self):
        """Auto-commit Multi-PV. 1 = best line only, 5 = five top lines.

        Higher values multiply the search-tree work roughly linearly, so
        we keep the validator bounded and surface the persisted default
        when the field is empty or out of range.
        """
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
        # The QIntValidator already constrains 1..5, but defend anyway.
        if not 1 <= value <= 5:
            current = self.config_manager.get("multi_pv", 1)
            self.multi_pv_input.setText(str(current))
            return
        if self.config_manager.get("multi_pv") != value:
            self.config_manager.set("multi_pv", value)

    def _on_live_time_committed(self):
        """Auto-commit Live-Analysis time budget (seconds).

        Bounds 0.5..10.0. The previous default of an infinite search
        (Limit(depth=None)) was the root cause of laptop overheating —
        see issue #5. A 2-second budget gives the engine a finite
        window to deepen the analysis, then releases the CPU.
        """
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
            return
        if self.config_manager.get("live_analysis_time") != value:
            self.config_manager.set("live_analysis_time", value)

    def browse_engine(self):
        filter_str = "Executables (*.exe);;All Files (*)" if os.name == 'nt' else "All Files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Select Stockfish Binary", "", filter_str)
        if path:
            self.path_input.setText(path)

    def save_engine_path(self):
        """Save every engine setting (path, threads, hash) at once.

        The button now reads "Save Settings" and serves as the explicit
        commit point for the Threads/Hash fields. Individual fields
        also auto-commit on editingFinished, so users can change them
        and tab away without clicking the button — but clicking this
        button persists all three and shows a single confirmation.
        """
        path = self.path_input.text()
        if not path:
            QMessageBox.warning(self, "Error", "Please enter a valid path.")
            return

        threads, threads_ok = self._validated_threads()
        hash_mb, hash_ok = self._validated_hash()

        if not threads_ok or not hash_ok:
            return  # the helpers already show an error message

        path_changed = self.config_manager.get("engine_path") != path
        threads_changed = self.config_manager.get("engine_threads") != threads
        hash_changed = self.config_manager.get("engine_hash") != hash_mb

        self.config_manager.set("engine_path", path)
        self.config_manager.set("engine_threads", threads)
        self.config_manager.set("engine_hash", hash_mb)

        if path_changed:
            self.engine_path_changed.emit(path)
        if threads_changed or hash_changed:
            self.engine_settings_changed.emit()

        QMessageBox.information(
            self,
            "Saved",
            f"Engine settings saved.\n"
            f"Path: {path}\n"
            f"Threads: {threads}\n"
            f"Hash: {hash_mb} MB",
        )

    def _validated_threads(self):
        """Return (value, ok) for the Threads field, or (None, False) on error."""
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
        """Return (value, ok) for the Hash field, or (None, False) on error."""
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

    # ------------------------------------------------------------------
    # Profile management helpers
    # ------------------------------------------------------------------

    def _reload_profile_combo(self) -> None:
        """Rebuild the profile combo from config and select the active profile."""
        self._loading_profile = True
        self.llm_profile_combo.blockSignals(True)
        self.llm_profile_combo.clear()
        profiles = self.config_manager.get_profiles()
        active_name = self.config_manager.get("llm_active_profile", "")
        select_idx = 0
        for i, p in enumerate(profiles):
            name = p.get("name", f"Profile {i+1}")
            self.llm_profile_combo.addItem(name)
            if name == active_name:
                select_idx = i
        self.llm_profile_combo.blockSignals(False)
        self.llm_profile_combo.setCurrentIndex(select_idx)
        # _on_profile_selected is suppressed by the blockSignals above, so
        # we also load the form explicitly — otherwise the form fields
        # would stay empty until the user clicks the combo.
        if 0 <= select_idx < len(profiles):
            self._load_profile_into_form(profiles[select_idx])
        self._loading_profile = False

    def _on_profile_selected(self, index: int) -> None:
        """Load the selected profile's data into the editor form."""
        if self._loading_profile:
            return
        profiles = self.config_manager.get_profiles()
        if 0 <= index < len(profiles):
            self._load_profile_into_form(profiles[index])

    def _load_profile_into_form(self, profile: dict) -> None:
        """Fill editor fields from a profile dict without triggering saves."""
        self._loading_profile = True
        self.llm_profile_name.setText(profile.get("name", ""))

        provider = profile.get("provider", "groq")
        idx = self.llm_provider_combo.findData(provider)
        self.llm_provider_combo.setCurrentIndex(max(0, idx))

        self.llm_key_input.setText(profile.get("api_key", ""))
        self.llm_model_input.setText(profile.get("model", ""))
        self.llm_url_input.setText(profile.get("base_url", ""))
        self._loading_profile = False

        self._on_provider_changed()  # update field visibility / placeholders
        self._update_active_label()

    def _on_provider_changed(self, _index=None) -> None:
        """Adjust field placeholders and visibility for the selected provider.

        The API key field and the Base URL field are always visible — the
        placeholders convey defaults, but the user must always be able to
        override them (e.g. for region-specific endpoints).
        """
        if self._loading_profile:
            return
        provider_key = self.llm_provider_combo.currentData() or "groq"
        preset = self._llm_providers.get(provider_key, {})

        # Always enabled — placeholder conveys whether key is required
        self.llm_key_input.setEnabled(True)
        self.lbl_llm_key.setEnabled(True)
        self.llm_key_input.setPlaceholderText(preset.get("key_placeholder", ""))

        self.llm_model_input.setPlaceholderText(preset.get("model_placeholder", ""))

        # Base URL field: always visible, prefilled with preset URL for non-custom.
        # Only overwrite the URL when switching provider AND the current value
        # matches an existing preset (i.e. user hasn't customised it yet) or is
        # empty — otherwise we would clobber the user's manual override.
        self.lbl_llm_url.setVisible(True)
        self.llm_url_input.setVisible(True)
        current_url = self.llm_url_input.text().strip()
        known_preset_urls = {
            meta.get("base_url", "") for meta in self._llm_providers.values()
        }
        if not current_url or current_url in known_preset_urls:
            self.llm_url_input.setText(preset.get("base_url", ""))

    def _update_active_label(self) -> None:
        active = self.config_manager.get("llm_active_profile", "")
        if active:
            self.llm_active_label.setText(f"Active: \"{active}\"")
        else:
            self.llm_active_label.setText("")

    def _current_profile_dict(self) -> dict:
        """Build a profile dict from the current form fields."""
        from ...backend.groq_service import GroqService
        provider = self.llm_provider_combo.currentData() or "groq"
        provider = GroqService._normalise_provider(provider)
        preset = self._llm_providers.get(provider, {})
        base_url = self.llm_url_input.text().strip()
        if not base_url and provider != "custom":
            base_url = preset.get("base_url", "")
        # Strip a trailing /chat/completions so the OpenAI SDK can append it
        base_url = GroqService._normalise_base_url(base_url)
        return {
            "name":     self.llm_profile_name.text().strip(),
            "provider": provider,
            "api_key":  self.llm_key_input.text().strip(),
            "model":    self.llm_model_input.text().strip() or preset.get("default_model", ""),
            "base_url": base_url,
        }

    def _save_llm_profile(self) -> None:
        """Persist edits to the selected profile without changing the active one."""
        profiles = self.config_manager.get_profiles()
        idx = self.llm_profile_combo.currentIndex()
        if not (0 <= idx < len(profiles)):
            return

        old_name = profiles[idx].get("name", "")
        new_profile = self._current_profile_dict()
        new_name = new_profile["name"]

        if not new_name:
            QMessageBox.warning(self, "Validation", "Profile name cannot be empty.")
            return

        # Check uniqueness (allow keeping the same name)
        if new_name != old_name and any(p["name"] == new_name for p in profiles):
            QMessageBox.warning(self, "Validation", f"A profile named \"{new_name}\" already exists.")
            return

        profiles[idx] = new_profile

        # If the active profile was renamed, follow the rename
        active = self.config_manager.get("llm_active_profile", "")
        new_active = new_name if active == old_name else active

        self.config_manager.set_profiles(profiles, new_active)
        self._reload_profile_combo()
        QMessageBox.information(self, "Saved", f"Profile \"{new_name}\" saved.")

    def _activate_llm_profile(self) -> None:
        """Save edits and set this profile as the active (applied) one."""
        profiles = self.config_manager.get_profiles()
        idx = self.llm_profile_combo.currentIndex()
        if not (0 <= idx < len(profiles)):
            return

        old_name = profiles[idx].get("name", "")
        new_profile = self._current_profile_dict()
        new_name = new_profile["name"]

        if not new_name:
            QMessageBox.warning(self, "Validation", "Profile name cannot be empty.")
            return
        if new_name != old_name and any(p["name"] == new_name for p in profiles):
            QMessageBox.warning(self, "Validation", f"A profile named \"{new_name}\" already exists.")
            return

        profiles[idx] = new_profile
        self.config_manager.set_profiles(profiles, new_name)
        self.llm_config_changed.emit()   # tell MainWindow to reload services
        self._reload_profile_combo()
        QMessageBox.information(self, "Activated", f"Profile \"{new_name}\" is now active.")

    def _new_llm_profile(self) -> None:
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New LLM Profile", "Profile name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        profiles = self.config_manager.get_profiles()
        if any(p["name"] == name for p in profiles):
            QMessageBox.warning(self, "Exists", f"A profile named \"{name}\" already exists.")
            return
        profiles.append({
            "name": name, "provider": "groq", "api_key": "",
            "model": "llama-3.3-70b-versatile", "base_url": "",
        })
        self.config_manager.set_profiles(profiles)
        self._reload_profile_combo()
        # Select the newly added profile
        self.llm_profile_combo.setCurrentIndex(len(profiles) - 1)

    def _delete_llm_profile(self) -> None:
        profiles = self.config_manager.get_profiles()
        if len(profiles) <= 1:
            QMessageBox.warning(self, "Cannot Delete", "You must keep at least one profile.")
            return
        idx = self.llm_profile_combo.currentIndex()
        if not (0 <= idx < len(profiles)):
            return
        name = profiles[idx].get("name", "")
        reply = QMessageBox.question(self, "Delete Profile",
                                     f"Delete profile \"{name}\"?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        profiles.pop(idx)
        active = self.config_manager.get("llm_active_profile", "")
        if active == name:
            active = profiles[0]["name"]
        self.config_manager.set_profiles(profiles, active)
        self.llm_config_changed.emit()
        self._reload_profile_combo()

    def _test_llm_profile(self) -> None:
        """
        Temporarily configure a GroqService from the *current form fields*
        (no need to save first) and send a minimal test prompt in a background
        thread so the UI stays responsive.
        """
        from PyQt6.QtCore import QThread, pyqtSignal as _Signal
        from ..gui_utils import show_error_dialog

        # If a previous worker is still running, stop it cleanly to avoid
        # double-emit crashes when the user clicks "Test LLM" twice.
        prev = getattr(self, "_test_worker", None)
        if prev is not None and prev.isRunning():
            prev.quit()
            prev.wait(2000)

        class _TestWorker(QThread):
            done = _Signal(bool, str, str)   # (success, short_msg, full_details)

            def __init__(self, profile: dict, parent=None):
                super().__init__(parent)
                self._profile = profile

            def run(self):
                # The real work is in a module-level function so it can be
                # exercised by plain pytest tests without a QApplication.
                ok, short, full = _test_llm_sync(self._profile)
                self.done.emit(ok, short, full)

        # Collect profile from form (no disk save required)
        profile = self._current_profile_dict()

        self.llm_test_btn.setEnabled(False)
        self.llm_test_result.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px; background: transparent;")
        self.llm_test_result.setText("Testing…")

        worker = _TestWorker(profile, parent=self)
        self._test_worker = worker

        def _on_done(success: bool, msg: str, details: str):
            # Defensive: if the Settings view was destroyed while the
            # worker was running, just bail out without touching widgets.
            if not self.isVisible() or self._test_worker is not worker:
                return
            color = Styles.COLOR_GOOD if success else Styles.COLOR_BLUNDER
            self.llm_test_result.setStyleSheet(
                f"color: {color}; font-size: 11px; font-weight: bold; background: transparent;")
            self.llm_test_result.setText(msg)
            self.llm_test_btn.setEnabled(True)
            if not success and details:
                try:
                    show_error_dialog(
                        self,
                        "LLM Connection Test Failed",
                        "The test request failed. The full error is shown below — "
                        "you can copy it with Ctrl+C.",
                        details,
                    )
                except Exception as exc:
                    # Last-resort: log the error so the user at least sees something
                    from ...utils.logger import logger
                    logger.error(f"Failed to show error dialog: {exc}")
                    logger.error(f"Original error: {details}")

        worker.done.connect(_on_done)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _save_lichess_token(self) -> None:
        self.config_manager.set("lichess_token", self.lichess_token_input.text())
        QMessageBox.information(self, "Saved", "Lichess token saved.")

    def save_usernames(self):
        chesscom = self.chesscom_input.text()
        lichess = self.lichess_input.text()
        self.config_manager.set("chesscom_username", chesscom)
        self.config_manager.set("lichess_username", lichess)
        # Emit signal for immediate update
        self.usernames_changed.emit()
        QMessageBox.information(self, "Saved", "Usernames saved successfully.")

    def clear_cache(self):
        reply = QMessageBox.question(self, "Confirm", "Are you sure you want to clear the analysis cache? This will not delete your game history.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            from ...backend.cache import AnalysisCache
            cache = AnalysisCache()
            cache.clear_cache()
            QMessageBox.information(self, "Success", "Analysis cache cleared.")

    def clear_all_data(self):
        reply = QMessageBox.question(self, "Confirm", "Are you sure you want to clear ALL data? This includes game history and analysis cache. This action cannot be undone.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            from ...backend.cache import AnalysisCache
            from ...backend.game_history import GameHistoryManager
            
            cache = AnalysisCache()
            cache.clear_cache()
            
            history = GameHistoryManager()
            history.clear_history()
            
            # Also clear current games list in MainWindow if possible
            window = self.window()
            if hasattr(window, "games"):
                window.games = []
                if hasattr(window, "history_view"):
                    window.history_view.load_history()
                if hasattr(window, "metrics_view"):
                    window.metrics_view.refresh([])
            
            QMessageBox.information(self, "Success", "All data cleared.")

    def open_website(self):
        QDesktopServices.openUrl(QUrl("https://chess-analyzer-ut.vercel.app/"))

    def open_feedback(self):
        QDesktopServices.openUrl(QUrl("https://chess-analyzer-ut.vercel.app/feedback"))

    def check_for_updates(self):
        """Manually check for updates."""
        from ...backend.update_checker import UpdateChecker, APP_VERSION
        from ..dialogs import UpdateNotificationDialog
        
        # Show checking message
        self.update_btn.setEnabled(False)
        self.update_btn.setText("  Checking...")
        QApplication.processEvents()
        
        try:
            update_info = UpdateChecker.check_for_updates()
            
            if update_info.available:
                dialog = UpdateNotificationDialog(update_info, self)
                dialog.exec()
            else:
                QMessageBox.information(
                    self, 
                    "Up to Date", 
                    f"You're running the latest version (v{APP_VERSION})."
                )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to check for updates: {e}")
        finally:
            self.update_btn.setEnabled(True)
            self.update_btn.setText("  Check for Updates")
            if HAS_QTAWESOME:
                self.update_btn.setIcon(qta.icon("fa5s.sync-alt", color=Styles.COLOR_TEXT_SECONDARY))

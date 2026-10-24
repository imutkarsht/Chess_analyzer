"""
API Configuration Settings group component.
"""
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from src.gui.styles import Styles

from .helpers import create_icon_button

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False

from src.backend.services.groq_service import GroqService
from src.constants import PROVIDERS
from src.gui.utils.gui_utils import show_error_dialog
from src.utils.path_utils import get_resource_path

from .modern_widgets import PasswordFieldWrapper


def test_llm_sync(profile: dict) -> tuple:
    """Run a one-shot chat completion against the given profile.
    Returns (success: bool, short_message: str, full_details: str).
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
        return (True, "✓ Connected", "")
    except Exception as exc:
        exc_type = type(exc).__name__
        full = f"{exc_type}: {exc}"
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


class ApiSettings(QGroupBox):
    def __init__(self, config_manager, parent=None):
        super().__init__("API Configuration", parent)
        self.config_manager = config_manager
        self.setStyleSheet(Styles.get_group_box_style())

        self._llm_providers = PROVIDERS
        self._loading_profile = False
        self._current_profile_index = -1

        self.setup_ui()

    def setup_ui(self):
        api_layout = QVBoxLayout(self)
        api_layout.setContentsMargins(20, 25, 20, 20)
        api_layout.setSpacing(10)

        lbl_style = Styles.get_label_style(size=13)
        _combo_style = Styles.get_combobox_style()
        sq_btn_style = Styles.get_settings_square_icon_style()

        # --- Profile selector row ---
        prof_row = QHBoxLayout()
        self._lbl_prof = QLabel("LLM Profile:")
        self._lbl_prof.setStyleSheet(lbl_style)
        self._lbl_prof.setFixedWidth(88)
        prof_row.addWidget(self._lbl_prof)

        self.llm_profile_combo = QComboBox()
        self.llm_profile_combo.setStyleSheet(_combo_style)
        self.llm_profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        prof_row.addWidget(self.llm_profile_combo, stretch=1)

        self.llm_add_btn = QPushButton()
        if HAS_QTAWESOME:
            self.llm_add_btn.setIcon(qta.icon("fa5s.plus", color=Styles.COLOR_TEXT_PRIMARY))
        else:
            self.llm_add_btn.setText("+")
        self.llm_add_btn.setStyleSheet(sq_btn_style)
        self.llm_add_btn.setToolTip("New profile")
        self.llm_add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.llm_add_btn.clicked.connect(self._new_llm_profile)
        prof_row.addWidget(self.llm_add_btn)

        self.llm_del_btn = QPushButton()
        if HAS_QTAWESOME:
            self.llm_del_btn.setIcon(qta.icon("fa5s.minus", color=Styles.COLOR_BLUNDER))
        else:
            self.llm_del_btn.setText("−")
        self.llm_del_btn.setStyleSheet(sq_btn_style)
        self.llm_del_btn.setToolTip("Delete profile")
        self.llm_del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.llm_del_btn.clicked.connect(self._delete_llm_profile)
        prof_row.addWidget(self.llm_del_btn)

        api_layout.addLayout(prof_row)

        # --- Thin divider ---
        _div = QFrame()
        _div.setFrameShape(QFrame.Shape.HLine)
        _div.setStyleSheet(Styles.get_divider_style())
        api_layout.addWidget(_div)

        # --- Profile editor form ---
        pf = QFormLayout()
        pf.setSpacing(10)
        pf.setContentsMargins(0, 0, 0, 0)
        pf.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self._lbl_pname = QLabel("Name:")
        self._lbl_pname.setStyleSheet(lbl_style)
        self.llm_profile_name = QLineEdit()
        self.llm_profile_name.setStyleSheet(Styles.get_input_style())
        pf.addRow(self._lbl_pname, self.llm_profile_name)

        self._lbl_prov = QLabel("Provider:")
        self._lbl_prov.setStyleSheet(lbl_style)
        self.llm_provider_combo = QComboBox()
        for pkey, pmeta in self._llm_providers.items():
            self.llm_provider_combo.addItem(pmeta["label"], userData=pkey)
        self.llm_provider_combo.setStyleSheet(_combo_style)
        self.llm_provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        pf.addRow(self._lbl_prov, self.llm_provider_combo)

        self.lbl_llm_key = QLabel("API Key:")
        self.lbl_llm_key.setStyleSheet(lbl_style)
        self.llm_key_input = PasswordFieldWrapper(self)
        pf.addRow(self.lbl_llm_key, self.llm_key_input)

        self._lbl_model = QLabel("Model:")
        self._lbl_model.setStyleSheet(lbl_style)
        self.llm_model_input = QLineEdit()
        self.llm_model_input.setStyleSheet(Styles.get_input_style())
        pf.addRow(self._lbl_model, self.llm_model_input)

        self.lbl_llm_url = QLabel("Base URL:")
        self.lbl_llm_url.setStyleSheet(lbl_style)
        self.llm_url_input = QLineEdit()
        self.llm_url_input.setPlaceholderText("http://localhost:1234/v1")
        self.llm_url_input.setStyleSheet(Styles.get_input_style())
        pf.addRow(self.lbl_llm_url, self.llm_url_input)

        api_layout.addLayout(pf)

        # --- Save / Activate / Test buttons ---
        act_row = QHBoxLayout()
        self.llm_test_btn = create_icon_button("Test LLM", "fa5s.plug", self._test_llm_profile, self)
        act_row.addWidget(self.llm_test_btn)
        act_row.addStretch()
        api_layout.addLayout(act_row)

        status_row = QHBoxLayout()
        self.llm_active_label = QLabel()
        self.llm_active_label.setStyleSheet(
            Styles.get_secondary_label_style(size=11))
        status_row.addWidget(self.llm_active_label)
        status_row.addStretch()
        self.llm_test_result = QLabel()
        self.llm_test_result.setStyleSheet(
            Styles.get_secondary_label_style(size=11))
        status_row.addWidget(self.llm_test_result)
        api_layout.addLayout(status_row)

        # --- Lichess token ---
        self._api_div2 = QFrame()
        self._api_div2.setFrameShape(QFrame.Shape.HLine)
        self._api_div2.setStyleSheet(Styles.get_divider_style())
        api_layout.addWidget(self._api_div2)

        lf = QFormLayout()
        lf.setSpacing(10)
        lf.setContentsMargins(0, 0, 0, 0)
        lf.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._lbl_lichess = QLabel("Lichess API Token:")
        self._lbl_lichess.setStyleSheet(lbl_style)
        self.lichess_token_input = PasswordFieldWrapper(self)
        self.lichess_token_input.setText(self.config_manager.get("lichess_token", ""))
        lf.addRow(self._lbl_lichess, self.lichess_token_input)
        api_layout.addLayout(lf)

        self._add_explanation_rows(api_layout, lbl_style, _combo_style)

        self._reload_profile_combo()

    def _add_explanation_rows(self, api_layout, lbl_style, combo_style) -> None:
        """Move-explanation (Coach) options, cache policy and the data note (D8)."""
        self._api_div3 = QFrame()
        self._api_div3.setFrameShape(QFrame.Shape.HLine)
        self._api_div3.setStyleSheet(Styles.get_divider_style())
        api_layout.addWidget(self._api_div3)

        self._lbl_explain = QLabel("Move Explanations (Coach):")
        self._lbl_explain.setStyleSheet(lbl_style)
        api_layout.addWidget(self._lbl_explain)

        tick_path = get_resource_path("assets/images/tick.svg").replace("\\", "/")
        cb_style = Styles.get_checkbox_style(tick_path)

        self.explain_trivial_checkbox = QCheckBox(
            "Also explain sound moves (Best, Excellent, Good, Book)"
        )
        self.explain_trivial_checkbox.setStyleSheet(cb_style)
        self.explain_trivial_checkbox.setChecked(
            bool(self.config_manager.get("explain_llm_for_trivial_moves", False))
        )
        self.explain_trivial_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        api_layout.addWidget(self.explain_trivial_checkbox)

        ttl_row = QHBoxLayout()
        self._lbl_explain_ttl = QLabel("Explanation cache:")
        self._lbl_explain_ttl.setStyleSheet(lbl_style)
        ttl_row.addWidget(self._lbl_explain_ttl)
        self.explain_ttl_combo = QComboBox()
        self.explain_ttl_combo.setStyleSheet(combo_style)
        for label, days in (
            ("7 days", 7),
            ("30 days", 30),
            ("90 days", 90),
            ("1 year", 365),
            ("Never expire", None),
        ):
            self.explain_ttl_combo.addItem(label, userData=days)
        stored_ttl = self.config_manager.get("explain_cache_ttl_days", 30)
        index = self.explain_ttl_combo.findData(stored_ttl)
        self.explain_ttl_combo.setCurrentIndex(max(0, index))
        ttl_row.addWidget(self.explain_ttl_combo, stretch=1)
        api_layout.addLayout(ttl_row)

        self.clear_explanations_btn = create_icon_button(
            "Clear Explanation Cache", "fa5s.broom", self.clear_explanations, self
        )
        api_layout.addWidget(self.clear_explanations_btn)

    def clear_explanations(self) -> None:
        """Drop every cached explanation (shared confirmation with Data settings)."""
        from .data_settings import clear_analysis_cache

        clear_analysis_cache(self)

    def sync_explanation_settings(self) -> None:
        """Re-read the Coach settings from config into the widgets."""
        self.explain_trivial_checkbox.setChecked(
            bool(self.config_manager.get("explain_llm_for_trivial_moves", False))
        )
        index = self.explain_ttl_combo.findData(
            self.config_manager.get("explain_cache_ttl_days", 30)
        )
        self.explain_ttl_combo.setCurrentIndex(max(0, index))

    def _reload_profile_combo(self) -> None:
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
        self._current_profile_index = select_idx
        if 0 <= select_idx < len(profiles):
            self._load_profile_into_form(profiles[select_idx])
        self._loading_profile = False

    def _on_profile_selected(self, index: int) -> None:
        if self._loading_profile:
            return
        profiles = self.config_manager.get_profiles()

        if 0 <= self._current_profile_index < len(profiles):
            profiles[self._current_profile_index] = self._current_profile_dict()

        if 0 <= index < len(profiles):
            self._load_profile_into_form(profiles[index])
            self._current_profile_index = index

    def _load_profile_into_form(self, profile: dict) -> None:
        self._loading_profile = True
        self.llm_profile_name.setText(profile.get("name", ""))

        provider = profile.get("provider", "groq")
        idx = self.llm_provider_combo.findData(provider)
        self.llm_provider_combo.setCurrentIndex(max(0, idx))

        self.llm_key_input.setText(profile.get("api_key", ""))
        self.llm_model_input.setText(profile.get("model", ""))
        self.llm_url_input.setText(profile.get("base_url", ""))
        self._loading_profile = False

        self._on_provider_changed()
        self._update_active_label()

    def _on_provider_changed(self, _index=None) -> None:
        if self._loading_profile:
            return
        provider_key = self.llm_provider_combo.currentData() or "groq"
        preset = self._llm_providers.get(provider_key, {})

        self.llm_key_input.setEnabled(True)
        self.lbl_llm_key.setEnabled(True)
        self.llm_key_input.setPlaceholderText(preset.get("key_placeholder", ""))
        self.llm_model_input.setPlaceholderText(preset.get("model_placeholder", ""))

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
        provider = self.llm_provider_combo.currentData() or "groq"
        provider = GroqService._normalise_provider(provider)
        preset = self._llm_providers.get(provider, {})
        base_url = self.llm_url_input.text().strip()
        if not base_url and provider != "custom":
            base_url = preset.get("base_url", "")
        base_url = GroqService._normalise_base_url(base_url)
        return {
            "name":     self.llm_profile_name.text().strip(),
            "provider": provider,
            "api_key":  self.llm_key_input.text().strip(),
            "model":    self.llm_model_input.text().strip() or preset.get("default_model", ""),
            "base_url": base_url,
        }

    def _new_llm_profile(self) -> None:
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New LLM Profile", "Profile name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        profiles = self.config_manager.get_profiles()
        if any(p["name"] == name for p in profiles):
            from src.gui.main_window import MainWindow
            MainWindow.toast_from_widget(self, f'A profile named "{name}" already exists.', "warning")
            return
        profiles.append({
            "name": name, "provider": "groq", "api_key": "",
            "model": "llama-3.3-70b-versatile", "base_url": "",
        })
        self.config_manager.set_profiles(profiles)
        self._reload_profile_combo()
        self.llm_profile_combo.setCurrentIndex(len(profiles) - 1)

    def _delete_llm_profile(self) -> None:
        profiles = self.config_manager.get_profiles()
        if len(profiles) <= 1:
            from src.gui.main_window import MainWindow
            MainWindow.toast_from_widget(self, "You must keep at least one profile.", "warning")
            return
        idx = self.llm_profile_combo.currentIndex()
        if not (0 <= idx < len(profiles)):
            return
        name = profiles[idx].get("name", "")
        from src.gui.utils.gui_utils import confirm_dialog
        if not confirm_dialog(self, "Delete Profile",
                              f'Delete profile "{name}"?',
                              confirm_label="Delete"):
            return
        profiles.pop(idx)
        active = self.config_manager.get("llm_active_profile", "")
        if active == name:
            active = profiles[0]["name"]
        self.config_manager.set_profiles(profiles, active_name=active)
        self._reload_profile_combo()

    def _test_llm_profile(self) -> None:
        prev = getattr(self, "_test_worker", None)
        if prev is not None and prev.isRunning():
            prev.quit()
            prev.wait(2000)

        class _TestWorker(QThread):
            done = pyqtSignal(bool, str, str)

            def __init__(self, profile: dict, parent=None):
                super().__init__(parent)
                self._profile = profile

            def run(self):
                ok, short, full = test_llm_sync(self._profile)
                self.done.emit(ok, short, full)

        profile = self._current_profile_dict()

        self.llm_test_btn.setEnabled(False)
        self.llm_test_result.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px; background: transparent;")
        self.llm_test_result.setText("Testing…")

        worker = _TestWorker(profile, parent=self)
        self._test_worker = worker

        def _on_done(success: bool, msg: str, details: str):
            if self._test_worker is not worker:
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
                    from ....utils.logger import logger
                    logger.error(f"Failed to show error dialog: {exc}")
                    logger.error(f"Original error: {details}")

        def _cleanup():
            if self._test_worker is worker:
                self._test_worker = None
            worker.deleteLater()

        worker.done.connect(_on_done)
        worker.finished.connect(_cleanup)
        worker.start()

    def set_advanced_visible(self, visible):
        self._lbl_pname.setVisible(visible)
        self.llm_profile_name.setVisible(visible)
        self.llm_add_btn.setVisible(visible)
        self.llm_del_btn.setVisible(visible)
        self.lbl_llm_url.setVisible(visible)
        self.llm_url_input.setVisible(visible)
        self.llm_test_btn.setVisible(visible)
        self.llm_test_result.setVisible(visible)
        self.llm_active_label.setVisible(visible)
        self._api_div2.setVisible(visible)
        self._lbl_lichess.setVisible(visible)
        self.lichess_token_input.setVisible(visible)

    def _refresh_label(self, attr_name):
        lbl = getattr(self, attr_name, None)
        if lbl:
            lbl.setStyleSheet(Styles.get_label_style(size=13))

    def _refresh_secondary_label(self, attr_name):
        lbl = getattr(self, attr_name, None)
        if lbl:
            lbl.setStyleSheet(Styles.get_secondary_label_style(size=11))

    def refresh_styles(self, *args, **kwargs):
        self.setStyleSheet(Styles.get_group_box_style())
        if hasattr(self, 'llm_profile_combo'):
            self.llm_profile_combo.setStyleSheet(Styles.get_combobox_style())
        if hasattr(self, 'llm_provider_combo'):
            self.llm_provider_combo.setStyleSheet(Styles.get_combobox_style())
        if hasattr(self, 'llm_add_btn'):
            self.llm_add_btn.setStyleSheet(Styles.get_settings_square_icon_style())
        if hasattr(self, 'llm_del_btn'):
            self.llm_del_btn.setStyleSheet(Styles.get_settings_square_icon_style())
        if hasattr(self, 'llm_test_btn'):
            self.llm_test_btn.setStyleSheet(Styles.get_settings_default_button_style())
        if hasattr(self, 'llm_profile_name'):
            self.llm_profile_name.setStyleSheet(Styles.get_input_style())
        if hasattr(self, 'llm_model_input'):
            self.llm_model_input.setStyleSheet(Styles.get_input_style())
        if hasattr(self, 'llm_url_input'):
            self.llm_url_input.setStyleSheet(Styles.get_input_style())
        for widget in [self.llm_key_input, self.lichess_token_input]:
            if hasattr(widget, 'refresh_styles'):
                widget.refresh_styles()
        self._refresh_label('_lbl_prof')
        self._refresh_label('_lbl_pname')
        self._refresh_label('_lbl_prov')
        self._refresh_label('lbl_llm_key')
        self._refresh_label('_lbl_model')
        self._refresh_label('lbl_llm_url')
        self._refresh_label('_lbl_lichess')
        self._refresh_secondary_label('llm_active_label')
        self._refresh_secondary_label('llm_test_result')
        if hasattr(self, '_div'):
            self._div.setStyleSheet(Styles.get_divider_style())
        if hasattr(self, '_api_div2'):
            self._api_div2.setStyleSheet(Styles.get_divider_style())

        if hasattr(self, '_api_div3'):
            self._api_div3.setStyleSheet(Styles.get_divider_style())
        if hasattr(self, 'explain_ttl_combo'):
            self.explain_ttl_combo.setStyleSheet(Styles.get_combobox_style())
        if hasattr(self, 'clear_explanations_btn'):
            self.clear_explanations_btn.setStyleSheet(Styles.get_settings_default_button_style())
        self._refresh_label('_lbl_explain')
        self._refresh_label('_lbl_explain_ttl')
        if hasattr(self, 'explain_trivial_checkbox'):
            tick_path = get_resource_path("assets/images/tick.svg").replace("\\", "/")
            cb_style = Styles.get_checkbox_style(tick_path)
            self.explain_trivial_checkbox.setStyleSheet(cb_style)

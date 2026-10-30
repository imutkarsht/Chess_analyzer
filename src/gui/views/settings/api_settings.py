"""
API Configuration Settings group component.
"""
import time

from PyQt6.QtCore import QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.backend.services.groq_service import GroqService, explanation_tuning
from src.constants import PROVIDERS
from src.gui.components import (
    Button,
    ButtonSize,
    ButtonVariant,
    Input,
    Select,
)
from src.gui.components.feedback.toast import ToastManager
from src.gui.styles import Styles
from src.gui.utils.gui_utils import show_error_dialog

from .components import (
    CONTROL_DEFAULT,
    CONTROL_WIDE,
    SettingsForm,
)
from .helpers import create_icon_button


def test_llm_sync(profile: dict, tuning: tuple | None = None) -> tuple:
    """Run a one-shot chat completion against the given profile.

    ``tuning`` is ``(temperature, max_tokens, reasoning_effort)`` from the
    explanation settings. Passing it makes the test exercise the same optional
    parameters as a real explanation, so an unsupported tuning choice fails
    here instead of silently falling back later.

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
        temperature, max_tokens, reasoning_effort = tuning or (None, None, "")
        options = {"max_tokens": max_tokens or 10}
        if temperature is not None:
            options["temperature"] = temperature
        if reasoning_effort:
            options["reasoning_effort"] = reasoning_effort

        client = OpenAI(api_key=api_key, base_url=base_url)
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user",
                       "content": "Reply with exactly: OK"}],
            **options,
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
        self._advanced_visible = True
        self._help_url = ""
        self._base_url_wrapper: QWidget | None = None

        self.setup_ui()

    def setup_ui(self):
        api_layout = QVBoxLayout(self)
        api_layout.setContentsMargins(0, 12, 0, 0)
        api_layout.setSpacing(10)

        self._profile_form = SettingsForm(self)
        api_layout.addWidget(self._profile_form)

        # --- Profile selector row ---
        self.llm_profile_combo = Select(min_width=220)
        self.llm_profile_combo.setMaximumWidth(420)
        self.llm_profile_combo.currentIndexChanged.connect(self._on_profile_selected)

        self.llm_add_btn = Button(
            variant=ButtonVariant.FILLED,
            size=ButtonSize.SM,
            icon="fa5s.plus",
            icon_position="only",
            tooltip="New profile",
            on_click=self._new_llm_profile,
            parent=self,
        )
        self.llm_add_btn.setAccessibleName("Add LLM profile")

        self.llm_del_btn = Button(
            variant=ButtonVariant.FILLED,
            size=ButtonSize.SM,
            icon="fa5s.minus",
            icon_position="only",
            danger=True,
            tooltip="Delete profile",
            on_click=self._delete_llm_profile,
            parent=self,
        )
        self.llm_del_btn.setAccessibleName("Delete LLM profile")

        self.llm_set_active_btn = create_icon_button(
            "Set active", "fa5s.star", self._on_set_active, self
        )
        self.llm_set_active_btn.setToolTip(
            "Use this profile for AI Coach and game reports."
        )
        self.llm_set_active_btn.setAccessibleName("Set active LLM profile")

        selector = QWidget()
        selector.setStyleSheet(Styles.get_transparent_label_style())
        selector_row = QHBoxLayout(selector)
        selector_row.setContentsMargins(0, 0, 0, 0)
        selector_row.setSpacing(8)
        selector_row.addWidget(self.llm_profile_combo)
        selector_row.addWidget(self.llm_add_btn)
        selector_row.addWidget(self.llm_del_btn)
        selector_row.addWidget(self.llm_set_active_btn)
        selector_row.addStretch(1)
        self._profile_form.add_row(
            "LLM Profile",
            selector,
            width=None,
            hint="Only the active profile is used by Coach and game reports.",
        )

        # --- Profile editor rows ---
        self.llm_profile_name = Input()
        self._profile_form.add_row(
            "Name",
            self.llm_profile_name,
            advanced=True,
            width=CONTROL_DEFAULT,
            hint="A label like Work or Local. Must be unique.",
        )

        self.llm_provider_combo = Select(min_width=220)
        for pkey, pmeta in self._llm_providers.items():
            self.llm_provider_combo.addItem(pmeta["label"], userData=pkey)
        self.llm_provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self._profile_form.add_row(
            "Provider",
            self.llm_provider_combo,
            width=CONTROL_DEFAULT,
            hint=(
                "Cloud providers receive game data. LM Studio runs entirely "
                "on this machine."
            ),
        )

        self.llm_key_input = Input(password=True)
        self.llm_key_input.setMaximumWidth(420)
        self.llm_help_btn = Button(
            "Get API key ↗",
            ButtonVariant.LINK,
            on_click=self._open_provider_help,
            parent=self,
        )
        self.llm_help_btn.setAccessibleName("Open provider API key page")
        self.llm_help_btn.setVisible(False)

        key_row = QWidget()
        key_row.setStyleSheet(Styles.get_transparent_label_style())
        key_layout = QHBoxLayout(key_row)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.setSpacing(8)
        key_layout.addWidget(self.llm_key_input)
        key_layout.addWidget(self.llm_help_btn)
        key_layout.addStretch(1)
        self._profile_form.add_row(
            "API Key",
            key_row,
            width=None,
            hint="Stored in the OS keychain, never in config.json.",
        )

        self.llm_model_input = Input()
        self._profile_form.add_row(
            "Model",
            self.llm_model_input,
            width=CONTROL_DEFAULT,
            hint="Use the provider's exact model id.",
        )

        self.llm_url_input = Input(placeholder="http://localhost:1234/v1")
        self._base_url_wrapper = self._profile_form.add_row(
            "Base URL",
            self.llm_url_input,
            advanced=True,
            width=CONTROL_WIDE,
            hint="Auto-filled for presets. Change only for proxies or self-hosted endpoints.",
        )

        for field in (
            self.llm_profile_name,
            self.llm_model_input,
            self.llm_url_input,
        ):
            field.editingFinished.connect(self._persist_current_profile)
        self.llm_key_input.editingFinished.connect(self._persist_current_profile)

        # --- Test connection ---
        act_row = QHBoxLayout()
        self.llm_test_btn = create_icon_button(
            "Test connection", "fa5s.plug", self._test_llm_profile, self
        )
        self.llm_test_btn.setAccessibleName("Test LLM connection")
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

        self.llm_privacy_label = QLabel(
            "Cloud providers receive the game data you send for explanations "
            "and reports. LM Studio runs locally. Without a working profile, "
            "Coach uses offline summaries."
        )
        self.llm_privacy_label.setWordWrap(True)
        self.llm_privacy_label.setStyleSheet(
            Styles.get_secondary_label_style(size=11)
        )
        api_layout.addWidget(self.llm_privacy_label)

        self._reload_profile_combo()

    # ------------------------------------------------------------------
    # Profile state
    # ------------------------------------------------------------------
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
        self._update_profile_actions()
        self._update_active_label()

    def _on_profile_selected(self, index: int) -> None:
        if self._loading_profile:
            return
        profiles = self.config_manager.get_profiles()
        current = self._current_profile_index

        if 0 <= current < len(profiles) and not self._persist_current_profile(
            index=current
        ):
            # Keep the invalid profile in the editor instead of loading another.
            self._loading_profile = True
            self.llm_profile_combo.setCurrentIndex(current)
            self._loading_profile = False
            return

        profiles = self.config_manager.get_profiles()
        if 0 <= index < len(profiles):
            self._load_profile_into_form(profiles[index])
            self._current_profile_index = index
        self._update_profile_actions()
        self._update_active_label()

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

        self._apply_provider_state(reset_defaults=False)
        self._update_active_label()

    def _on_provider_changed(self, _index=None) -> None:
        if self._loading_profile:
            return
        self._apply_provider_state(reset_defaults=True)
        self._persist_current_profile()

    def _apply_provider_state(self, *, reset_defaults: bool) -> None:
        provider = self.llm_provider_combo.currentData() or "groq"
        preset = self._llm_providers.get(provider, {})
        is_custom = provider == "custom"
        requires_key = preset.get("requires_key", True)

        self.llm_key_input.setEnabled(requires_key or is_custom)
        self.llm_key_input.setPlaceholderText(preset.get("key_placeholder", ""))
        self.llm_model_input.setPlaceholderText(preset.get("model_placeholder", ""))

        self._help_url = preset.get("help_url", "")
        self.llm_help_btn.setVisible(bool(self._help_url))

        if self._base_url_wrapper is not None:
            self._profile_form.set_row_forced_visible(
                self._base_url_wrapper, is_custom
            )

        if reset_defaults:
            self.llm_model_input.setText(preset.get("default_model", ""))
            self.llm_url_input.setText(preset.get("base_url", ""))

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

    def _persist_current_profile(
        self, index: int | None = None, activate: bool = False
    ) -> bool:
        """Persist the editor to the profile list.

        Profile edits save on field commit like every binder-driven card, so
        switching profiles or closing Settings cannot silently discard them.
        ``index`` lets a profile-switch commit the profile that is still shown
        in the editor *before* loading the newly selected one.
        """
        if self._loading_profile:
            return False
        profiles = self.config_manager.get_profiles()
        idx = self.llm_profile_combo.currentIndex() if index is None else index
        if not (0 <= idx < len(profiles)):
            return False

        old_name = profiles[idx].get("name", "")
        profile = self._current_profile_dict()
        new_name = profile["name"]
        if not new_name:
            self._warn("Profile name cannot be empty.")
            return False
        if new_name != old_name and any(
            p.get("name") == new_name for p in profiles
        ):
            self._warn(f'A profile named "{new_name}" already exists.')
            return False

        profiles[idx] = profile
        active = self.config_manager.get("llm_active_profile", "")
        if active == old_name:
            active = new_name
        if activate:
            active = new_name
        self.config_manager.set_profiles(profiles, active_name=active)

        if self.llm_profile_combo.itemText(idx) != new_name:
            self.llm_profile_combo.blockSignals(True)
            self.llm_profile_combo.setItemText(idx, new_name)
            self.llm_profile_combo.blockSignals(False)

        self._update_active_label()
        return True

    def _on_set_active(self) -> None:
        self._persist_current_profile(activate=True)

    def _update_active_label(self) -> None:
        active = self.config_manager.get("llm_active_profile", "")
        if active:
            self.llm_active_label.setText(f'Active profile: "{active}"')
        else:
            self.llm_active_label.setText("")

        current = self.llm_profile_name.text().strip()
        self.llm_set_active_btn.setEnabled(bool(current) and current != active)

    def _update_profile_actions(self) -> None:
        can_delete = self.llm_profile_combo.count() > 1
        self.llm_del_btn.setEnabled(can_delete)
        self.llm_del_btn.setToolTip(
            "Delete profile" if can_delete else "Keep at least one profile"
        )

    def _warn(self, message: str) -> None:
        ToastManager.warning(self, message)

    def _open_provider_help(self) -> None:
        if self._help_url:
            QDesktopServices.openUrl(QUrl(self._help_url))

    # ------------------------------------------------------------------
    # Profile actions
    # ------------------------------------------------------------------
    def _new_llm_profile(self) -> None:
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New LLM Profile", "Profile name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        profiles = self.config_manager.get_profiles()
        if any(p["name"] == name for p in profiles):
            self._warn(f'A profile named "{name}" already exists.')
            return
        preset = self._llm_providers["groq"]
        profiles.append({
            "name": name,
            "provider": "groq",
            "api_key": "",
            "model": preset["default_model"],
            "base_url": preset["base_url"],
        })
        self.config_manager.set_profiles(profiles)
        self._reload_profile_combo()
        self.llm_profile_combo.setCurrentIndex(len(profiles) - 1)

    def _delete_llm_profile(self) -> None:
        if not self._persist_current_profile():
            return
        profiles = self.config_manager.get_profiles()
        if len(profiles) <= 1:
            self._warn("You must keep at least one profile.")
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

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------
    def _test_llm_profile(self) -> None:
        prev = getattr(self, "_test_worker", None)
        if prev is not None and prev.isRunning():
            prev.quit()
            prev.wait(2000)

        class _TestWorker(QThread):
            done = pyqtSignal(bool, str, str, float)

            def __init__(self, profile: dict, tuning: tuple, parent=None):
                super().__init__(parent)
                self._profile = profile
                self._tuning = tuning

            def run(self):
                start = time.perf_counter()
                ok, short, full = test_llm_sync(self._profile, self._tuning)
                elapsed_ms = (time.perf_counter() - start) * 1000
                self.done.emit(ok, short, full, elapsed_ms)

        profile = self._current_profile_dict()
        model = profile.get("model") or "default model"
        tuning = explanation_tuning(self.config_manager)

        self.llm_test_btn.setEnabled(False)
        self.llm_test_result.setStyleSheet(
            f"color: {Styles.COLOR_TEXT_SECONDARY}; font-size: 11px; background: transparent;")
        self.llm_test_result.setText("Testing…")

        previous_toast = getattr(self, "_test_toast", None)
        if previous_toast is not None:
            previous_toast.dismiss()
        self._test_toast = ToastManager.loading(self, f"Testing {model}…")

        worker = _TestWorker(profile, tuning, parent=self)
        self._test_worker = worker

        def _on_done(success: bool, msg: str, details: str, elapsed_ms: float):
            if self._test_worker is not worker:
                return
            color = Styles.COLOR_GOOD if success else Styles.COLOR_BLUNDER
            self.llm_test_result.setStyleSheet(
                f"color: {color}; font-size: 11px; font-weight: bold; background: transparent;")
            text = f"{msg} · {model} · {elapsed_ms:.0f} ms" if success else msg
            self.llm_test_result.setText(text)
            self.llm_test_btn.setEnabled(True)
            if success:
                self._test_toast.update(
                    f"Connected · {model} · {elapsed_ms:.0f} ms", variant="success"
                )
            else:
                self._test_toast.update(msg or "Connection test failed.", variant="error")
            self._test_toast = None
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
        self._advanced_visible = visible
        self._profile_form.set_advanced_visible(visible)
        provider = self.llm_provider_combo.currentData() or "groq"
        if self._base_url_wrapper is not None:
            self._profile_form.set_row_forced_visible(
                self._base_url_wrapper, provider == "custom"
            )

    def _refresh_secondary_label(self, attr_name):
        lbl = getattr(self, attr_name, None)
        if lbl:
            lbl.setStyleSheet(Styles.get_secondary_label_style(size=11))

    def refresh_styles(self, *args, **kwargs):
        self.setStyleSheet(Styles.get_group_box_style())
        if hasattr(self, 'llm_add_btn'):
            self.llm_add_btn.refresh_styles()
        if hasattr(self, 'llm_del_btn'):
            self.llm_del_btn.refresh_styles()
        if hasattr(self, 'llm_set_active_btn'):
            self.llm_set_active_btn.refresh_styles()
        if hasattr(self, 'llm_help_btn'):
            self.llm_help_btn.refresh_styles()
        if hasattr(self, 'llm_test_btn'):
            self.llm_test_btn.refresh_styles()
        if hasattr(self, 'llm_profile_name'):
            self.llm_profile_name.refresh_styles()
        if hasattr(self, 'llm_model_input'):
            self.llm_model_input.refresh_styles()
        if hasattr(self, 'llm_url_input'):
            self.llm_url_input.refresh_styles()
        if hasattr(self, '_profile_form'):
            self._profile_form.refresh_styles()
        for widget in [self.llm_key_input]:
            if hasattr(widget, 'refresh_styles'):
                widget.refresh_styles()
        self._refresh_secondary_label('llm_active_label')
        self._refresh_secondary_label('llm_test_result')
        if hasattr(self, 'llm_privacy_label'):
            self.llm_privacy_label.setStyleSheet(
                Styles.get_secondary_label_style(size=11)
            )

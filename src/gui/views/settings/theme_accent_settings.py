"""Appearance settings: visual theme gallery, tint, and accent controls."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from src.gui.components import (
    AccentSwatch,
    Button,
    ButtonSize,
    ButtonVariant,
    Checkbox,
    CheckboxVariant,
    Label,
    TextRole,
    ToastManager,
)
from src.gui.icons import IconStyleManager
from src.gui.theme import ACCENT_PRESETS, AccentPreset, ThemeManager
from src.gui.views.settings.components import SettingsBinder, SettingsForm
from src.gui.views.settings.theme_gallery import ThemeGallery


class ThemeAccentSettings(QGroupBox):
    """Application theme and accent controls."""

    theme_refreshed = pyqtSignal()

    def __init__(self, config_manager, parent=None):
        super().__init__("Appearance", parent)
        self.config_manager = config_manager
        self.setProperty("settingsCard", True)
        title_font = self.font()
        title_font.setPixelSize(20)
        title_font.setWeight(QFont.Weight.Bold)
        self.setFont(title_font)
        self.setup_ui()

    def setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)
        outer.setSpacing(14)

        self.gallery = ThemeGallery(self.config_manager, self)
        self.gallery.theme_selected.connect(self._on_theme_selected)
        outer.addWidget(self.gallery)

        self._add_tint_row(outer)
        outer.addWidget(self._make_divider())
        self._add_accent_section(outer)

        # Notification position remains a schema-bound settings row. Theme,
        # tint, and accent are applied live and persisted by their own
        # handlers so the gallery can update immediately.
        self.form = SettingsForm(self)
        self.binder = SettingsBinder(self.config_manager, self.form, self)
        outer.addWidget(self.form)
        self.toast_position_combo = self.binder.add(
            "toast_position",
            hint="",
            width=None,
            on_change=self._on_toast_position_changed,
        )
        self.icon_style_combo = self.binder.add(
            "icon_style",
            hint="",
            width=None,
            on_change=self._on_icon_style_changed,
        )
        self.icon_variant_combo = self.binder.add(
            "icon_variant",
            hint="",
            width=None,
            on_change=self._on_icon_variant_changed,
        )

        self._last_runtime_mode = ThemeManager.mode()
        ThemeManager.instance().theme_changed.connect(
            self._on_runtime_theme_changed
        )
        self._update_tint_visibility()
        self._refresh_accent_presets()

    # ------------------------------------------------------------------
    # Tint
    # ------------------------------------------------------------------
    def _add_tint_row(self, outer: QVBoxLayout) -> None:
        self.tint_checkbox = Checkbox(
            "Accent tint",
            CheckboxVariant.FLAT,
            parent=self,
        )
        self.tint_checkbox.setToolTip(
            "Mix the accent colour into window and card surfaces. "
            "Available for Light and Dark themes."
        )
        self.tint_checkbox.setAccessibleDescription(
            "Mix the accent colour into window and card surfaces. "
            "Available for Light and Dark themes."
        )
        self.tint_checkbox.stateChanged.connect(
            lambda _state: self._on_tint_changed(self.tint_checkbox.isChecked())
        )

        self.tint_row = QWidget(self)
        tint_layout = QHBoxLayout(self.tint_row)
        tint_layout.setContentsMargins(4, 0, 0, 0)
        tint_layout.addWidget(self.tint_checkbox)
        tint_layout.addStretch(1)
        outer.addWidget(self.tint_row)

    def _on_tint_changed(self, enabled: bool) -> None:
        self.config_manager.set("tint_enabled", bool(enabled))
        ThemeManager.set_tint_enabled(bool(enabled))
        self.gallery.refresh_previews()
        self.theme_refreshed.emit()

    def _update_tint_visibility(self, mode: str | None = None) -> None:
        mode = mode or self.config_manager.get("theme_mode", "system")
        self.tint_row.setVisible(mode in {"light", "dark"})

    # ------------------------------------------------------------------
    # Accent
    # ------------------------------------------------------------------
    def _add_accent_section(self, outer: QVBoxLayout) -> None:
        header = QHBoxLayout()
        header.setContentsMargins(4, 0, 0, 0)
        header.addWidget(Label("Accent", role=TextRole.SUBHEADING))
        header.addStretch(1)
        outer.addLayout(header)

        self.system_accent_btn = Button(
            "System accent",
            ButtonVariant.GHOST,
            ButtonSize.SM,
            checkable=True,
            tooltip="Follow the operating system accent colour",
            on_click=self._use_system_accent,
            parent=self,
        )
        self.custom_accent_btn = Button(
            "Custom\u2026",
            ButtonVariant.GHOST,
            ButtonSize.SM,
            icon="palette",
            checkable=True,
            tooltip="Choose a custom accent colour",
            on_click=self.change_accent_color,
            parent=self,
        )

        accent_row = QHBoxLayout()
        accent_row.setContentsMargins(4, 2, 0, 0)
        accent_row.setSpacing(10)
        self.accent_group = QButtonGroup(self)
        self.accent_group.setExclusive(True)
        self.accent_buttons: dict[str, AccentSwatch] = {}
        for preset in ACCENT_PRESETS:
            swatch = AccentSwatch(preset.color(ThemeManager.mode()), preset.name, self)
            self.accent_group.addButton(swatch)
            swatch.clicked.connect(
                lambda _checked=False, choice=preset: self._select_preset(choice)
            )
            accent_row.addWidget(swatch)
            self.accent_buttons[preset.name] = swatch
        accent_row.addSpacing(10)
        accent_row.addWidget(self.system_accent_btn)
        accent_row.addWidget(self.custom_accent_btn)
        accent_row.addStretch(1)
        outer.addLayout(accent_row)

    def _refresh_accent_presets(self) -> None:
        mode = ThemeManager.mode()
        previous_mode = self._last_runtime_mode
        self._last_runtime_mode = mode

        if previous_mode is not None and mode != previous_mode:
            self._remap_preset_accent(mode)

        for preset in ACCENT_PRESETS:
            self.accent_buttons[preset.name].set_color(preset.color(mode))
        self._sync_accent_selection()

    def _remap_preset_accent(self, mode: str) -> None:
        """Move a preset accent to its light/dark seed when the theme flips."""
        if ThemeManager.active_bundle_owns_accent():
            return
        if str(self.config_manager.get("accent_mode", "system")) != "custom":
            return

        current = str(
            self.config_manager.get("accent_color", "") or ThemeManager.accent()
        ).upper()
        for preset in ACCENT_PRESETS:
            if not preset.matches(current):
                continue
            new_color = preset.color(mode)
            if new_color.upper() != current:
                self.config_manager.set("accent_color", new_color)
                ThemeManager.set_accent_mode("custom")
                ThemeManager.set_accent(new_color)
            return

    def _select_preset(self, preset: AccentPreset) -> None:
        color = preset.color(ThemeManager.mode())
        self.config_manager.set("accent_color", color)
        self.config_manager.set("accent_mode", "custom")
        ThemeManager.set_accent_mode("custom")
        ThemeManager.set_accent(color)
        self._sync_accent_selection()
        self.gallery.refresh_previews()
        self.theme_refreshed.emit()

    def _use_system_accent(self) -> None:
        self.config_manager.set("accent_mode", "system")
        ThemeManager.set_accent_mode("system")
        detected = ThemeManager.accent()
        if detected:
            self.config_manager.set("accent_color", detected)
        self._sync_accent_selection()
        self.gallery.refresh_previews()
        self.theme_refreshed.emit()

    def change_accent_color(self):
        # The custom action is checkable so it can show that a non-preset
        # accent is active; reset it before opening the dialog.
        self._sync_accent_selection()

        color = QColorDialog.getColor(
            initial=QColor(ThemeManager.accent()),
            parent=self,
            title="Select Accent Color",
        )
        if color.isValid():
            name = color.name()
            self.config_manager.set("accent_color", name)
            self.config_manager.set("accent_mode", "custom")
            ThemeManager.set_accent_mode("custom")
            ThemeManager.set_accent(name)
            self._sync_accent_selection()
            self.gallery.refresh_previews()
            self.theme_refreshed.emit()

    def _sync_accent_selection(
        self,
        mode: str | None = None,
        accent: str | None = None,
    ) -> None:
        if not hasattr(self, "accent_buttons"):
            return

        mode = mode or str(self.config_manager.get("accent_mode", "system"))
        accent = (
            accent
            or self.config_manager.get("accent_color", "")
            or ThemeManager.accent()
            or ""
        )
        accent = str(accent).upper()

        self.system_accent_btn.setChecked(mode == "system")

        self.accent_group.setExclusive(False)
        for swatch in self.accent_buttons.values():
            swatch.setChecked(False)
        self.accent_group.setExclusive(True)

        match = None
        if mode != "system":
            for preset in ACCENT_PRESETS:
                if preset.matches(accent):
                    match = self.accent_buttons[preset.name]
                    break

        if match is not None:
            match.setChecked(True)
        self.custom_accent_btn.setChecked(mode != "system" and match is None)

    # ------------------------------------------------------------------
    # Selection wiring
    # ------------------------------------------------------------------
    def _on_theme_selected(self, mode: str) -> None:
        self._update_tint_visibility(mode)
        self._refresh_accent_presets()

    def _on_runtime_theme_changed(self, *_args) -> None:
        self._refresh_accent_presets()

    def _on_toast_position_changed(self, position):
        ToastManager.configure(position=position)

    def _on_icon_style_changed(self, style) -> None:
        value = str(style)
        self.config_manager.set("icon_style", value)
        IconStyleManager.set_pack(value)

    def _on_icon_variant_changed(self, variant) -> None:
        value = str(variant)
        self.config_manager.set("icon_variant", value)
        IconStyleManager.set_variant(value)

    @staticmethod
    def _make_divider() -> QFrame:
        divider = QFrame()
        divider.setObjectName("SettingsDivider")
        divider.setFixedHeight(1)
        return divider

    # ------------------------------------------------------------------
    # Lifecycle hooks used by SettingsView
    # ------------------------------------------------------------------
    def reload_from_config(self):
        self.binder.load()
        self.gallery.reload_from_config()

        self.tint_checkbox.blockSignals(True)
        try:
            self.tint_checkbox.setChecked(
                bool(self.config_manager.get("tint_enabled", False))
            )
        finally:
            self.tint_checkbox.blockSignals(False)

        self._update_tint_visibility()
        self._refresh_accent_presets()

    def set_advanced_visible(self, visible):
        self.binder.set_advanced_visible(visible)

    def refresh_styles(self, *args, **kwargs):
        self.style().unpolish(self)
        self.style().polish(self)
        self.form.refresh_styles()
        self.gallery.refresh_styles()
        self.tint_checkbox.refresh_styles()
        self.system_accent_btn.refresh_styles()
        self.custom_accent_btn.refresh_styles()
        self._refresh_accent_presets()

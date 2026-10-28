"""Theme mode and accent colour settings."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QColorDialog, QGroupBox, QVBoxLayout

from ....config.settings_schema import get_spec
from ...components import Button, ButtonVariant
from ...components.toast import ToastManager
from ...styles import Styles
from ...theme import ThemeManager
from .components import RadioChoice, SettingsBinder, SettingsForm


class ThemeAccentSettings(QGroupBox):
    """Application theme and accent controls."""

    theme_refreshed = pyqtSignal()

    def __init__(self, config_manager, parent=None):
        super().__init__("Theme && Accent", parent)
        self.config_manager = config_manager
        self.setStyleSheet(Styles.get_group_box_style())
        self.setup_ui()

    def setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)

        self.form = SettingsForm(self)
        self.binder = SettingsBinder(self.config_manager, self.form, self)
        outer.addWidget(self.form)

        self._add_theme_mode_row()
        self._add_accent_row()
        self._add_toast_position_row()

    def _add_theme_mode_row(self):
        spec = get_spec("theme_mode")
        self.theme_mode_choice = RadioChoice(
            [(choice.value, choice.label) for choice in spec.choices]
        )
        self.binder.add(
            "theme_mode",
            self.theme_mode_choice,
            hint="",
            width=None,
            on_change=self._on_theme_mode_changed,
        )

    def _on_theme_mode_changed(self, mode):
        ThemeManager.set_theme_mode(mode)

    def _add_accent_row(self):
        self.color_btn = Button(
            "Choose Color",
            ButtonVariant.FILLED,
            on_click=self.change_accent_color,
        )
        self.color_btn.setMaximumWidth(150)

        self.accent_choice = RadioChoice(
            [(choice.value, choice.label) for choice in get_spec("accent_mode").choices],
            trailing=self.color_btn,
        )
        self.accent_mode_system, self.accent_mode_custom = self.accent_choice.radios()
        self._update_accent_btn_visibility()
        self.binder.add(
            "accent_mode",
            self.accent_choice,
            hint="",
            width=None,
            on_change=self._on_accent_mode_changed,
        )
        # The binder loads the stored mode without emitting valueChanged, so
        # evaluate the picker visibility again after the initial value is set.
        self._update_accent_btn_visibility()

    def _on_accent_mode_changed(self, mode):
        self._update_accent_btn_visibility()
        ThemeManager.set_accent_mode(mode)
        self.theme_refreshed.emit()

    def _add_toast_position_row(self):
        self.toast_position_combo = self.binder.add(
            "toast_position",
            hint="",
            width=None,
            on_change=self._on_toast_position_changed,
        )

    def _on_toast_position_changed(self, position):
        ToastManager.configure(position=position)

    def _update_accent_btn_visibility(self):
        self.color_btn.setVisible(self.accent_mode_custom.isChecked())

    def change_accent_color(self):
        color = QColorDialog.getColor(
            initial=QColor(ThemeManager.accent()),
            parent=self,
            title="Select Accent Color",
        )
        if color.isValid():
            self.config_manager.set("accent_color", color.name())
            self.config_manager.set("accent_mode", "custom")
            self.accent_choice.setValue("custom")
            self._update_accent_btn_visibility()
            ThemeManager.set_accent(color.name())
            self.theme_refreshed.emit()

    # ------------------------------------------------------------------
    # Lifecycle hooks used by SettingsView
    # ------------------------------------------------------------------
    def reload_from_config(self):
        self.binder.load()
        self._update_accent_btn_visibility()

    def set_advanced_visible(self, visible):
        self.binder.set_advanced_visible(visible)

    def refresh_styles(self, *args, **kwargs):
        self.setStyleSheet(Styles.get_group_box_style())
        self.form.refresh_styles()
        self.color_btn.refresh_styles()
        self.theme_mode_choice.refresh_styles()
        self.accent_choice.refresh_styles()

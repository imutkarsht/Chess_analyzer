"""Player accounts, credentials, and import/network settings."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.backend.api.import_limits import (
    clamp_games_limit,
    max_games_limit,
)
from src.backend.api.import_limits import (
    current_token as configured_token,
)
from src.gui.styles import Styles

from .background_card import BackgroundTaskCard
from .components import (
    CONTROL_WIDE,
    SettingsBinder,
    SettingsForm,
    make_checkbox,
    make_combo,
    make_line_edit,
)
from .helpers import create_icon_button
from .modern_widgets import ModernSliderCounter, PasswordFieldWrapper
from .profile_preview import ProfilePreview


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(Styles.get_divider_style())
    return line


def _status_style(color: str) -> str:
    return (
        f"font-size: 11px; color: {color}; background: transparent; "
        "border: none; padding: 2px 0px;"
    )


class _ProfileCard(BackgroundTaskCard):
    """Shared username + preview wiring for the two platform cards."""

    def __init__(self, title: str, platform: str, config_manager, parent=None):
        super().__init__(title, parent)
        self.config_manager = config_manager
        self.platform = platform
        self._preview_loaded = False
        self._preview_username = ""

    def _install_preview(self, input_widget) -> None:
        self.preview = ProfilePreview(self.platform, self)
        self.preview.setMaximumWidth(660)
        self.form.add_row("Profile", self.preview, width=None)
        input_widget.editingFinished.connect(self._refresh_preview)

    def _refresh_preview(self) -> None:
        username = self.username_input.text().strip()
        self._preview_username = username
        self._preview_loaded = True
        self.preview.load(username)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # SettingsView is built at launch but its pages stay hidden. Load the
        # preview only when the Integrations page is actually opened.
        if not self._preview_loaded:
            self._refresh_preview()

    def _reload_preview_if_changed(self) -> None:
        username = self.username_input.text().strip()
        if self._preview_loaded and username != self._preview_username:
            self._refresh_preview()


class ChessComCard(_ProfileCard):
    """Chess.com handle and public profile preview."""

    def __init__(self, config_manager, parent=None):
        super().__init__("Chess.com", "chesscom", config_manager, parent)
        self.setup_ui()

    def setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)

        self.form = SettingsForm(self)
        outer.addWidget(self.form)
        self.binder = SettingsBinder(self.config_manager, self.form, self)

        self.username_input = self.binder.add(
            "chesscom_username",
            make_line_edit("e.g. magnuscarlsen"),
            hint="Your Chess.com handle. Also used for one-click game imports.",
        )
        self.chesscom_input = self.username_input
        self._install_preview(self.username_input)

    def reload_from_config(self) -> None:
        self.binder.load()
        self._reload_preview_if_changed()

    def set_advanced_visible(self, visible: bool) -> None:
        self.binder.set_advanced_visible(visible)

    def refresh_styles(self, *args, **kwargs) -> None:
        self.setStyleSheet(Styles.get_group_box_style())
        self.form.refresh_styles()
        self.username_input.setStyleSheet(Styles.get_input_style())
        self.preview.refresh_styles()


class LichessCard(_ProfileCard):
    """Lichess handle, token, and online explorer toggle."""

    token_changed = pyqtSignal()

    def __init__(self, config_manager, parent=None):
        super().__init__("Lichess", "lichess", config_manager, parent)
        self.setup_ui()

    def setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)

        self.form = SettingsForm(self)
        outer.addWidget(self.form)
        self.binder = SettingsBinder(self.config_manager, self.form, self)

        self.username_input = self.binder.add(
            "lichess_username",
            make_line_edit("e.g. drnykterstein"),
            hint="Your Lichess handle. Also used for one-click game imports.",
        )
        self.lichess_input = self.username_input
        self._install_preview(self.username_input)

        self.lichess_token_input = PasswordFieldWrapper(self)
        self.lichess_token_input.setMaximumWidth(420)
        self.lichess_token_input.setPlaceholderText("lip_… (optional)")

        self.validate_token_btn = create_icon_button(
            "Validate", "fa5s.key", self._validate_token, self
        )
        self.validate_token_btn.setToolTip(
            "Check the token against your Lichess account."
        )

        self.token_status_label = QLabel()
        self.token_status_label.setWordWrap(True)
        self.token_status_label.setStyleSheet(
            _status_style(Styles.COLOR_TEXT_SECONDARY)
        )

        token_row = QWidget()
        token_row.setStyleSheet(Styles.get_transparent_label_style())
        token_layout = QVBoxLayout(token_row)
        token_layout.setContentsMargins(0, 0, 0, 0)
        token_layout.setSpacing(4)
        token_line = QHBoxLayout()
        token_line.setContentsMargins(0, 0, 0, 0)
        token_line.setSpacing(8)
        token_line.addWidget(self.lichess_token_input)
        token_line.addWidget(self.validate_token_btn)
        token_line.addStretch(1)
        token_layout.addLayout(token_line)
        token_layout.addWidget(self.token_status_label)

        self.binder.add(
            "lichess_token",
            self.lichess_token_input,
            container=token_row,
            width=None,
            hint=(
                "Optional. Raises the import cap from 20 to 30 games, unlocks "
                "private archives, and enables the online opening explorer."
            ),
        )
        self.lichess_token_input.editingFinished.connect(self._on_token_committed)
        self.lichess_token_input.line_edit.textChanged.connect(
            self._on_token_text_changed
        )

        self.explorer_checkbox = self.binder.add(
            "lichess_explorer_enabled",
            make_checkbox("Use the online Lichess opening explorer (token)"),
            width=None,
            inline_hint=False,
        )
        self.register_busy_widgets(self.validate_token_btn)

    def current_token(self) -> str:
        return (
            self.lichess_token_input.text().strip()
            or configured_token(self.config_manager)
        ).strip()

    def _on_token_text_changed(self, text: str) -> None:
        # Clear stale validation text as soon as the token changes. Raising the
        # import cap immediately also lets the user enter 21–30 before leaving
        # the field; lowering waits for editingFinished so editing is not jerky.
        self.token_status_label.setText("")
        if text.strip():
            self.token_changed.emit()

    def _on_token_committed(self) -> None:
        self.token_status_label.setText("")
        self.token_changed.emit()

    def _validate_token(self) -> None:
        token = self.current_token()
        if not token:
            self.token_status_label.setStyleSheet(
                _status_style(Styles.COLOR_TEXT_SECONDARY)
            )
            self.token_status_label.setText("Enter a token first.")
            return

        self.token_status_label.setStyleSheet(
            _status_style(Styles.COLOR_TEXT_SECONDARY)
        )
        self.token_status_label.setText("Checking token…")

        # Imported here so the settings package does not pull the API stack in
        # until the user actually asks for a network check.
        from src.backend.api.lichess_api import LichessAPI

        self.run_task(
            lambda: LichessAPI().get_account(token),
            self._on_account_checked,
            self._on_account_error,
        )

    def _on_account_checked(self, result: object) -> None:
        data, status = result if isinstance(result, tuple) else (None, "error")
        if status == "ok" and isinstance(data, dict) and data.get("username"):
            self.token_status_label.setStyleSheet(
                _status_style(Styles.COLOR_GOOD)
            )
            self.token_status_label.setText(
                f"✓ Valid — signed in as {data['username']}"
            )
        elif status == "unauthorized":
            self.token_status_label.setStyleSheet(
                _status_style(Styles.COLOR_BLUNDER)
            )
            self.token_status_label.setText("✗ Token rejected by Lichess.")
        elif status == "offline":
            self.token_status_label.setStyleSheet(
                _status_style(Styles.COLOR_ENGINE_BUSY)
            )
            self.token_status_label.setText("Can't reach Lichess right now.")
        else:
            self.token_status_label.setStyleSheet(
                _status_style(Styles.COLOR_BLUNDER)
            )
            self.token_status_label.setText("✗ Token check failed.")

    def _on_account_error(self, _message: str) -> None:
        self.token_status_label.setStyleSheet(
            _status_style(Styles.COLOR_BLUNDER)
        )
        self.token_status_label.setText("✗ Token check failed.")

    def reload_from_config(self) -> None:
        self.binder.load()
        self.token_status_label.setText("")
        self._reload_preview_if_changed()

    def set_advanced_visible(self, visible: bool) -> None:
        self.binder.set_advanced_visible(visible)

    def refresh_styles(self, *args, **kwargs) -> None:
        self.setStyleSheet(Styles.get_group_box_style())
        self.form.refresh_styles()
        self.username_input.setStyleSheet(Styles.get_input_style())
        self.lichess_token_input.refresh_styles()
        self.validate_token_btn.refresh_styles()
        self.token_status_label.setStyleSheet(
            _status_style(Styles.COLOR_TEXT_SECONDARY)
        )
        self.preview.refresh_styles()


class ImportNetworkCard(QGroupBox):
    """Import cap and profile cache policy."""

    def __init__(self, config_manager, token_provider, parent=None):
        super().__init__("Import & Network", parent)
        self.config_manager = config_manager
        self._token_provider = token_provider
        self.setStyleSheet(Styles.get_group_box_style())
        self.setup_ui()

    def setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)

        self.form = SettingsForm(self)
        outer.addWidget(self.form)
        self.binder = SettingsBinder(self.config_manager, self.form, self)

        self.games_limit_input = ModernSliderCounter(
            1,
            max_games_limit(self._token_provider()),
            step=1,
            value=20,
            parent=self,
        )
        self.binder.add(
            "api_games_limit",
            self.games_limit_input,
            hint=(
                "Recent games fetched per import. The cap is 20 anonymously "
                "and 30 with a Lichess API token."
            ),
            width=CONTROL_WIDE,
            on_change=self._on_games_limit_changed,
        )

        self.cache_ttl_combo = self.binder.add(
            "profile_cache_ttl_hours",
            make_combo(180),
            width=180,
        )
        self.register_styles()

    def register_styles(self) -> None:
        self.setStyleSheet(Styles.get_group_box_style())

    def apply_games_limit(self, value) -> str:
        """Clamp, persist, and sync the import cap; return a warning or ""."""
        try:
            requested = max(1, int(float(value)))
        except (TypeError, ValueError):
            requested = 20
        limit = clamp_games_limit(requested, self._token_provider())
        self.config_manager.set("api_games_limit", limit)
        if str(limit) != self.games_limit_input.text().strip():
            self.games_limit_input.setText(str(limit))

        if limit == requested:
            return ""
        if max_games_limit(self._token_provider()) == 30:
            return (
                "Games limit capped at 30 (the maximum allowed when a "
                "Lichess API token is configured)."
            )
        return (
            "Games limit capped at 20. Add a Lichess API token in the Lichess "
            "card to raise the cap to 30 games."
        )

    def _on_games_limit_changed(self, value) -> None:
        self.apply_games_limit(value)

    def set_token_state(self) -> None:
        """React to token edits by widening or narrowing the slider."""
        maximum = max_games_limit(self._token_provider())
        previous_max = self.games_limit_input.max_val
        self.games_limit_input.set_maximum(maximum)
        if int(self.games_limit_input.value()) > maximum:
            self.apply_games_limit(maximum)
        elif maximum != previous_max:
            # Keep a previously clamped value from being silently re-raised.
            self.apply_games_limit(self.games_limit_input.text().strip())

    def reload_from_config(self) -> None:
        self.binder.load()
        self.set_token_state()

    def set_advanced_visible(self, visible: bool) -> None:
        self.binder.set_advanced_visible(visible)

    def refresh_styles(self, *args, **kwargs) -> None:
        self.register_styles()
        self.form.refresh_styles()
        if hasattr(self.cache_ttl_combo, "setStyleSheet"):
            self.cache_ttl_combo.setStyleSheet(Styles.get_combobox_style())
        if hasattr(self.games_limit_input, "refresh_styles"):
            self.games_limit_input.refresh_styles()


class PlayerSettings(QWidget):
    """The three Integrations cards, kept together for page wiring."""

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        self.chesscom_card = ChessComCard(config_manager, self)
        self.lichess_card = LichessCard(config_manager, self)
        self.import_network_card = ImportNetworkCard(
            config_manager, self.lichess_card.current_token, self
        )
        self.cards = (
            self.chesscom_card,
            self.lichess_card,
            self.import_network_card,
        )

        for index, card in enumerate(self.cards):
            if index:
                layout.addWidget(_divider())
            layout.addWidget(card)
        layout.addStretch(1)

        self.lichess_card.token_changed.connect(
            self.import_network_card.set_token_state
        )

        # Backwards-compatible aliases used by SettingsView and tests.
        self.chesscom_input = self.chesscom_card.chesscom_input
        self.lichess_input = self.lichess_card.lichess_input
        self.lichess_token_input = self.lichess_card.lichess_token_input
        self.games_limit_input = self.import_network_card.games_limit_input

    def reload_from_config(self) -> None:
        for card in self.cards:
            card.reload_from_config()
        self.import_network_card.set_token_state()

    def set_advanced_visible(self, visible: bool) -> None:
        for card in self.cards:
            card.set_advanced_visible(visible)

    def apply_games_limit(self, value) -> str:
        return self.import_network_card.apply_games_limit(value)

    def commit_all(self) -> None:
        for card in self.cards:
            binder = getattr(card, "binder", None)
            if binder is not None:
                binder.commit_all()
        # A token edit can lower the permitted import cap; keep the slider and
        # the saved limit in sync even when the field never lost focus.
        self.import_network_card.set_token_state()

    def refresh_styles(self, *args, **kwargs) -> None:
        for card in self.cards:
            card.refresh_styles()

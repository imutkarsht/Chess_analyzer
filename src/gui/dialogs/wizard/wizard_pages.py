import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from src.constants import PROVIDERS
from src.gui.components import Button, ButtonSize, ButtonVariant
from src.gui.styles import Styles
from src.utils.path_utils import get_resource_path

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False


def build_gatekeeper_page(wizard) -> QWidget:
    page = QWidget()
    page.setObjectName("wizardPage")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(60, 60, 60, 40)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    wizard.gatekeeper_label = QLabel()
    wizard.gatekeeper_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    wizard.gatekeeper_label.setProperty("class", "wizard-heading")
    layout.addWidget(wizard.gatekeeper_label)

    wizard.gatekeeper_detail = QLabel()
    wizard.gatekeeper_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
    wizard.gatekeeper_detail.setProperty("class", "wizard-helper")
    layout.addWidget(wizard.gatekeeper_detail)

    wizard.gatekeeper_timer = QTimer(wizard)
    wizard.gatekeeper_timer.setSingleShot(True)
    wizard.gatekeeper_timer.timeout.connect(lambda: wizard._show_page(1))
    return page


def build_welcome_page(wizard) -> QWidget:
    page = QWidget()
    page.setObjectName("wizardPage")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(60, 40, 60, 40)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.setSpacing(20)

    layout.addStretch(1)

    logo_path = get_resource_path(os.path.join("assets", "images", "logo.png"))
    if os.path.exists(logo_path):
        logo_label = QLabel()
        pixmap = QPixmap(logo_path).scaled(
            110, 110,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        logo_label.setPixmap(pixmap)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo_label)

    title = QLabel("Chess Analyzer Pro")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title.setProperty("class", "wizard-title")
    layout.addWidget(title)

    subtitle = QLabel(
        "Analyze your games, uncover your blind spots, and track your performance.\n"
        "Let's get your workspace customized in just a couple minutes."
    )
    subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
    subtitle.setWordWrap(True)
    subtitle.setProperty("class", "wizard-helper")
    layout.addWidget(subtitle)

    btn_space = QWidget()
    btn_space.setFixedHeight(12)
    layout.addWidget(btn_space)

    wizard.get_started_btn = Button(
        "Get Started",
        ButtonVariant.PRIMARY,
        size=ButtonSize.LG,
        on_click=lambda: wizard._go_to(2),
    )
    wizard.get_started_btn.setFixedHeight(44)
    layout.addWidget(wizard.get_started_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    layout.addStretch(1)
    return page


def build_profile_page(wizard) -> QWidget:
    page = QWidget()
    page.setObjectName("wizardPage")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(50, 30, 50, 30)
    layout.setSpacing(10)

    heading = QLabel("Link Chess Accounts")
    heading.setProperty("class", "wizard-heading")
    layout.addWidget(heading)

    helper = QLabel(
        "Optional: Enter your handles so Chess Analyzer Pro can pre-fill game fetch dialogues "
        "and aggregate your stats across games. Your credentials are never stored."
    )
    helper.setWordWrap(True)
    helper.setProperty("class", "wizard-helper")
    layout.addWidget(helper)

    # Card container
    card = QFrame()
    card.setObjectName("profileCard")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(16, 16, 16, 16)
    card_layout.setSpacing(10)

    # Chess.com
    lbl = QLabel("Chess.com Username")
    lbl.setProperty("class", "wizard-label")
    card_layout.addWidget(lbl)
    wizard.chesscom_input = QLineEdit()
    wizard.chesscom_input.setPlaceholderText("e.g. magnuscarlsen")
    wizard.chesscom_input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    card_layout.addWidget(wizard.chesscom_input)

    # Lichess
    lbl = QLabel("Lichess Username")
    lbl.setProperty("class", "wizard-label")
    card_layout.addWidget(lbl)
    wizard.lichess_input = QLineEdit()
    wizard.lichess_input.setPlaceholderText("e.g. drnykterstein")
    wizard.lichess_input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    card_layout.addWidget(wizard.lichess_input)

    # Lichess Token
    tok_row = QHBoxLayout()
    lbl = QLabel("Lichess Personal API Token")
    lbl.setProperty("class", "wizard-label")
    tok_row.addWidget(lbl)
    tok_row.addStretch()

    wizard.lichess_tok_link = QLabel()
    wizard.lichess_tok_link.setOpenExternalLinks(True)
    wizard._update_lichess_tok_link()
    tok_row.addWidget(wizard.lichess_tok_link)
    card_layout.addLayout(tok_row)

    wizard.lichess_token_input = QLineEdit()
    wizard.lichess_token_input.setPlaceholderText("lip_...")
    wizard.lichess_token_input.setEchoMode(QLineEdit.EchoMode.Password)
    wizard.lichess_token_input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    card_layout.addWidget(wizard.lichess_token_input)

    hint = QLabel(
        "Optional. Raises the import limit from 20 to 30 games, unlocks "
        "private archive downloads, and enables the online opening explorer."
    )
    hint.setProperty("class", "wizard-hint")
    card_layout.addWidget(hint)

    layout.addWidget(card)
    layout.addStretch()
    page._on_show = lambda: wizard.chesscom_input.setFocus()
    return page


def build_appearance_page(wizard) -> QWidget:
    page = QWidget()
    page.setObjectName("wizardPage")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(50, 30, 50, 30)
    layout.setSpacing(10)

    heading = QLabel("Appearance & Themes")
    heading.setProperty("class", "wizard-heading")
    layout.addWidget(heading)

    helper = QLabel("Customize the board aesthetic and application accent colors to match your taste.")
    helper.setWordWrap(True)
    helper.setProperty("class", "wizard-helper")
    layout.addWidget(helper)

    card = QFrame()
    card.setObjectName("appearanceCard")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(16, 16, 16, 16)
    card_layout.setSpacing(12)

    # App theme mode (Dark / Light / System)
    mode_lbl = QLabel("App Theme")
    mode_lbl.setProperty("class", "wizard-label")
    card_layout.addWidget(mode_lbl)

    wizard.wizard_theme_mode_combo = QComboBox()
    wizard.wizard_theme_mode_combo.addItem("System (Follow OS)", "system")
    wizard.wizard_theme_mode_combo.addItem("Dark Theme", "dark")
    wizard.wizard_theme_mode_combo.addItem("Light Theme", "light")
    wizard.wizard_theme_mode_combo.setStyleSheet(Styles.get_combobox_style())
    wizard.wizard_theme_mode_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    wizard.wizard_theme_mode_combo.currentIndexChanged.connect(lambda: _on_theme_mode_changed(wizard))
    card_layout.addWidget(wizard.wizard_theme_mode_combo)

    theme_lbl = QLabel("Board Theme")
    theme_lbl.setProperty("class", "wizard-label")
    card_layout.addWidget(theme_lbl)
    wizard.wizard_theme_combo = QComboBox()
    wizard.wizard_theme_combo.addItems(list(Styles.BOARD_THEMES.keys()))
    wizard.wizard_theme_combo.setCurrentText("Green")
    wizard.wizard_theme_combo.setStyleSheet(Styles.get_combobox_style())
    wizard.wizard_theme_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    card_layout.addWidget(wizard.wizard_theme_combo)

    accent_lbl = QLabel("Accent Color")
    accent_lbl.setProperty("class", "wizard-label")
    card_layout.addWidget(accent_lbl)

    accent_row = QHBoxLayout()
    wizard.wizard_accent_btn = Button(
        variant=ButtonVariant.FILLED,
        align="left",
        on_click=lambda: _pick_accent_color(wizard),
    )
    wizard.wizard_accent_btn.setFixedHeight(38)
    accent_row.addWidget(wizard.wizard_accent_btn, 1)

    # Reset button
    wizard.wizard_reset_accent_btn = Button(
        "Reset to Default",
        ButtonVariant.FILLED,
        on_click=lambda: _reset_accent_color(wizard),
    )
    wizard.wizard_reset_accent_btn.setFixedHeight(38)
    accent_row.addWidget(wizard.wizard_reset_accent_btn)

    card_layout.addLayout(accent_row)
    layout.addWidget(card)

    wizard.wizard_accent_color = "#FF9500"
    wizard.wizard_accent_mode = "system"
    _apply_accent_button_style(wizard, wizard.wizard_accent_color, wizard.wizard_accent_mode)
    layout.addStretch()
    return page


def _on_theme_mode_changed(wizard):
    idx = wizard.wizard_theme_mode_combo.currentIndex()
    mode = wizard.wizard_theme_mode_combo.itemData(idx) or "system"
    wizard.settings["theme_mode"] = mode
    from src.gui.theme import ThemeManager
    ThemeManager.set_theme_mode(mode)
    wizard.refresh_accent()


def _pick_accent_color(wizard):
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import QColorDialog
    color = QColorDialog.getColor(initial=QColor(wizard.wizard_accent_color), parent=wizard, title="Select Accent Color")
    if color.isValid():
        _apply_accent(wizard, color.name(), mode="custom")


def _reset_accent_color(wizard):
    from src.gui.theme import ThemeManager
    ThemeManager.set_accent_mode("system")
    detected = ThemeManager.accent() or "#FF9500"
    _apply_accent(wizard, detected, mode="system")


def _apply_accent_button_style(wizard, hex_code: str, mode: str):
    if not hasattr(wizard, "wizard_accent_btn"):
        return
    btn = wizard.wizard_accent_btn
    if mode == "custom":
        btn.set_variant(ButtonVariant.PRIMARY)
        btn.set_accent(hex_code)
        btn.setText(hex_code)
    else:
        btn.set_variant(ButtonVariant.FILLED)
        btn.set_accent(None)
        btn.setText("System Default Accent")


def _apply_accent(wizard, hex_code: str, mode: str = "custom"):
    wizard.wizard_accent_color = hex_code
    wizard.wizard_accent_mode = mode
    from src.gui.theme import ThemeManager

    if mode == "custom":
        Styles.set_accent_color(hex_code)
    else:
        ThemeManager.set_accent_mode("system")

    _apply_accent_button_style(wizard, hex_code, mode)
    wizard.refresh_accent()


def build_stockfish_page(wizard) -> QWidget:
    page = QWidget()
    page.setObjectName("wizardPage")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(50, 30, 50, 30)
    layout.setSpacing(10)

    heading = QLabel("Stockfish Chess Engine")
    heading.setProperty("class", "wizard-heading")
    layout.addWidget(heading)

    helper = QLabel(
        "Stockfish runs 100% locally on your machine for grandmaster-level evaluation, "
        "tactical discovery, and move classification without any internet connection."
    )
    helper.setWordWrap(True)
    helper.setProperty("class", "wizard-helper")
    layout.addWidget(helper)

    card = QFrame()
    card.setObjectName("stockfishCard")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(18, 18, 18, 18)
    card_layout.setSpacing(12)

    status_row = QHBoxLayout()
    status_row.setSpacing(10)
    wizard.sf_icon_label = QLabel()
    wizard.sf_icon_label.setFixedSize(24, 24)
    if HAS_QTAWESOME:
        wizard.sf_icon_label.setPixmap(qta.icon("fa5s.cog", color=Styles.COLOR_TEXT_MUTED).pixmap(24, 24))
    status_row.addWidget(wizard.sf_icon_label)

    status_text_col = QVBoxLayout()
    status_text_col.setSpacing(3)
    wizard.sf_status = QLabel("Checking engine configuration...")
    wizard.sf_status.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; background: transparent;")
    status_text_col.addWidget(wizard.sf_status)

    wizard.sf_detail = QLabel("")
    wizard.sf_detail.setWordWrap(True)
    wizard.sf_detail.setProperty("class", "wizard-helper")
    status_text_col.addWidget(wizard.sf_detail)
    status_row.addLayout(status_text_col, 1)
    card_layout.addLayout(status_row)

    # Progress bar with stage description
    wizard.sf_progress_desc = QLabel("")
    wizard.sf_progress_desc.setProperty("class", "wizard-hint")
    wizard.sf_progress_desc.setVisible(False)
    card_layout.addWidget(wizard.sf_progress_desc)

    wizard.sf_progress = QProgressBar()
    wizard.sf_progress.setStyleSheet(Styles.get_progress_bar_style())
    wizard.sf_progress.setVisible(False)
    card_layout.addWidget(wizard.sf_progress)

    # Action buttons row
    btn_row = QHBoxLayout()
    btn_row.setSpacing(10)

    wizard.sf_download_btn = Button(
        "Download Stockfish",
        ButtonVariant.PRIMARY,
        on_click=wizard._download_stockfish,
    )
    wizard.sf_download_btn.setFixedHeight(38)
    wizard.sf_download_btn.setVisible(False)
    btn_row.addWidget(wizard.sf_download_btn)

    wizard.sf_cancel_btn = Button(
        "Cancel",
        ButtonVariant.FILLED,
        on_click=wizard._cancel_stockfish_download,
    )
    wizard.sf_cancel_btn.setFixedHeight(38)
    wizard.sf_cancel_btn.setVisible(False)
    btn_row.addWidget(wizard.sf_cancel_btn)

    wizard.sf_browse_btn = Button(
        "Browse...",
        ButtonVariant.FILLED,
        on_click=lambda: _browse_stockfish_binary(wizard),
    )
    wizard.sf_browse_btn.setFixedHeight(38)
    btn_row.addWidget(wizard.sf_browse_btn)

    btn_row.addStretch()
    card_layout.addLayout(btn_row)

    layout.addWidget(card)
    layout.addStretch()
    page._on_show = wizard._detect_stockfish
    return page


def _browse_stockfish_binary(wizard):
    file_path, _ = QFileDialog.getOpenFileName(
        wizard,
        "Select Stockfish Engine Binary",
        "",
        "Executable Files (*);;All Files (*)",
    )
    if file_path:
        wizard._set_custom_stockfish_path(file_path)


def build_llm_page(wizard) -> QWidget:
    page = QWidget()
    page.setObjectName("wizardPage")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(50, 24, 50, 24)
    layout.setSpacing(8)

    heading = QLabel("AI Game Coach (Optional)")
    heading.setProperty("class", "wizard-heading")
    layout.addWidget(heading)

    helper = QLabel(
        "Connect an AI provider for grandmaster-style narrative summaries, tactical feedback, "
        "and customized improvement tips. Skip anytime and configure later in Settings."
    )
    helper.setWordWrap(True)
    helper.setProperty("class", "wizard-helper")
    layout.addWidget(helper)

    card = QFrame()
    card.setObjectName("llmCard")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(16, 14, 16, 14)
    card_layout.setSpacing(8)

    # Provider dropdown row
    prov_row = QHBoxLayout()
    lbl = QLabel("Provider:")
    lbl.setProperty("class", "wizard-label")
    prov_row.addWidget(lbl)

    wizard.llm_provider_combo = QComboBox()
    for prov_key, prov_info in PROVIDERS.items():
        wizard.llm_provider_combo.addItem(prov_info.get("label", prov_key.title()), prov_key)
    wizard.llm_provider_combo.setStyleSheet(Styles.get_combobox_style())
    wizard.llm_provider_combo.currentIndexChanged.connect(lambda: _on_provider_changed(wizard))
    prov_row.addWidget(wizard.llm_provider_combo, 1)

    wizard.llm_portal_link = QLabel()
    wizard.llm_portal_link.setOpenExternalLinks(True)
    prov_row.addWidget(wizard.llm_portal_link)
    card_layout.addLayout(prov_row)

    # API Key row
    wizard.llm_key_label = QLabel("API Key")
    wizard.llm_key_label.setProperty("class", "wizard-label")
    card_layout.addWidget(wizard.llm_key_label)

    wizard.llm_key_input = QLineEdit()
    wizard.llm_key_input.setPlaceholderText("gsk_...")
    wizard.llm_key_input.setEchoMode(QLineEdit.EchoMode.Password)
    card_layout.addWidget(wizard.llm_key_input)

    # Model input row
    wizard.llm_model_label = QLabel("Model")
    wizard.llm_model_label.setProperty("class", "wizard-label")
    card_layout.addWidget(wizard.llm_model_label)

    wizard.llm_model_input = QLineEdit()
    wizard.llm_model_input.setPlaceholderText("llama-3.3-70b-versatile")
    card_layout.addWidget(wizard.llm_model_input)

    # Base URL row (shown for custom / local)
    wizard.llm_base_url_label = QLabel("Base URL")
    wizard.llm_base_url_label.setProperty("class", "wizard-label")
    card_layout.addWidget(wizard.llm_base_url_label)

    wizard.llm_base_url_input = QLineEdit()
    wizard.llm_base_url_input.setPlaceholderText("https://api.openai.com/v1")
    card_layout.addWidget(wizard.llm_base_url_input)

    # Test button & result row
    test_row = QHBoxLayout()
    wizard.llm_test_btn = Button(
        "Test Connection",
        ButtonVariant.FILLED,
        on_click=wizard._test_llm,
    )
    wizard.llm_test_btn.setFixedHeight(36)
    test_row.addWidget(wizard.llm_test_btn)

    wizard.llm_test_result = QLabel("")
    wizard.llm_test_result.setWordWrap(True)
    test_row.addWidget(wizard.llm_test_result, 1)
    card_layout.addLayout(test_row)

    layout.addWidget(card)
    layout.addStretch()

    page._on_show = lambda: _update_llm_ui_hints(wizard)
    return page


def _update_llm_ui_hints(wizard):
    idx = wizard.llm_provider_combo.currentIndex()
    prov_key = wizard.llm_provider_combo.itemData(idx) or "groq"
    prov_info = PROVIDERS.get(prov_key, PROVIDERS["custom"])

    key_ph = prov_info.get("key_placeholder", "")
    model_ph = prov_info.get("model_placeholder", "")
    help_url = prov_info.get("help_url", "")

    wizard.llm_key_input.setPlaceholderText(key_ph)
    wizard.llm_model_input.setPlaceholderText(model_ph)

    # Show/hide base URL field for Custom and LM Studio
    is_custom = prov_key in ("custom", "lmstudio")
    wizard.llm_base_url_label.setVisible(is_custom)
    wizard.llm_base_url_input.setVisible(is_custom)

    if help_url:
        wizard.llm_portal_link.setText(
            f'<a href="{help_url}" style="color: {Styles.COLOR_ACCENT}; text-decoration: none;">Get Key ↗</a>'
        )
        wizard.llm_portal_link.setVisible(True)
    else:
        wizard.llm_portal_link.setVisible(False)


def _on_provider_changed(wizard):
    idx = wizard.llm_provider_combo.currentIndex()
    prov_key = wizard.llm_provider_combo.itemData(idx) or "groq"
    prov_info = PROVIDERS.get(prov_key, PROVIDERS["custom"])

    _update_llm_ui_hints(wizard)

    prev_prov = getattr(wizard, "_last_selected_provider", None)
    wizard._last_selected_provider = prov_key

    # Only replace field contents if provider was changed to a different one
    if prev_prov is not None and prev_prov != prov_key:
        wizard.llm_model_input.setText(prov_info.get("default_model", ""))
        wizard.llm_base_url_input.setText(prov_info.get("base_url", ""))
        wizard.llm_key_input.setText("")
        wizard.llm_test_result.setText("")
    elif not wizard.llm_model_input.text().strip():
        # First time setup / blank input: seed defaults
        wizard.llm_model_input.setText(prov_info.get("default_model", ""))
        if not wizard.llm_base_url_input.text().strip():
            wizard.llm_base_url_input.setText(prov_info.get("base_url", ""))


def build_done_page(wizard) -> QWidget:
    page = QWidget()
    page.setObjectName("wizardPage")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(50, 24, 50, 24)
    layout.setSpacing(0)

    layout.addStretch(1)

    # Success Icon
    wizard.done_icon_label = QLabel()
    wizard.done_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    wizard._update_done_icon()
    layout.addWidget(wizard.done_icon_label)

    layout.addSpacing(14)

    heading = QLabel("You're all set!")
    heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
    heading.setProperty("class", "wizard-title")
    layout.addWidget(heading)

    layout.addSpacing(4)

    wizard.ready_label = QLabel("Ready to analyze your games!")
    wizard.ready_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    wizard.ready_label.setStyleSheet(
        f"font-size: 13px; color: {Styles.COLOR_ACCENT}; font-weight: bold; background: transparent;"
    )
    layout.addWidget(wizard.ready_label)

    layout.addSpacing(16)

    # Summary card container
    summary_card = QFrame()
    summary_card.setObjectName("summaryCard")
    card_layout = QVBoxLayout(summary_card)
    card_layout.setContentsMargins(18, 12, 18, 12)
    card_layout.setSpacing(0)
    layout.addWidget(summary_card)

    wizard._done_card_layout = card_layout
    wizard._done_summary_card = summary_card

    layout.addSpacing(18)

    wizard.done_btn = Button(
        "Launch Chess Analyzer Pro",
        ButtonVariant.PRIMARY,
        size=ButtonSize.LG,
        on_click=wizard._on_finish,
    )
    wizard.done_btn.setFixedHeight(44)
    layout.addWidget(wizard.done_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    layout.addStretch(1)

    wizard.summary_label = QLabel("")
    wizard.summary_label.setVisible(False)
    layout.addWidget(wizard.summary_label)

    def _on_done_show():
        """Rebuild the summary card rows with QtAwesome icons."""
        while wizard._done_card_layout.count():
            item = wizard._done_card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        raw = wizard.summary_label.text()
        items = raw.split("\n") if raw else []
        valid_items = [x for x in items if x.strip()]

        for i, item in enumerate(valid_items):
            is_warning = item.startswith("⚠")
            is_check = item.startswith("✓")

            if is_warning:
                icon_name = "fa5s.exclamation-triangle"
                icon_color = Styles.COLOR_MISTAKE
                text = item[1:].strip()
            elif is_check:
                icon_name = "fa5s.check-circle"
                icon_color = Styles.COLOR_BEST
                text = item[1:].strip()
            else:
                icon_name = "fa5s.info-circle"
                icon_color = Styles.COLOR_TEXT_MUTED
                text = item.strip()

            row = QWidget()
            row.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 8, 0, 8)
            row_layout.setSpacing(12)

            icon_lbl = QLabel()
            icon_lbl.setFixedSize(20, 20)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if HAS_QTAWESOME:
                icon_lbl.setPixmap(qta.icon(icon_name, color=icon_color).pixmap(18, 18))
            else:
                icon_lbl.setText("✓" if is_check else ("⚠" if is_warning else "•"))
                icon_lbl.setStyleSheet(f"color: {icon_color}; font-weight: bold; background: transparent;")
            row_layout.addWidget(icon_lbl)

            text_lbl = QLabel(text)
            text_lbl.setWordWrap(True)
            text_lbl.setStyleSheet(
                f"font-size: 13px; color: {Styles.COLOR_TEXT_PRIMARY}; background: transparent;"
            )
            row_layout.addWidget(text_lbl, 1)

            wizard._done_card_layout.addWidget(row)

            if i < len(valid_items) - 1:
                divider = QWidget()
                divider.setFixedHeight(1)
                divider.setStyleSheet(f"background-color: {Styles.COLOR_BORDER}; border: none;")
                wizard._done_card_layout.addWidget(divider)

    wizard._on_done_show = _on_done_show
    page._on_show = _on_done_show
    return page

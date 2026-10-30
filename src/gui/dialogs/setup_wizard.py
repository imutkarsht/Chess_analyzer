import os
import subprocess
import sys

from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QStackedWidget,
    QVBoxLayout,
)

from src.backend.analysis.engine import invalidate_engine_cache, resolve_engine_path
from src.backend.engine.downloader import (
    download_and_extract,
    get_download_candidates,
    probe_engine_binary,
    try_package_manager_install,
)
from src.constants import DEFAULT_BOARD_THEME, PROVIDERS
from src.gui.dialogs.wizard.wizard_nav_bar import WizardNavBar
from src.gui.dialogs.wizard.wizard_pages import (
    build_appearance_page,
    build_done_page,
    build_gatekeeper_page,
    build_llm_page,
    build_profile_page,
    build_stockfish_page,
    build_welcome_page,
)
from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.utils.logger import logger
from src.utils.path_utils import get_engine_data_dir

try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False


class StockfishDownloadWorker(QThread):
    progress = pyqtSignal(int)
    stage = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, dest_dir, parent=None):
        super().__init__(parent)
        self.dest_dir = dest_dir
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        import shutil

        # 1. On macOS, try installing Stockfish via Homebrew first
        if sys.platform == "darwin":
            brew_path = shutil.which("brew")
            if not brew_path:
                for p in ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"]:
                    if os.path.isfile(p) and os.access(p, os.X_OK):
                        brew_path = p
                        break

            if brew_path:
                self.stage.emit("Checking Homebrew installation...")
                self.progress.emit(15)
                logger.info("StockfishDownloadWorker: attempting Homebrew installation via %s", brew_path)
                try:
                    result = subprocess.run(
                        [brew_path, "install", "stockfish"],
                        capture_output=True, text=True, timeout=120
                    )
                    if self._is_cancelled:
                        return

                    if result.returncode == 0:
                        for candidate in ["/opt/homebrew/bin/stockfish", "/usr/local/bin/stockfish"]:
                            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                                self.progress.emit(100)
                                self.finished.emit(candidate)
                                return
                        which_sf = shutil.which("stockfish")
                        if which_sf and os.path.isfile(which_sf) and os.access(which_sf, os.X_OK):
                            self.progress.emit(100)
                            self.finished.emit(which_sf)
                            return
                    logger.warning("StockfishDownloadWorker: Homebrew installation failed: %s", result.stderr)
                except Exception as e:
                    logger.warning("StockfishDownloadWorker: Homebrew installation crashed: %s", e)

        if self._is_cancelled:
            return

        # 2. Github Releases download fallback
        download_error = None
        try:
            self.stage.emit("Resolving latest release candidate...")
            candidates = get_download_candidates()
            if not candidates:
                raise RuntimeError("No compatible Stockfish download was found for this platform")

            if self._is_cancelled:
                return

            self.stage.emit("Downloading Stockfish binary...")

            def progress_callback(downloaded, total):
                if self._is_cancelled:
                    raise RuntimeError("Download cancelled by user")
                pct = int(downloaded / total * 100) if total else 0
                self.progress.emit(pct)

            binary_path = download_and_extract(
                candidates[0],
                self.dest_dir,
                progress_callback=progress_callback,
                fallback_urls=candidates[1:],
            )
            if self._is_cancelled:
                return

            self.stage.emit("Verifying engine binary...")
            logger.info("StockfishDownloadWorker: successfully downloaded Stockfish to %s", binary_path)
            self.finished.emit(binary_path)
            return
        except Exception as e:
            if self._is_cancelled:
                logger.info("StockfishDownloadWorker: cancelled")
                return
            download_error = e
            logger.warning("StockfishDownloadWorker: GitHub download failed: %s", e)

        # 3. Distro package manager fallback (Linux and friends)
        if not self._is_cancelled:
            self.stage.emit("Attempting system package manager fallback...")
            pm_path = try_package_manager_install()
            if pm_path:
                logger.info("StockfishDownloadWorker: package manager installed Stockfish to %s", pm_path)
                self.finished.emit(pm_path)
                return

        logger.error("StockfishDownloadWorker: all download strategies failed: %s", download_error)
        self.error.emit(str(download_error))


class LLMTestWorker(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, api_key: str, base_url: str, model: str, parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def run(self):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key or "not-needed", base_url=self.base_url)
            client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Reply with just the word: ok"}],
                max_tokens=10,
                timeout=15.0,
            )
            self.finished.emit(True, "Connection successful")
        except Exception as e:
            self.finished.emit(False, str(e))


class SetupWizard(QDialog):
    WIZARD_WIDTH = 640
    WIZARD_HEIGHT = 560

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.settings = {}
        self.current_page = 0
        self._llm_worker = None
        self._download_worker = None

        self.setWindowTitle("Chess Analyzer Pro - Quick Setup")
        self.setMinimumSize(self.WIZARD_WIDTH, self.WIZARD_HEIGHT)
        self.resize(self.WIZARD_WIDTH, self.WIZARD_HEIGHT)

        self._build_ui()
        self.setStyleSheet(self._build_stylesheet())
        self._populate_from_config()

        # Gatekeeper skip check for non-macOS or non-frozen runs
        is_macos_frozen = getattr(sys, "frozen", False) and sys.platform == "darwin"
        initial_page = 0 if is_macos_frozen else 1
        self._show_page(initial_page)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setObjectName("wizardStack")
        self.stack.addWidget(build_gatekeeper_page(self))   # 0
        self.stack.addWidget(build_welcome_page(self))      # 1
        self.stack.addWidget(build_profile_page(self))      # 2
        self.stack.addWidget(build_appearance_page(self))   # 3
        self.stack.addWidget(build_stockfish_page(self))    # 4
        self.stack.addWidget(build_llm_page(self))          # 5
        self.stack.addWidget(build_done_page(self))         # 6
        layout.addWidget(self.stack, 1)

        self.nav_bar = WizardNavBar()
        self.nav_bar.next_btn.clicked.connect(self._on_next)
        self.nav_bar.back_btn.clicked.connect(self._on_back)
        self.nav_bar.skip_btn.clicked.connect(self._on_skip)
        layout.addWidget(self.nav_bar)

    def _build_stylesheet(self):
        p = ThemeManager.palette()
        return f"""
            SetupWizard, QWidget#wizardPage, QStackedWidget#wizardStack {{
                background-color: {p.background};
            }}
            QLabel {{
                color: {p.text_primary};
                background: transparent;
            }}
            QLabel[class="wizard-title"] {{
                color: {p.text_primary};
                font-size: 22px;
                font-weight: bold;
                background: transparent;
            }}
            QLabel[class="wizard-heading"] {{
                color: {p.text_primary};
                font-size: 17px;
                font-weight: bold;
                background: transparent;
            }}
            QLabel[class="wizard-label"] {{
                color: {p.text_primary};
                font-size: 13px;
                font-weight: 600;
                background: transparent;
            }}
            QLabel[class="wizard-helper"] {{
                color: {p.text_secondary};
                font-size: 13px;
                background: transparent;
            }}
            QLabel[class="wizard-hint"] {{
                color: {p.text_muted};
                font-size: 11px;
                background: transparent;
            }}
            QFrame#profileCard,
            QFrame#appearanceCard,
            QFrame#stockfishCard,
            QFrame#llmCard,
            QFrame#summaryCard {{
                background-color: {p.surface};
                border: 1px solid {p.border};
                border-radius: 10px;
            }}
        """

    def refresh_accent(self):
        self.setStyleSheet(self._build_stylesheet())
        self.nav_bar.refresh_theme()
        self.nav_bar.update(self.current_page)

        if hasattr(self, "wizard_accent_btn"):
            accent_col = getattr(self, "wizard_accent_color", "#FF9500")
            accent_mode = getattr(self, "wizard_accent_mode", "system")
            from src.gui.dialogs.wizard.wizard_pages import _apply_accent_button_style
            _apply_accent_button_style(self, accent_col, accent_mode)

        if hasattr(self, "wizard_reset_accent_btn"):
            self.wizard_reset_accent_btn.refresh_styles()

        if hasattr(self, "done_btn"):
            self.done_btn.refresh_styles()

        if hasattr(self, "ready_label"):
            self.ready_label.setStyleSheet(
                f"font-size: 13px; color: {Styles.COLOR_ACCENT}; font-weight: bold; background: transparent;"
            )

        if hasattr(self, "llm_test_btn"):
            self.llm_test_btn.refresh_styles()

        if hasattr(self, "sf_browse_btn"):
            self.sf_browse_btn.refresh_styles()
        if hasattr(self, "sf_cancel_btn"):
            self.sf_cancel_btn.refresh_styles()
        if hasattr(self, "sf_download_btn"):
            self.sf_download_btn.refresh_styles()
        if hasattr(self, "get_started_btn"):
            self.get_started_btn.refresh_styles()
        if hasattr(self, "sf_progress"):
            self.sf_progress.setStyleSheet(Styles.get_progress_bar_style())

        if hasattr(self, "sf_icon_label") and (self._download_worker is None or not self._download_worker.isRunning()):
            self._detect_stockfish()

        self._update_done_icon()
        self._update_lichess_tok_link()

        from src.gui.dialogs.wizard.wizard_pages import _update_llm_ui_hints
        if hasattr(self, "llm_provider_combo"):
            _update_llm_ui_hints(self)

        if self.current_page == 6 and hasattr(self, "_on_done_show"):
            self._on_done_show()

    def _update_lichess_tok_link(self):
        if hasattr(self, "lichess_tok_link"):
            self.lichess_tok_link.setText(
                f'<a href="https://lichess.org/account/oauth/token" style="color: {Styles.COLOR_ACCENT}; text-decoration: none;">Create Token ↗</a>'
            )

    def _update_done_icon(self):
        if not hasattr(self, 'done_icon_label'):
            return
        if HAS_QTAWESOME:
            icon = qta.icon("fa5s.check-circle", color=Styles.COLOR_ACCENT)
            pixmap = icon.pixmap(72, 72)
            self.done_icon_label.setPixmap(pixmap)
        else:
            self.done_icon_label.setText("✓")
            self.done_icon_label.setStyleSheet(f"font-size: 64px; color: {Styles.COLOR_ACCENT}; font-weight: bold; background: transparent;")

    def _show_page(self, index):
        self.current_page = index
        self.stack.setCurrentIndex(index)
        self.nav_bar.update(index)

        if index == 0:
            QTimer.singleShot(150, self._run_gatekeeper)
        elif index == 6:
            parts = []
            engine = self.settings.get("engine_path") or self.config_manager.get("engine_path")
            if engine and engine != "stockfish":
                parts.append(f"✓ Chess Engine: {os.path.basename(engine)}")
            else:
                parts.append("⚠ Chess Engine: Not configured")

            llm_info = self.settings.get("llm_profile")
            if llm_info and (llm_info.get("api_key") or not llm_info.get("requires_key", True)):
                prov = llm_info.get("provider", "Groq").title()
                parts.append(f"✓ AI Coach ({prov}): Configured")
            else:
                parts.append("✓ AI Coach: Skipped (configure anytime in Settings)")

            cc = self.settings.get("chesscom_username") or self.config_manager.get("chesscom_username")
            li = self.settings.get("lichess_username") or self.config_manager.get("lichess_username")
            accounts = []
            if cc:
                accounts.append("Chess.com")
            if li:
                accounts.append("Lichess")
            if accounts:
                parts.append(f"✓ Accounts Linked: {', '.join(accounts)}")
            else:
                parts.append("✓ Accounts: Skipped")

            self.summary_label.setText("\n".join(parts))

        page = self.stack.currentWidget()
        on_show = getattr(page, "_on_show", None)
        if on_show:
            on_show()

    def _go_to(self, index):
        self._show_page(index)

    def _on_next(self):
        self._save_current_page()
        if self.current_page == 6:
            self._persist_settings()
            self.accept()
        else:
            self._show_page(self.current_page + 1)

    def _on_back(self):
        # Save current page inputs before navigating back
        if self.current_page > 1:
            self._save_current_page()
            self._show_page(self.current_page - 1)

    def _on_skip(self):
        self._show_page(6)

    def _on_finish(self):
        self._save_current_page()
        self._persist_settings()
        self.accept()

    def _save_current_page(self):
        idx = self.current_page
        if idx == 2:
            self.settings["chesscom_username"] = self.chesscom_input.text().strip()
            self.settings["lichess_username"] = self.lichess_input.text().strip()
            self.settings["lichess_token"] = self.lichess_token_input.text().strip()
        elif idx == 3:
            if hasattr(self, "wizard_theme_combo"):
                self.settings["board_theme"] = self.wizard_theme_combo.currentText()
            if hasattr(self, "wizard_theme_mode_combo"):
                self.settings["theme_mode"] = self.wizard_theme_mode_combo.currentData() or "system"
            self.settings["accent_color"] = getattr(self, "wizard_accent_color", "#FF9500")
            self.settings["accent_mode"] = getattr(self, "wizard_accent_mode", "system")
        elif idx == 5:
            prov_idx = self.llm_provider_combo.currentIndex()
            prov_key = self.llm_provider_combo.itemData(prov_idx) or "groq"
            prov_preset = PROVIDERS.get(prov_key, PROVIDERS["custom"])

            key = self.llm_key_input.text().strip()
            model = self.llm_model_input.text().strip() or prov_preset.get("default_model", "")
            base_url = self.llm_base_url_input.text().strip() or prov_preset.get("base_url", "")

            if key or model or not prov_preset.get("requires_key", True):
                self.settings["llm_profile"] = {
                    "provider": prov_key,
                    "api_key": key,
                    "model": model,
                    "base_url": base_url,
                    "requires_key": prov_preset.get("requires_key", True)
                }

    def _populate_from_config(self):
        self.chesscom_input.setText(self.config_manager.get("chesscom_username", ""))
        self.lichess_input.setText(self.config_manager.get("lichess_username", ""))
        self.lichess_token_input.setText(self.config_manager.get("lichess_token", ""))

        # Pre-populate appearance preferences
        saved_board_theme = self.config_manager.get("board_theme", DEFAULT_BOARD_THEME)
        if hasattr(self, "wizard_theme_combo"):
            self.wizard_theme_combo.setCurrentText(saved_board_theme)

        saved_theme_mode = self.config_manager.get("theme_mode", "system")
        if hasattr(self, "wizard_theme_mode_combo"):
            for i in range(self.wizard_theme_mode_combo.count()):
                if self.wizard_theme_mode_combo.itemData(i) == saved_theme_mode:
                    self.wizard_theme_mode_combo.setCurrentIndex(i)
                    break

        saved_accent = self.config_manager.get("accent_color")
        saved_accent_mode = self.config_manager.get("accent_mode", "system")
        from src.gui.dialogs.wizard.wizard_pages import _apply_accent
        if saved_accent_mode == "custom" and saved_accent:
            _apply_accent(self, saved_accent, mode="custom")
        else:
            _apply_accent(self, "#FF9500", mode="system")

        # Pre-populate active LLM profile if configured
        active_prof = self.config_manager.get_active_profile()
        if not active_prof:
            profiles = self.config_manager.get("llm_profiles", [])
            if profiles:
                active_prof = profiles[0]

        if active_prof:
            prov = active_prof.get("provider", "groq")
            for i in range(self.llm_provider_combo.count()):
                if self.llm_provider_combo.itemData(i) == prov:
                    self.llm_provider_combo.setCurrentIndex(i)
                    break
            if active_prof.get("api_key"):
                self.llm_key_input.setText(active_prof.get("api_key", ""))
            if active_prof.get("model"):
                self.llm_model_input.setText(active_prof.get("model", ""))
            if active_prof.get("base_url"):
                self.llm_base_url_input.setText(active_prof.get("base_url", ""))
            self._last_selected_provider = prov
            self.settings["llm_profile"] = dict(active_prof)

    def _run_gatekeeper(self):
        if getattr(sys, "frozen", False) and sys.platform == "darwin":
            self.gatekeeper_label.setText("Checking macOS Security...")
            self.gatekeeper_detail.setText("Ensuring the app runs smoothly with Gatekeeper.")

            app_bundle = os.path.dirname(sys.executable)
            while not app_bundle.endswith(".app") and app_bundle != "/":
                app_bundle = os.path.dirname(app_bundle)

            if app_bundle.endswith(".app"):
                result = subprocess.run(
                    ["xattr", "-p", "com.apple.quarantine", app_bundle],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    subprocess.run(
                        ["xattr", "-dr", "com.apple.quarantine", app_bundle],
                        stderr=subprocess.DEVNULL, timeout=5,
                    )
                    self.gatekeeper_label.setText("Permissions Ready")
                    self.gatekeeper_detail.setText("macOS Gatekeeper configured successfully.")
                    logger.info("Gatekeeper: removed quarantine from .app bundle")
                else:
                    self.gatekeeper_label.setText("Security Check Passed")
                    self.gatekeeper_detail.setText("Your environment is completely ready.")
            else:
                self.gatekeeper_label.setText("Security Check Passed")
                self.gatekeeper_detail.setText("Running outside an app container.")
        else:
            self.gatekeeper_label.setText("Ready")
            self.gatekeeper_detail.setText("Starting setup...")

        QTimer.singleShot(600, lambda: self._show_page(1))

    def _detect_stockfish(self):
        if self._download_worker is not None and self._download_worker.isRunning():
            return

        path = resolve_engine_path(self.config_manager)
        if path:
            self.sf_status.setText("Stockfish Engine Ready")
            self.sf_status.setStyleSheet(
                f"font-size: 14px; color: {Styles.COLOR_BEST}; font-weight: bold; background: transparent;"
            )
            self.sf_detail.setText(f"Found binary: {path}")
            self.sf_detail.setVisible(True)
            self.sf_download_btn.setVisible(False)
            self.sf_cancel_btn.setVisible(False)
            self.sf_progress.setVisible(False)
            self.sf_progress_desc.setVisible(False)
            self.settings["engine_path"] = path
            if HAS_QTAWESOME:
                self.sf_icon_label.setPixmap(qta.icon("fa5s.check-circle", color=Styles.COLOR_BEST).pixmap(24, 24))
        else:
            self.sf_status.setText("Stockfish Not Detected")
            self.sf_status.setStyleSheet(
                f"font-size: 14px; color: {Styles.COLOR_MISTAKE}; font-weight: bold; background: transparent;"
            )
            self.sf_detail.setText("Download Stockfish automatically or select an existing binary on your drive.")
            self.sf_detail.setVisible(True)
            self.sf_download_btn.setText("Download Stockfish")
            self.sf_download_btn.setVisible(True)
            self.sf_cancel_btn.setVisible(False)
            self.sf_progress.setVisible(False)
            self.sf_progress_desc.setVisible(False)
            if HAS_QTAWESOME:
                self.sf_icon_label.setPixmap(qta.icon("fa5s.exclamation-circle", color=Styles.COLOR_MISTAKE).pixmap(24, 24))

    def _set_custom_stockfish_path(self, path: str):
        if not path or not os.path.exists(path):
            return

        if not probe_engine_binary(path):
            self.sf_status.setText("Invalid Engine Selected")
            self.sf_status.setStyleSheet(f"font-size: 14px; color: {Styles.COLOR_BLUNDER}; font-weight: bold; background: transparent;")
            self.sf_detail.setText("The selected file failed the UCI handshake test. Please choose a valid Stockfish binary.")
            return

        invalidate_engine_cache()
        self.settings["engine_path"] = path
        self.sf_status.setText("Stockfish Ready (Custom Binary)")
        self.sf_status.setStyleSheet(
            f"font-size: 14px; color: {Styles.COLOR_BEST}; font-weight: bold; background: transparent;"
        )
        self.sf_detail.setText(f"Found binary: {path}")
        self.sf_detail.setVisible(True)
        self.sf_download_btn.setVisible(False)
        self.sf_cancel_btn.setVisible(False)
        self.sf_progress.setVisible(False)
        self.sf_progress_desc.setVisible(False)
        if HAS_QTAWESOME:
            self.sf_icon_label.setPixmap(qta.icon("fa5s.check-circle", color=Styles.COLOR_BEST).pixmap(24, 24))

    def _download_stockfish(self):
        self.sf_download_btn.setVisible(False)
        self.sf_cancel_btn.setVisible(True)
        self.sf_progress.setVisible(True)
        self.sf_progress.setValue(0)
        self.sf_progress_desc.setVisible(True)
        self.sf_progress_desc.setText("Initializing Stockfish download...")
        self.sf_status.setText("Downloading Stockfish...")
        self.sf_status.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; background: transparent;")

        dest_dir = get_engine_data_dir()
        self._download_worker = StockfishDownloadWorker(dest_dir, self)
        self._download_worker.progress.connect(self._on_download_progress)
        self._download_worker.stage.connect(self._on_download_stage)
        self._download_worker.finished.connect(self._on_download_finished)
        self._download_worker.error.connect(self._on_download_error)
        self._download_worker.start()

    def _cancel_stockfish_download(self):
        if self._download_worker and self._download_worker.isRunning():
            self._download_worker.cancel()
            self._download_worker.wait(1500)
            self._download_worker = None

        self.sf_status.setText("Download Cancelled")
        self.sf_status.setStyleSheet(f"font-size: 14px; color: {Styles.COLOR_MISTAKE}; font-weight: bold; background: transparent;")
        self.sf_progress.setVisible(False)
        self.sf_progress_desc.setVisible(False)
        self.sf_download_btn.setText("Download Stockfish")
        self.sf_download_btn.setVisible(True)
        self.sf_cancel_btn.setVisible(False)

    def _on_download_progress(self, pct):
        self.sf_progress.setValue(pct)

    def _on_download_stage(self, stage_text):
        self.sf_progress_desc.setText(stage_text)

    def _on_download_finished(self, binary_path):
        self.sf_progress.setValue(100)
        invalidate_engine_cache()
        self.sf_status.setText("Stockfish Ready")
        self.sf_status.setStyleSheet(
            f"font-size: 14px; color: {Styles.COLOR_BEST}; font-weight: bold; background: transparent;"
        )
        self.settings["engine_path"] = binary_path
        self.sf_detail.setText(f"Engine installed at: {binary_path}")
        self.sf_detail.setVisible(True)
        self.sf_download_btn.setVisible(False)
        self.sf_cancel_btn.setVisible(False)
        self.sf_progress.setVisible(False)
        self.sf_progress_desc.setVisible(False)
        if HAS_QTAWESOME:
            self.sf_icon_label.setPixmap(qta.icon("fa5s.check-circle", color=Styles.COLOR_BEST).pixmap(24, 24))
        logger.info("SetupWizard: Stockfish downloaded to %s", binary_path)

    def _on_download_error(self, err_msg):
        logger.error("SetupWizard: Stockfish download failed: %s", err_msg)
        self.sf_status.setText("Download Failed")
        self.sf_status.setStyleSheet(
            f"font-size: 14px; color: {Styles.COLOR_BLUNDER}; font-weight: bold; background: transparent;"
        )
        self.sf_detail.setText(f"Error: {err_msg}")
        self.sf_progress.setVisible(False)
        self.sf_progress_desc.setVisible(False)
        self.sf_download_btn.setText("Retry Download")
        self.sf_download_btn.setVisible(True)
        self.sf_cancel_btn.setVisible(False)

    def _test_llm(self):
        prov_idx = self.llm_provider_combo.currentIndex()
        prov_key = self.llm_provider_combo.itemData(prov_idx) or "groq"
        prov_preset = PROVIDERS.get(prov_key, PROVIDERS["custom"])

        key = self.llm_key_input.text().strip()
        model = self.llm_model_input.text().strip() or prov_preset.get("default_model", "")
        base_url = self.llm_base_url_input.text().strip() or prov_preset.get("base_url", "")

        if prov_preset.get("requires_key", True) and not key:
            self.llm_test_result.setText("Please enter an API key first")
            self.llm_test_result.setStyleSheet(f"font-size: 12px; color: {Styles.COLOR_MISTAKE}; background: transparent;")
            return

        if not base_url:
            self.llm_test_result.setText("Base URL is required")
            self.llm_test_result.setStyleSheet(f"font-size: 12px; color: {Styles.COLOR_MISTAKE}; background: transparent;")
            return

        if not model:
            self.llm_test_result.setText("Model identifier is required")
            self.llm_test_result.setStyleSheet(f"font-size: 12px; color: {Styles.COLOR_MISTAKE}; background: transparent;")
            return

        self.llm_test_btn.setEnabled(False)
        self.llm_test_btn.setText("Testing Connection...")
        self.llm_test_result.setText("Connecting to API endpoint...")
        self.llm_test_result.setStyleSheet(f"font-size: 12px; color: {Styles.COLOR_TEXT_MUTED}; background: transparent;")

        self._llm_worker = LLMTestWorker(key, base_url, model, self)
        self._llm_worker.finished.connect(self._on_llm_test_finished)
        self._llm_worker.start()

    def _on_llm_test_finished(self, success: bool, message: str):
        self.llm_test_btn.setEnabled(True)
        self.llm_test_btn.setText("Test Connection")

        if success:
            self.llm_test_result.setText(f"✓ {message}")
            self.llm_test_result.setStyleSheet(f"font-size: 12px; color: {Styles.COLOR_BEST}; font-weight: bold; background: transparent;")
        else:
            self.llm_test_result.setText(f"✗ Failed: {message}")
            self.llm_test_result.setStyleSheet(f"font-size: 12px; color: {Styles.COLOR_BLUNDER}; background: transparent;")

    def _persist_settings(self):
        cfg = self.config_manager

        if "chesscom_username" in self.settings:
            cfg.set("chesscom_username", self.settings["chesscom_username"])
        if "lichess_username" in self.settings:
            cfg.set("lichess_username", self.settings["lichess_username"])
        if "lichess_token" in self.settings:
            cfg.set("lichess_token", self.settings["lichess_token"])
        if "engine_path" in self.settings:
            cfg.set("engine_path", self.settings["engine_path"])

        if "llm_profile" in self.settings:
            prof = self.settings["llm_profile"]
            profiles = cfg.get("llm_profiles", [])
            # Update existing matching provider or append new profile
            existing = next((p for p in profiles if p.get("provider", "").lower() == prof["provider"].lower()), None)
            if existing:
                existing["api_key"] = prof["api_key"]
                existing["model"] = prof["model"]
                existing["base_url"] = prof["base_url"]
            else:
                profiles.append({
                    "provider": prof["provider"],
                    "api_key": prof["api_key"],
                    "model": prof["model"],
                    "base_url": prof["base_url"],
                })
            cfg.set("llm_profiles", profiles)
            cfg.set("active_llm_provider", prof["provider"])

        if "board_theme" in self.settings:
            cfg.set("board_theme", self.settings["board_theme"])

        if "theme_mode" in self.settings:
            cfg.set("theme_mode", self.settings["theme_mode"])
            from src.gui.theme import ThemeManager
            ThemeManager.set_theme_mode(self.settings["theme_mode"])

        accent_mode = self.settings.get("accent_mode", getattr(self, "wizard_accent_mode", "system"))
        cfg.set("accent_mode", accent_mode)
        if accent_mode == "custom":
            accent_col = self.settings.get("accent_color", getattr(self, "wizard_accent_color", "#FF9500"))
            cfg.set("accent_color", accent_col)
            Styles.set_accent_color(accent_col)
        else:
            from src.gui.theme import ThemeManager
            ThemeManager.set_accent_mode("system")
        cfg.set("setup_completed", True)

    def accepted_data(self) -> dict:
        return dict(self.settings)

import sys
import os
import subprocess
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QStackedWidget, QLabel, QApplication,
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal

from src.utils.logger import logger
from src.utils.path_utils import get_resource_path, get_engine_data_dir
from src.backend.analysis.engine import resolve_engine_path, invalidate_engine_cache
from src.backend.engine.downloader import (
    get_official_releases,
    get_expected_asset_name,
    get_download_url,
    download_and_extract,
)
from src.gui.styles import Styles
from src.gui.dialogs.wizard.wizard_nav_bar import WizardNavBar
from src.gui.dialogs.wizard.wizard_pages import (
    build_gatekeeper_page,
    build_welcome_page,
    build_profile_page,
    build_appearance_page,
    build_stockfish_page,
    build_llm_page,
    build_done_page,
)

class StockfishDownloadWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, dest_dir, parent=None):
        super().__init__(parent)
        self.dest_dir = dest_dir

    def run(self):
        import shutil
        # 1. On macOS, try installing Stockfish via Homebrew first
        if sys.platform == "darwin":
            brew_path = shutil.which("brew")
            if not brew_path:
                # Check common homebrew installation paths
                for p in ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"]:
                    if os.path.isfile(p) and os.access(p, os.X_OK):
                        brew_path = p
                        break

            if brew_path:
                self.progress.emit(20)
                logger.info("StockfishDownloadWorker: attempting Homebrew installation via %s", brew_path)
                try:
                    import subprocess
                    result = subprocess.run(
                        [brew_path, "install", "stockfish"],
                        capture_output=True, text=True, timeout=120
                    )
                    if result.returncode == 0:
                        # Check if stockfish binary exists in standard brew paths
                        for candidate in ["/opt/homebrew/bin/stockfish", "/usr/local/bin/stockfish"]:
                            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                                self.progress.emit(100)
                                self.finished.emit(candidate)
                                return
                        # Fallback check via PATH lookup
                        which_sf = shutil.which("stockfish")
                        if which_sf and os.path.isfile(which_sf) and os.access(which_sf, os.X_OK):
                            self.progress.emit(100)
                            self.finished.emit(which_sf)
                            return
                    logger.warning("StockfishDownloadWorker: Homebrew installation failed: %s", result.stderr)
                except Exception as e:
                    logger.warning("StockfishDownloadWorker: Homebrew installation crashed: %s", e)
                # If Homebrew failed or did not resolve the binary, fall back to Github releases.

        # 2. Github Releases download fallback
        try:
            releases = get_official_releases()
            target = get_expected_asset_name()
            url = get_download_url(releases, target)
            if not url:
                raise RuntimeError(f"No download found for {target}")

            def progress_callback(downloaded, total):
                pct = int(downloaded / total * 100) if total else 0
                self.progress.emit(pct)

            binary_path = download_and_extract(url, self.dest_dir, progress_callback=progress_callback)
            self.finished.emit(binary_path)
        except Exception as e:
            self.error.emit(str(e))


class SetupWizard(QDialog):
    WIZARD_WIDTH = 600
    WIZARD_HEIGHT = 520

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.settings = {}
        self.current_page = 0

        self.setWindowTitle("Chess Analyzer Pro - Setup")
        self.setFixedSize(self.WIZARD_WIDTH, self.WIZARD_HEIGHT)
        self.setStyleSheet(self._build_stylesheet())

        self._build_ui()
        self._populate_from_config()
        self._show_page(0)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.addWidget(build_gatekeeper_page(self))
        self.stack.addWidget(build_welcome_page(self))
        self.stack.addWidget(build_profile_page(self))
        self.stack.addWidget(build_appearance_page(self))
        self.stack.addWidget(build_stockfish_page(self))
        self.stack.addWidget(build_llm_page(self))
        self.stack.addWidget(build_done_page(self))
        layout.addWidget(self.stack, 1)

        self.nav_bar = WizardNavBar()
        self.nav_bar.next_btn.clicked.connect(self._on_next)
        self.nav_bar.back_btn.clicked.connect(self._on_back)
        self.nav_bar.skip_btn.clicked.connect(self._on_skip)
        layout.addWidget(self.nav_bar)

    def _build_stylesheet(self):
        return f"""
            SetupWizard {{
                background-color: {Styles.COLOR_BACKGROUND};
            }}
            QLabel {{
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
            QLineEdit {{
                padding: 10px 14px;
                min-height: 24px;
                border: 2px solid {Styles.COLOR_BORDER};
                border-radius: 6px;
                background-color: {Styles.COLOR_SURFACE_LIGHT};
                color: {Styles.COLOR_TEXT_PRIMARY};
            }}
            QLineEdit:focus {{
                border: 2px solid {Styles.COLOR_ACCENT};
            }}
            QLineEdit::placeholder {{
                color: {Styles.COLOR_TEXT_MUTED};
            }}
        """

    def refresh_accent(self):
        self.setStyleSheet(self._build_stylesheet())
        self.nav_bar.refresh_accent()
        self.nav_bar.update(self.current_page)
        if hasattr(self, 'done_btn'):
            self.done_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Styles.COLOR_ACCENT};
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 12px 40px;
                    font-size: 15px;
                    font-weight: bold;
                }}
                QPushButton:hover {{ background-color: {Styles.COLOR_ACCENT_HOVER}; }}
            """)
        if hasattr(self, 'ready_label'):
            self.ready_label.setStyleSheet(
                f"font-size: 15px; color: {Styles.COLOR_ACCENT}; font-weight: bold; background: transparent;"
            )
        if hasattr(self, 'wizard_theme_combo'):
            self.wizard_theme_combo.setStyleSheet(Styles.get_combobox_style())
        if hasattr(self, 'llm_test_btn'):
            self.llm_test_btn.setStyleSheet(Styles.get_control_button_style())
        if hasattr(self, 'sf_download_btn'):
            self.sf_download_btn.setStyleSheet(Styles.get_button_style())
        if hasattr(self, 'provider_label'):
            self.provider_label.setStyleSheet(
                f"font-size: 14px; font-weight: bold; color: {Styles.COLOR_ACCENT}; background: transparent;"
            )
        if hasattr(self, 'wizard_accent_btn') and self.wizard_accent_color != "#FF9500":
            c = self.wizard_accent_color
            self.wizard_accent_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c};
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {c}CC;
                }}
            """)
        if hasattr(self, 'sf_progress'):
            self.sf_progress.setStyleSheet(Styles.get_progress_bar_style())
        self._update_done_icon()

    def _update_done_icon(self):
        if not hasattr(self, 'done_icon_label'):
            return
        try:
            import qtawesome as qta
            icon = qta.icon("fa5s.check-circle", color=Styles.COLOR_ACCENT)
            pixmap = icon.pixmap(80, 80)
            self.done_icon_label.setPixmap(pixmap)
        except Exception:
            self.done_icon_label.setText("✓")
            self.done_icon_label.setStyleSheet(f"font-size: 72px; color: {Styles.COLOR_ACCENT}; font-weight: bold; background: transparent;")

    def _show_page(self, index):
        self.current_page = index
        self.stack.setCurrentIndex(index)
        self.nav_bar.update(index)

        if index == 0:
            QTimer.singleShot(200, self._run_gatekeeper)
        elif index == 6:
            parts = []
            engine = self.settings.get("engine_path") or self.config_manager.get("engine_path")
            if engine and engine != "stockfish":
                # Get just the filename/basename to keep it clean
                parts.append(f"✓ Chess Engine: {os.path.basename(engine)}")
            else:
                parts.append("⚠ Chess Engine: Not configured")

            llm_key = self.settings.get("groq_api_key")
            if not llm_key:
                active_profile = self.config_manager.get_active_profile()
                if active_profile:
                    llm_key = active_profile.get("api_key")
            if llm_key:
                parts.append("✓ AI Coach (Groq): Connected")
            else:
                parts.append("✓ AI Coach: Skipped (configure later in Settings)")

            cc = self.settings.get("chesscom_username") or self.config_manager.get("chesscom_username")
            li = self.settings.get("lichess_username") or self.config_manager.get("lichess_username")
            accounts = []
            if cc: accounts.append("Chess.com")
            if li: accounts.append("Lichess")
            if accounts:
                parts.append(f"✓ Accounts: Linked ({', '.join(accounts)})")
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
        if self.current_page > 1:
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
                self.settings["accent_color"] = self.wizard_accent_color
        elif idx == 5:
            key = self.llm_key_input.text().strip()
            if key:
                self.settings["groq_api_key"] = key

    def _populate_from_config(self):
        self.chesscom_input.setText(self.config_manager.get("chesscom_username", ""))
        self.lichess_input.setText(self.config_manager.get("lichess_username", ""))
        self.lichess_token_input.setText(self.config_manager.get("lichess_token", ""))

    def _run_gatekeeper(self):
        if getattr(sys, "frozen", False) and sys.platform == "darwin":
            self.gatekeeper_label.setText("Checking Gatekeeper...")
            self.gatekeeper_detail.setText("Ensuring the app runs smoothly on macOS.")

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
                    self.gatekeeper_label.setText("Restrictions removed")
                    self.gatekeeper_detail.setText("Gatekeeper has been configured.")
                    logger.info("Gatekeeper: removed quarantine from .app bundle")
                else:
                    self.gatekeeper_label.setText("No restrictions found")
                    self.gatekeeper_detail.setText("Your system is all set.")
            else:
                self.gatekeeper_label.setText("Skipped")
                self.gatekeeper_detail.setText("Not running from a bundled .app.")
        else:
            self.gatekeeper_label.setText("Skipped")
            self.gatekeeper_detail.setText("Gatekeeper check not needed in this environment.")

        QTimer.singleShot(800, lambda: self._show_page(1))

    def _detect_stockfish(self):
        path = resolve_engine_path(self.config_manager)
        if path:
            self.sf_status.setText("Stockfish ready")
            self.sf_status.setStyleSheet(
                "font-size: 14px; color: #3AAA55; font-weight: bold; background: transparent;"
            )
            self.sf_detail.setText(f"Found at {path}")
            self.sf_detail.setVisible(True)
            self.sf_download_btn.setVisible(False)
            self.settings["engine_path"] = path
        else:
            self.sf_status.setText("Stockfish not found")
            self.sf_status.setStyleSheet(
                "font-size: 14px; color: #E67E22; background: transparent;"
            )
            self.sf_detail.setText("")
            self.sf_detail.setVisible(False)
            self.sf_download_btn.setVisible(True)

    def _download_stockfish(self):
        self.sf_download_btn.setVisible(False)
        self.sf_progress.setVisible(True)
        self.sf_progress.setValue(0)
        self.sf_status.setText("Downloading Stockfish...")
        self.sf_status.setStyleSheet("font-size: 14px; background: transparent;")

        dest_dir = get_engine_data_dir()

        self._download_worker = StockfishDownloadWorker(dest_dir, self)
        self._download_worker.progress.connect(self._on_download_progress)
        self._download_worker.finished.connect(self._on_download_finished)
        self._download_worker.error.connect(self._on_download_error)
        self._download_worker.start()

    def _on_download_progress(self, pct):
        self.sf_progress.setValue(pct)

    def _on_download_finished(self, binary_path):
        self.sf_progress.setValue(100)
        invalidate_engine_cache()
        self.sf_status.setText("Stockfish downloaded")
        self.sf_status.setStyleSheet(
            "font-size: 14px; color: #3AAA55; font-weight: bold; background: transparent;"
        )
        self.settings["engine_path"] = binary_path
        self.sf_detail.setText(f"Found at {binary_path}")
        self.sf_detail.setVisible(True)
        logger.info("SetupWizard: Stockfish downloaded to %s", binary_path)

    def _on_download_error(self, err_msg):
        logger.error("SetupWizard: Stockfish download failed: %s", err_msg)
        self.sf_status.setText(f"Download failed: {err_msg}")
        self.sf_status.setStyleSheet(
            "font-size: 14px; color: #D02030; background: transparent;"
        )
        self.sf_download_btn.setText("Retry")
        self.sf_download_btn.setVisible(True)

    def _test_llm(self):
        key = self.llm_key_input.text().strip()
        if not key:
            self.llm_test_result.setText("Enter an API key first")
            self.llm_test_result.setStyleSheet(
                "font-size: 13px; color: #E67E22; margin-top: 4px; background: transparent;"
            )
            return

        self.llm_test_btn.setEnabled(False)
        self.llm_test_btn.setText("Testing...")
        self.llm_test_result.setText("")
        QApplication.processEvents()

        try:
            from openai import OpenAI
            client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
            client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": "Reply with just the word: ok"}],
                max_tokens=10,
            )
            self.llm_test_result.setText("Connection successful")
            self.llm_test_result.setStyleSheet(
                "font-size: 13px; color: #3AAA55; background: transparent;"
            )
            self.settings["groq_api_key"] = key
        except Exception as e:
            self.llm_test_result.setText(f"Failed: {e}")
            self.llm_test_result.setStyleSheet(
                "font-size: 13px; color: #D02030; background: transparent;"
            )
        finally:
            self.llm_test_btn.setEnabled(True)
            self.llm_test_btn.setText("Test Connection")

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
        if "groq_api_key" in self.settings:
            profiles = cfg.get("llm_profiles", [])
            groq_profile = next(
                (p for p in profiles if p.get("provider", "").lower() == "groq"), None
            )
            if groq_profile:
                groq_profile["api_key"] = self.settings["groq_api_key"]
            else:
                profiles.append({
                    "provider": "groq",
                    "api_key": self.settings["groq_api_key"],
                    "model": "llama-3.3-70b-versatile",
                    "base_url": "https://api.groq.com/openai/v1",
                })
            cfg.set("llm_profiles", profiles)
        if "board_theme" in self.settings:
            cfg.set("board_theme", self.settings["board_theme"])
        if "accent_color" in self.settings and self.settings["accent_color"] != "#FF9500":
            cfg.set("accent_color", self.settings["accent_color"])
            Styles.set_accent_color(self.settings["accent_color"])
        cfg.set("setup_completed", True)

    def accepted_data(self) -> dict:
        return dict(self.settings)

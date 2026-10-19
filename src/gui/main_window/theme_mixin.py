from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QMessageBox

from src.backend.analysis.analyzer import Analyzer
from src.backend.analysis.engine import EngineManager, resolve_engine_path
from src.backend.services.groq_service import GroqService
from src.gui.styles import Styles
from src.gui.theme import ThemeManager
from src.utils.logger import logger


class ThemeMixin:
    """Theme application, palette updates, and settings synchronization."""

    def update_engine_path(self, new_path):
        """Updates the engine path and re-initializes the analyzer."""
        resolved = resolve_engine_path(self.config_manager)
        if resolved:
            new_path = resolved
        logger.info(f"Updating engine path to: {new_path}")
        self.engine_path = new_path
        # Re-initialize analyzer with new engine
        try:
            self.analyzer = Analyzer(
                EngineManager(self.engine_path, config_manager=self.config_manager)
            )
            if hasattr(self, "move_list_panel"):
                self.move_list_panel.update_engine_path(new_path)
            self.show_toast("Engine path updated. Future analyses will use the new engine.", "info")
        except Exception as e:
            logger.error(f"Failed to update engine: {e}")
            QMessageBox.warning(
                self, "Warning", f"Engine path updated, but failed to initialize: {e}"
            )
        finally:
            self._refresh_engine_status()

    def apply_engine_settings(self):
        """Re-apply the current Threads/Hash settings to a running engine.

        No-op when no analysis is in progress — the next analysis will
        pick up the new values automatically.
        """
        logger.info("MainWindow: apply_engine_settings triggered by settings update.")
        engine = getattr(self.analyzer, "engine_manager", None)
        if engine is not None:
            engine.apply_settings_from_config()
        # Also reconfigure the live analysis worker engine dynamically
        if hasattr(self, "move_list_panel") and hasattr(self.move_list_panel, "live_worker"):
            logger.info("MainWindow: Reconfiguring live worker engine.")
            self.move_list_panel.live_worker.configure_engine()
        if hasattr(self, "explorer_view") and hasattr(self.explorer_view, "live_worker"):
            logger.info("MainWindow: Reconfiguring explorer live worker engine.")
            self.explorer_view.live_worker.configure_engine()

    def update_llm_config(self):
        """Re-instantiate the LLM service in every view that holds one.

        Triggered by SettingsView.llm_config_changed after the user saves
        a profile. The new GroqService() reads its settings from the
        ConfigManager itself, so we don't have to pass anything here.
        """
        logger.info("Updating LLM configuration in all views...")
        if hasattr(self, "metrics_view") and hasattr(self.metrics_view, "groq_service"):
            self.metrics_view.groq_service = GroqService()
            logger.info("LLM service in metrics_view refreshed.")
        if hasattr(self, "analysis_panel") and hasattr(self.analysis_panel, "groq_service"):
            self.analysis_panel.groq_service = GroqService()
            logger.info("LLM service in analysis_panel refreshed.")

    def on_usernames_changed(self):
        """Reloads config values in views that use usernames."""
        logger.info("Usernames changed, refreshing dependent views...")
        # Reload config in config_manager (it's a singleton pattern issue)
        self.config_manager.reload_config()
        # Refresh metrics view which uses usernames
        if hasattr(self, "metrics_view"):
            self.metrics_view.mark_dirty()
            if self.stack.currentIndex() == 3:
                self.metrics_view.refresh(force=True)
        # Refresh history view
        if hasattr(self, "history_view"):
            self.history_view.load_history()

    def _apply_palette(self):
        p = ThemeManager.palette()
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(p.background))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(p.text_primary))
        palette.setColor(QPalette.ColorRole.Base, QColor(p.surface))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(p.surface_light))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(p.surface_light))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(p.text_primary))
        palette.setColor(QPalette.ColorRole.Text, QColor(p.text_primary))
        palette.setColor(QPalette.ColorRole.Button, QColor(p.surface))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(p.text_primary))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(p.accent))
        palette.setColor(QPalette.ColorRole.Link, QColor(p.accent))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(p.accent))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        QApplication.setPalette(palette)

    def _on_theme_changed(self, mode: str):
        self.refresh_theme()

    def _on_accent_changed(self, hex_color: str):
        self.config_manager.set("accent_color", hex_color)
        self.refresh_theme()

    def refresh_theme(self):
        """Re-applies the global central QSS theme and updates non-QSS canvas/board widgets."""
        self._apply_palette()
        ThemeManager.apply_app_stylesheet()

        # Header Buttons
        if hasattr(self, "btn_analyze"):
            if getattr(self, "_full_analysis_running", False):
                self.btn_analyze.setStyleSheet(Styles.get_danger_button_style())
            else:
                self.btn_analyze.setStyleSheet(Styles.get_button_style())
        if hasattr(self, "btn_explore"):
            self.btn_explore.setStyleSheet(Styles.get_control_button_style())
        if hasattr(self, "btn_load"):
            self.btn_load.setStyleSheet(Styles.get_control_button_style())

        # Analysis page header containers
        if hasattr(self, "analysis_header_bar"):
            self.analysis_header_bar.setStyleSheet(
                Styles.get_header_bar_ext_style(Styles.COLOR_BACKGROUND)
                + " QFrame QLabel { background: transparent; }"
            )
        if hasattr(self, "title_lbl"):
            self.title_lbl.setStyleSheet(
                Styles.get_label_style(size=24, color=Styles.COLOR_TEXT_PRIMARY, bold=True)
                + " "
                + Styles.get_transparent_label_style()
            )
        if hasattr(self, "left_widget"):
            self.left_widget.setStyleSheet(Styles.get_background_style())
        if hasattr(self, "center_widget"):
            self.center_widget.setStyleSheet(Styles.get_background_style())

        # Update Chess Boards (Graphics / QPainter)
        if hasattr(self, "board_widget"):
            self.board_widget.update_board()
        if hasattr(self, "explorer_view") and hasattr(self.explorer_view, "board_widget"):
            self.explorer_view.board_widget.update_board()

        # Refresh Matplotlib Evaluation Graphs & Custom Gauges
        if hasattr(self, "analysis_panel"):
            self.analysis_panel.refresh_styles()
        if hasattr(self, "move_list_panel"):
            self.move_list_panel.refresh_styles()
        if hasattr(self, "history_view"):
            self.history_view.refresh_styles()
        if hasattr(self, "settings_view"):
            self.settings_view.refresh_styles()
        if hasattr(self, "metrics_view"):
            if hasattr(self.metrics_view, "refresh_styles"):
                self.metrics_view.refresh_styles()
            else:
                self.metrics_view.refresh()
        if hasattr(self, "game_info_label"):
            self.game_info_label.setStyleSheet(
                f"font-size: 16px; font-weight: bold; color: {Styles.COLOR_TEXT_PRIMARY}; padding: 5px; background: transparent;"
            )

        # Update Menu Styles
        menu_style = f"QMenu {{ background-color: {Styles.COLOR_SURFACE}; color: {Styles.COLOR_TEXT_PRIMARY}; border: 1px solid {Styles.COLOR_BORDER}; }} QMenu::item {{ padding: 5px 20px; }} QMenu::item:selected {{ background-color: {Styles.COLOR_ACCENT}; color: white; }}"
        if hasattr(self, "load_menu"):
            self.load_menu.setStyleSheet(menu_style)
        if hasattr(self, "menu_pgn"):
            self.menu_pgn.setStyleSheet(menu_style)
        if hasattr(self, "menu_chesscom"):
            self.menu_chesscom.setStyleSheet(menu_style)
        if hasattr(self, "menu_lichess"):
            self.menu_lichess.setStyleSheet(menu_style)

        # Update Captured Pieces
        for cp in ("captured_white", "captured_black"):
            if hasattr(self, cp):
                w = getattr(self, cp)
                if hasattr(w, "refresh_styles"):
                    w.refresh_styles()

        # Update Game Controls
        if hasattr(self, "controls") and hasattr(self.controls, "refresh_styles"):
            self.controls.refresh_styles()

        # Update explorer view panels
        if hasattr(self, "explorer_view"):
            ev = self.explorer_view
            if hasattr(ev, "refresh_styles"):
                ev.refresh_styles()
            if hasattr(ev, "move_list_widget") and hasattr(ev.move_list_widget, "refresh_styles"):
                ev.move_list_widget.refresh_styles()
        # Update sidebar
        if hasattr(self, "sidebar"):
            self.sidebar.apply_style()

        # Update tour overlay accent
        if hasattr(self, "tour_overlay"):
            self.tour_overlay.refresh_accent()

        # Update status bar
        self.statusBar().setStyleSheet(f"""
            QStatusBar {{
                background-color: {Styles.COLOR_BACKGROUND};
                border-top: 1px solid {Styles.COLOR_BORDER};
            }}
            QStatusBar QLabel {{
                background: transparent;
            }}
        """)
        if hasattr(self, "_status_lbl"):
            self._status_lbl.setStyleSheet(
                f"font-size: 12px; color: {Styles.COLOR_TEXT_SECONDARY}; background: transparent;"
            )
        if hasattr(self, "_engine_pill"):
            state = self._engine_pill.text()
            if "Offline" in state:
                self._engine_pill.setStyleSheet(
                    f"font-size: 12px; font-weight: 600; padding: 0 6px; color: {Styles.COLOR_BLUNDER};"
                )
            elif "Calculating" in state:
                self._engine_pill.setStyleSheet(
                    f"font-size: 12px; font-weight: 600; padding: 0 6px; color: {Styles.COLOR_ENGINE_BUSY};"
                )
            else:
                self._engine_pill.setStyleSheet(
                    f"font-size: 12px; font-weight: 600; padding: 0 6px; color: {Styles.COLOR_ENGINE_READY};"
                )

        # Force full style re-evaluation for all children
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

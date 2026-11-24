from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

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
            if hasattr(self, "explorer_view"):
                self.explorer_view.update_engine_path(new_path)
            self.show_toast("Engine path updated. Future analyses will use the new engine.", "info")
        except Exception as e:
            logger.error(f"Failed to update engine: {e}")
            self.show_toast(
                f"Engine path updated, but failed to initialize: {e}",
                "warning",
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
        # Also reconfigure the shared live-engine sessions dynamically
        if hasattr(self, "move_list_panel") and hasattr(self.move_list_panel, "session"):
            logger.info("MainWindow: Reconfiguring live analysis engine.")
            self.move_list_panel.session.reconfigure()
        if hasattr(self, "explorer_view") and hasattr(self.explorer_view, "session"):
            logger.info("MainWindow: Reconfiguring explorer live engine.")
            self.explorer_view.session.reconfigure()

    def update_llm_config(self):
        """Re-instantiate the LLM service in every view that holds one.

        Triggered by SettingsView.llm_config_changed after the user saves
        a profile. The new GroqService() reads its settings from the
        ConfigManager itself, so we don't have to pass anything here.
        """
        logger.info("Updating LLM configuration in all views...")
        if self.metrics_view is not None and hasattr(self.metrics_view, "groq_service"):
            self.metrics_view.groq_service = GroqService()
            logger.info("LLM service in metrics_view refreshed.")
        if hasattr(self, "analysis_panel") and hasattr(
            self.analysis_panel, "set_llm_service"
        ):
            self.analysis_panel.set_llm_service(GroqService())
            logger.info("LLM service in analysis_panel refreshed.")

    def on_usernames_changed(self):
        """Reloads config values in views that use usernames."""
        logger.info("Usernames changed, refreshing dependent views...")
        # Reload config in config_manager (it's a singleton pattern issue)
        self.config_manager.reload_config()
        # Refresh metrics view which uses usernames
        if self.metrics_view is not None:
            self.metrics_view.mark_dirty()
            if self.stack.currentIndex() == 3:
                self.metrics_view.refresh(force=True)
        # Refresh history view
        if hasattr(self, "history_view"):
            self.history_view.load_history()
        # Recolour the current game result from the new saved player's POV
        if hasattr(self, "board_game_header"):
            self.board_game_header.refresh_styles()

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
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(Styles.COLOR_ON_ACCENT))
        QApplication.setPalette(palette)

    def _on_theme_changed(self, mode: str):
        self._refresh_theme_safely()

    def _on_accent_changed(self, hex_color: str):
        self.config_manager.set("accent_color", hex_color)
        self._refresh_theme_safely()

    def _refresh_theme_safely(self) -> None:
        """Run a theme refresh unless the window (or a child) is being deleted.

        Theme signals are application-wide, so a closing window can still
        receive one after parts of its widget tree are gone.
        """
        from PyQt6 import sip

        if sip.isdeleted(self):
            return
        try:
            self.refresh_theme()
        except RuntimeError:
            pass

    def refresh_theme(self):
        """Re-apply the central QSS theme and repaint non-QSS widgets.

        ``ThemeManager.set_mode`` / ``set_accent`` already apply the global
        stylesheet before emitting their signals, so this method must not
        apply it a second time — one parse of the central sheet is the single
        largest cost of a theme switch.
        """
        self._apply_palette()

        # Button state sync (not a theme concern, but cheap and must not drift)
        if hasattr(self, "btn_analyze"):
            self.btn_analyze.set_danger(self.analysis_controller._full_analysis_running)

        self._refresh_canvas_widgets()
        self._refresh_data_widgets()

        # Force full style re-evaluation for all children (cheap; ~1ms)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _refresh_canvas_widgets(self) -> None:
        """Widgets that paint outside the style engine."""
        # Chess boards (QPainter + SVG)
        if hasattr(self, "board_widget"):
            self.board_widget.refresh_settings()
        if hasattr(self, "explorer_view") and hasattr(self.explorer_view, "board_widget"):
            self.explorer_view.board_widget.refresh_settings()

        # Variation graph (custom QPainter nodes and accent pills)
        if hasattr(self, "variation_graph"):
            self.variation_graph.refresh_styles()

        # Tour overlay accent glow
        if hasattr(self, "tour_overlay"):
            self.tour_overlay.refresh_accent()

        # Sidebar icons depend on check state, not QSS
        if hasattr(self, "sidebar"):
            self.sidebar.apply_style()

    def _refresh_data_widgets(self) -> None:
        """Re-render data-derived colours for the visible page only.

        Hidden pages are marked dirty and flushed when the user navigates to
        them — rebuilding every chart and game card synchronously during the
        theme switch is what made it feel like a multi-second freeze.
        """
        from src.constants import PAGE_ANALYSIS, PAGE_EXPLORER, PAGE_HISTORY, PAGE_METRICS

        current = self.stack.currentIndex() if hasattr(self, "stack") else -1
        dirty = self._dirty_theme_pages()

        # Settings is cheap (mostly global QSS) and usually the visible page.
        if hasattr(self, "settings_view"):
            self.settings_view.refresh_styles()

        if current == PAGE_ANALYSIS:
            self._refresh_analysis_page()
        else:
            dirty.add(PAGE_ANALYSIS)

        if hasattr(self, "explorer_view"):
            if current == PAGE_EXPLORER:
                self.explorer_view.refresh_styles()
            else:
                dirty.add(PAGE_EXPLORER)

        if hasattr(self, "history_view") and current != PAGE_HISTORY:
            # Navigation to History always calls load_history(), which
            # rebuilds the cards with the live palette.
            dirty.add(PAGE_HISTORY)

        if self.metrics_view is not None:
            if current == PAGE_METRICS:
                self.metrics_view.refresh_styles()
            else:
                # Visits refetch when needs_refresh is set.
                self.metrics_view.mark_dirty()

    def _refresh_analysis_page(self) -> None:
        """Data-driven widgets that live on the Analyze page."""
        if hasattr(self, "analysis_panel"):
            self.analysis_panel.refresh_styles()
        if hasattr(self, "move_list_panel"):
            self.move_list_panel.refresh_styles()
        if hasattr(self, "welcome_panel") and hasattr(self.welcome_panel, "refresh_styles"):
            self.welcome_panel.refresh_styles()
        for cp in ("captured_white", "captured_black"):
            if hasattr(self, cp):
                widget = getattr(self, cp)
                if hasattr(widget, "refresh_styles"):
                    widget.refresh_styles()

    def _dirty_theme_pages(self) -> set[int]:
        dirty = getattr(self, "_theme_dirty_pages", None)
        if dirty is None:
            dirty = set()
            self._theme_dirty_pages = dirty
        return dirty

    def _flush_theme_refresh(self, page_index: int) -> None:
        """Refresh a page that was hidden during the last theme switch."""
        from src.constants import PAGE_ANALYSIS, PAGE_EXPLORER

        dirty = self._dirty_theme_pages()
        if page_index not in dirty:
            return
        dirty.discard(page_index)
        if page_index == PAGE_ANALYSIS:
            self._refresh_analysis_page()
        elif page_index == PAGE_EXPLORER and hasattr(self, "explorer_view"):
            self.explorer_view.refresh_styles()

    def _apply_cta_drop_highlight(self, active: bool) -> None:
        """Toggle the hero CTA drop-target outline via a QSS property.

        The global template owns the actual colours, so this only flips the
        property and forces this one widget to re-evaluate its style.
        """
        cta = getattr(self, "empty_state_cta", None)
        if cta is None:
            return
        cta.setProperty("dropHighlight", bool(active))
        style = cta.style()
        style.unpolish(cta)
        style.polish(cta)
        cta.update()

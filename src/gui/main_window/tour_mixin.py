from PyQt6.QtCore import QTimer

from src.gui.components.tour_manager import TourStep


class TourMixin:
    """Page switching, tour orchestration, and tour step definitions."""

    def switch_page(self, index):
        QTimer.singleShot(0, lambda: self._do_switch_page(index))

    def _do_switch_page(self, index):
        self.stack.setCurrentIndex(index)
        if index == 2 and hasattr(self, "history_view"):
            analyzing_id = (
                self.current_game.game_id
                if hasattr(self, "worker")
                and self.worker
                and self.worker.isRunning()
                and self.current_game
                else None
            )
            self.history_view.set_analyzing_game_id(analyzing_id)
            self.history_view.load_history()
        if index == 3 and hasattr(self, "metrics_view") and self.metrics_view.needs_refresh:
            self.metrics_view.refresh()
        # If a tour is active, close it silently (don't mark seen — user didn't finish it).
        if hasattr(self, "tour_overlay") and self.tour_overlay.isVisible():
            self.tour_overlay.close_silently()
        # Auto-start the tour the first time the user visits this page.
        tour_key = self._get_tour_key(index)
        if not self.tour_manager.has_seen_tour(tour_key):
            QTimer.singleShot(400, lambda idx=index: self._auto_start_tour(idx))

    def _get_tour_key(self, page_index: int | None = None) -> str:
        """Resolve the semantic tour key for the specified or current page."""
        if page_index is None:
            page_index = self.stack.currentIndex()

        if page_index == 0:
            return "landing" if self.current_game is None else "analysis"
        if page_index == 1:
            return "explorer"
        if page_index == 2:
            return "history"
        if page_index == 3:
            if (
                hasattr(self, "metrics_view")
                and hasattr(self.metrics_view, "stacked_widget")
                and self.metrics_view.stacked_widget.currentIndex() == 1
            ):
                return "metrics_drill_down"
            return "metrics"
        if page_index == 4:
            return "settings"
        return str(page_index)

    def _on_drill_down_opened(self):
        """Auto-start drill-down tour on first inspection."""
        if hasattr(self, "tour_manager") and not self.tour_manager.has_seen_tour("metrics_drill_down"):
            QTimer.singleShot(400, lambda: self._auto_start_tour(3))

    def _on_drill_down_closed(self):
        """Silently dismiss tour overlay if open when returning to metrics dashboard."""
        if hasattr(self, "tour_overlay") and self.tour_overlay.isVisible():
            self.tour_overlay.close_silently()

    def _auto_start_tour(self, page_index: int):
        """Start tour on first visit only — guards against delayed mis-fires."""
        if self.stack.currentIndex() != page_index:
            return  # user navigated away during the 400ms delay
        tour_key = self._get_tour_key(page_index)
        if self.tour_manager.has_seen_tour(tour_key):
            return  # already seen (e.g. Ctrl+T was pressed and dismissed)

        # Skip tour if the page has no relevant data yet (don't mark seen,
        # so the tour retriggers on next visit once data becomes available).
        if tour_key == "history" and hasattr(self, "history_view") and not self.history_view.games:
            return
        if tour_key == "metrics" and hasattr(self, "metrics_view"):
            mv = self.metrics_view
            if not any(
                hasattr(mv, attr) and getattr(mv, attr) and getattr(mv, attr).isVisible()
                for attr in ("stats_container", "accuracy_card", "openings_card", "quality_card")
            ):
                return
        if tour_key == "metrics_drill_down" and hasattr(self, "metrics_view"):
            ddv = getattr(self.metrics_view, "drill_down_view", None)
            if not ddv or not ddv.items:
                return

        self._launch_tour(page_index)

    def start_tour(self):
        """Ctrl+T: start/replay tour for the currently active page/view."""
        index = self.stack.currentIndex()
        self._launch_tour(index)

    def _launch_tour(self, page_index: int):
        """Build steps and show the tour overlay for the given page/view."""
        tour_key = self._get_tour_key(page_index)
        steps = self._build_tour_steps(page_index, tour_key=tour_key)
        if not steps:
            return
        self._tour_page = page_index  # remember the originating page
        self._tour_key = tour_key
        self.tour_overlay.setGeometry(self.rect())
        self.tour_manager.start(steps)
        self.tour_overlay.show_tour()

    def _on_tour_finished(self):
        """Called when the tour overlay closes."""
        tour_key = getattr(self, "_tour_key", None)
        if not tour_key:
            tour_key = self._get_tour_key(getattr(self, "_tour_page", self.stack.currentIndex()))
        self.tour_manager.mark_seen(tour_key)

    def _build_tour_steps(self, page_index: int, tour_key: str | None = None) -> list:
        """Return a list of TourStep objects tailored to the visible page/view."""
        if tour_key is None:
            tour_key = self._get_tour_key(page_index)

        ev = self.explorer_view
        hv = self.history_view
        sv = self.settings_view
        mv = self.metrics_view
        steps = []

        if tour_key == "landing":
            # Hero focus empty-state landing view
            if hasattr(self, "board_widget"):
                steps.append(
                    TourStep(
                        target=self.board_widget,
                        title="Interactive Chessboard",
                        text="Welcome to Chess Analyzer Pro! Drag & drop any .pgn file directly onto the board, or press Ctrl+V to paste game text from your clipboard.",
                        position="right",
                        page_index=0,
                        tour_key="landing",
                    )
                )
            if hasattr(self, "btn_hero_load"):
                steps.append(
                    TourStep(
                        target=self.btn_hero_load,
                        title="Load Game",
                        text="Click 'Load Game' to open local PGN files, paste raw moves, or import matches directly from Chess.com and Lichess.",
                        position="below",
                        page_index=0,
                        tour_key="landing",
                    )
                )
            if hasattr(self, "sidebar"):
                steps.append(
                    TourStep(
                        target=self.sidebar,
                        title="Navigation",
                        text="Use the sidebar to explore openings, browse your game history archive, inspect performance analytics, and adjust engine settings.",
                        position="right",
                        page_index=0,
                        tour_key="landing",
                    )
                )
        elif tour_key == "analysis":
                # Full 3-column analysis workspace
                if hasattr(self, "btn_load"):
                    steps.append(
                        TourStep(
                            target=self.btn_load,
                            title="Load Game",
                            text="Open new games from local files, clipboard text, or online accounts at any time.",
                            position="below",
                            page_index=0,
                        )
                    )
                if hasattr(self, "btn_analyze"):
                    steps.append(
                        TourStep(
                            target=self.btn_analyze,
                            title="Engine Analysis",
                            text="Click 'Analyze Game' to run Stockfish. If you pause, 'Resume Analysis' continues right where it stopped. You can also re-analyze completed games.",
                            position="below",
                            page_index=0,
                        )
                    )
                if hasattr(self, "board_widget"):
                    steps.append(
                        TourStep(
                            target=self.board_widget,
                            title="Analysis Board",
                            text="Displays moves with a dynamic evaluation bar, best-move arrows, threat indicators, and real-time material balance.",
                            position="right",
                            page_index=0,
                        )
                    )
                if hasattr(self, "move_list_panel"):
                    steps.append(
                        TourStep(
                            target=self.move_list_panel,
                            title="Move List & Badges",
                            text="Colour-coded move list with classification badges (Brilliant, Great, Best, Inaccuracy, Mistake, Blunder) and multi-PV candidate lines.",
                            position="left",
                            page_index=0,
                        )
                    )
                if hasattr(self, "analysis_panel"):
                    steps.append(
                        TourStep(
                            target=self.analysis_panel,
                            title="Analysis Dashboard",
                            text="Interactive evaluation chart (click any move to jump to it), circular accuracy gauges, and AI Coach match reviews.",
                            position="left",
                            page_index=0,
                        )
                    )
                if hasattr(self, "controls"):
                    steps.append(
                        TourStep(
                            target=self.controls,
                            title="Playback Controls",
                            text="Step through moves with arrow keys, jump to start/end, flip board perspective, or auto-play through the game.",
                            position="above",
                            page_index=0,
                        )
                    )
                if hasattr(self, "btn_explore"):
                    steps.append(
                        TourStep(
                            target=self.btn_explore,
                            title="Opening Explorer",
                            text="'Explore from here' opens the Opening Explorer at the current position to research master continuations and book statistics.",
                            position="below",
                            page_index=0,
                        )
                    )

        elif page_index == 1 or tour_key == "explorer":  # ── Explorer ────────────────────────────────
            if hasattr(ev, "header_bar") and ev.header_bar.isVisible():
                steps.append(
                    TourStep(
                        target=ev.header_bar,
                        title="Opening Recognition",
                        text="Displays the current opening ECO code and opening name, updating dynamically with every played move.",
                        position="below",
                        page_index=1,
                    )
                )
            if hasattr(ev, "board_widget") and ev.board_widget.isVisible():
                steps.append(
                    TourStep(
                        target=ev.board_widget,
                        title="Sandbox Board",
                        text="Interactive sandbox board: Play moves freely, test alternate lines, or study continuations with live Stockfish evaluation.",
                        position="right",
                        page_index=1,
                    )
                )
            if hasattr(ev, "chk_classify") and ev.chk_classify.isVisible():
                steps.append(
                    TourStep(
                        target=ev.chk_classify,
                        title="Move Evaluation",
                        text="Toggle 'Classify Moves' to receive real-time Brilliant, Great, and Blunder badges on every move you test.",
                        position="below",
                        page_index=1,
                    )
                )
            if hasattr(ev, "book_toggle") and ev.book_toggle.isVisible():
                steps.append(
                    TourStep(
                        target=ev.book_toggle,
                        title="Opening Book",
                        text="Book Moves queries the Lichess Masters & Public database with interactive Win/Draw/Loss ratio bars and move statistics.",
                        position="left",
                        page_index=1,
                    )
                )
            if hasattr(ev, "move_input") and ev.move_input.isVisible():
                steps.append(
                    TourStep(
                        target=ev.move_input,
                        title="Move Input",
                        text="Type SAN moves directly (e.g. 'e4', 'Nf3', 'O-O') to quickly jump to any variation or opening branch.",
                        position="left",
                        page_index=1,
                    )
                )
            if hasattr(ev, "btn_flip") and ev.btn_flip.isVisible():
                steps.append(
                    TourStep(
                        target=ev.btn_flip,
                        title="Board Tools",
                        text="Use Flip Board, Copy FEN, and Copy PGN to easily export, analyze, or share any board position.",
                        position="below",
                        page_index=1,
                    )
                )

        elif page_index == 2 or tour_key == "history":  # ── History ──────────────────────────────────
            if hasattr(hv, "search_input") and hv.search_input.isVisible():
                steps.append(
                    TourStep(
                        target=hv.search_input,
                        title="Instant Search",
                        text="Search your game history archive by player username, opening ECO code, event title, or date in real time.",
                        position="below",
                        page_index=2,
                    )
                )
            if hasattr(hv, "result_filter") and hv.result_filter.isVisible():
                steps.append(
                    TourStep(
                        target=hv.result_filter,
                        title="Outcome Filter",
                        text="Filter games by result: Wins, Losses, or Draws.",
                        position="below",
                        page_index=2,
                    )
                )
            if hasattr(hv, "type_filter") and hv.type_filter.isVisible():
                steps.append(
                    TourStep(
                        target=hv.type_filter,
                        title="Format & Speed Filter",
                        text="Filter games by time control speed: Rapid, Blitz, Bullet, Classical, or multi-day Daily correspondence.",
                        position="below",
                        page_index=2,
                    )
                )
            if hasattr(hv, "source_filter") and hv.source_filter.isVisible():
                steps.append(
                    TourStep(
                        target=hv.source_filter,
                        title="Platform Source",
                        text="Filter matches by origin platform: Chess.com, Lichess, or local imported files.",
                        position="below",
                        page_index=2,
                    )
                )
            if hasattr(hv, "btn_import") and hv.btn_import.isVisible():
                steps.append(
                    TourStep(
                        target=hv.btn_import,
                        title="Bulk Import",
                        text="'Import' bulk-loads game archives from CSV or PGN files into your local offline database off the UI thread.",
                        position="left",
                        page_index=2,
                    )
                )
            if hasattr(hv, "btn_export") and hv.btn_export.isVisible():
                steps.append(
                    TourStep(
                        target=hv.btn_export,
                        title="Export Games",
                        text="'Export' saves your analyzed games to standard PGN files compatible with ChessBase and Lichess Studies.",
                        position="left",
                        page_index=2,
                    )
                )
            if hasattr(hv, "btn_clear") and hv.btn_clear.isVisible():
                steps.append(
                    TourStep(
                        target=hv.btn_clear,
                        title="Clear History",
                        text="'Clear' safely cleans up or resets your saved history database. Always export a backup first if you want to keep the data.",
                        position="left",
                        page_index=2,
                    )
                )
            if hasattr(hv, "game_list") and hv.game_list.isVisible():
                steps.append(
                    TourStep(
                        target=hv.game_list,
                        title="Game Archive",
                        text="Saved game archive cards: Displays accuracy ratings, termination badges, live 'Analyzing...' progress, and quick action buttons to Analyze or Resume.",
                        position="above",
                        page_index=2,
                    )
                )

        elif tour_key == "metrics" or (page_index == 3 and tour_key != "metrics_drill_down"):  # ── Metrics Dashboard ──────────────────────
            if hasattr(mv, "btn_refresh") and mv.btn_refresh.isVisible():
                steps.append(
                    TourStep(
                        target=mv.btn_refresh,
                        title="Refresh Stats",
                        text="Stats calculate automatically when you open this page. Click Refresh to recalculate with newly analyzed games.",
                        position="left",
                        page_index=3,
                    )
                )
            if hasattr(mv, "filter_bar") and mv.filter_bar.isVisible():
                steps.append(
                    TourStep(
                        target=mv.filter_bar,
                        title="Filter Dashboard",
                        text="Filter your analytics across Colors (White/Black), Formats (Rapid, Blitz, Bullet, Chess960), Sources, and Time Periods.",
                        position="below",
                        page_index=3,
                    )
                )
            if hasattr(mv, "stats_container") and mv.stats_container.isVisible():
                steps.append(
                    TourStep(
                        target=mv.stats_container,
                        title="Performance Overview",
                        text="Key performance summary cards: Total Games, Win Rate, and Average Accuracy. Notice 'Blunders / Game' and 'Clean Games' cards are interactive — click them to drill down into specific positions!",
                        position="below",
                        page_index=3,
                    )
                )
            if hasattr(mv, "accuracy_card") and mv.accuracy_card.isVisible():
                steps.append(
                    TourStep(
                        target=mv.accuracy_card,
                        title="Accuracy Trend",
                        text="Accuracy Trend charts your average move accuracy trajectory over time. Watch the trend line climb as your play improves.",
                        position="above",
                        page_index=3,
                    )
                )
            if hasattr(mv, "phase_card") and mv.phase_card.isVisible():
                steps.append(
                    TourStep(
                        target=mv.phase_card,
                        title="Phase Performance",
                        text="Phase Performance evaluates your tactical precision and accuracy separately across Opening, Middlegame, and Endgame.",
                        position="above",
                        page_index=3,
                    )
                )
            if hasattr(mv, "ending_card") and mv.ending_card.isVisible():
                steps.append(
                    TourStep(
                        target=mv.ending_card,
                        title="Ending Distribution",
                        text="Ending Distribution breaks down how your games finish (Checkmate, Resignation, Timeout, Stalemate, or Draw).",
                        position="above",
                        page_index=3,
                    )
                )
            if hasattr(mv, "quality_card") and mv.quality_card.isVisible():
                steps.append(
                    TourStep(
                        target=mv.quality_card,
                        title="Move Quality Breakdown",
                        text="Move Quality Breakdown: Donut chart showing your proportion of Brilliant, Great, Best, Inaccurate, Mistake, and Blunder moves.",
                        position="above",
                        page_index=3,
                    )
                )
            if hasattr(mv, "hanging_card") and mv.hanging_card.isVisible():
                steps.append(
                    TourStep(
                        target=mv.hanging_card,
                        title="Hanging Pieces Drill-Down",
                        text="Missed Tactics & Hanging Pieces: Click this card to open a full interactive drill-down with board review of all tactical errors.",
                        position="above",
                        page_index=3,
                    )
                )
            if hasattr(mv, "tactics_card") and mv.tactics_card.isVisible():
                steps.append(
                    TourStep(
                        target=mv.tactics_card,
                        title="Tactical Themes Drill-Down",
                        text="Tactical Themes: Identifies pins, forks, skewers, and discovered attacks. Click any theme to drill down into exact board positions.",
                        position="above",
                        page_index=3,
                    )
                )
            if hasattr(mv, "advantage_card") and mv.advantage_card.isVisible():
                steps.append(
                    TourStep(
                        target=mv.advantage_card,
                        title="Advantage Conversion",
                        text="Advantage Conversion: Tracks your conversion rate in winning positions vs squandered leads. Click to inspect squandered positions.",
                        position="above",
                        page_index=3,
                    )
                )
            if hasattr(mv, "openings_card") and mv.openings_card.isVisible():
                steps.append(
                    TourStep(
                        target=mv.openings_card,
                        title="Top Openings",
                        text="Top Openings: Ranks your most-played repertoires and win rates. Click any opening to inspect all games played in that line.",
                        position="above",
                        page_index=3,
                    )
                )
            if hasattr(mv, "brilliancy_card") and mv.brilliancy_card.isVisible():
                steps.append(
                    TourStep(
                        target=mv.brilliancy_card,
                        title="Brilliancy Hall of Fame",
                        text="Brilliancy Hall: Highlights your highest-rated brilliant moves and sacrifices. Click any card to jump directly to that position on the board!",
                        position="above",
                        page_index=3,
                    )
                )
            if hasattr(mv, "ai_coach_card") and mv.ai_coach_card.isVisible():
                steps.append(
                    TourStep(
                        target=mv.ai_coach_card,
                        title="AI Coach Insights",
                        text="AI Coach Insights: Personalized tactical diagnosis, recurring mistake patterns, and tailored training priorities powered by your configured LLM.",
                        position="above",
                        page_index=3,
                    )
                )
            if not steps:
                steps.append(
                    TourStep(
                        target=mv,
                        title="Performance Dashboard",
                        text="Your personal performance dashboard with accuracy trends, interactive drill-downs, tactical cards, and AI Coach insights. Configure your usernames in Settings or analyze games to populate stats.",
                        position="below",
                        page_index=3,
                        tour_key="metrics",
                    )
                )

        elif tour_key == "metrics_drill_down":
            ddv = getattr(mv, "drill_down_view", None)
            if ddv is not None:
                if hasattr(ddv, "btn_back") and ddv.btn_back.isVisible():
                    steps.append(
                        TourStep(
                            target=ddv.btn_back,
                            title="Return to Metrics",
                            text="Click 'Back to Dashboard' whenever you want to return to your main performance analytics overview.",
                            position="below",
                            page_index=3,
                            tour_key="metrics_drill_down",
                        )
                    )
                if hasattr(ddv, "badge_count") and ddv.badge_count.isVisible():
                    steps.append(
                        TourStep(
                            target=ddv.badge_count,
                            title="Occurrence Filter",
                            text="Shows the exact metric or tactical pattern you are inspecting and total occurrences detected across all your analyzed games.",
                            position="below",
                            page_index=3,
                            tour_key="metrics_drill_down",
                        )
                    )
                first_card = None
                if hasattr(ddv, "list_layout") and ddv.list_layout.count() > 0:
                    item = ddv.list_layout.itemAt(0)
                    if item and item.widget() and item.widget().isVisible():
                        first_card = item.widget()
                target_card = first_card or getattr(ddv, "scroll_area", None)
                if target_card and target_card.isVisible():
                    steps.append(
                        TourStep(
                            target=target_card,
                            title="Interactive Position Cards",
                            text="Each card shows the board position, opponent, played move, and engine classification. Click anywhere on a card to jump directly into the full analysis workspace at that exact move!",
                            position="right" if first_card else "below",
                            page_index=3,
                            tour_key="metrics_drill_down",
                        )
                    )
                if hasattr(ddv, "pagination_bar") and ddv.pagination_bar.isVisible():
                    steps.append(
                        TourStep(
                            target=ddv.pagination_bar,
                            title="Pagination Controls",
                            text="Browse through large sets of tactical occurrences 10 at a time with Previous and Next page controls.",
                            position="above",
                            page_index=3,
                            tour_key="metrics_drill_down",
                        )
                    )

        elif page_index == 4 or tour_key == "settings":  # ── Settings ─────────────────────────────────
            mode_btn = getattr(sv, "mode_toggle_btn", None)
            eng = getattr(sv, "engine_settings", None)
            app = getattr(sv, "appearance_settings", None)
            api = getattr(sv, "api_settings", None)
            ply = getattr(sv, "player_settings", None)
            bok = getattr(sv, "book_settings", None)
            dat = getattr(sv, "data_settings", None)
            lnk = getattr(sv, "links_settings", None)
            save_btn = getattr(sv, "save_settings_btn", None)

            if mode_btn and mode_btn.isVisible():
                steps.append(
                    TourStep(
                        target=mode_btn,
                        title="Settings Mode",
                        text="Settings Mode: Toggle between 'Basic' for essential configuration and 'Advanced' for fine-grained engine memory, threads, multi-PV, and cache tuning.",
                        position="below",
                        page_index=4,
                    )
                )
            if eng and eng.isVisible():
                steps.append(
                    TourStep(
                        target=eng,
                        title="Stockfish Engine",
                        text="Chess Engine: Configure your Stockfish executable path (or click Download to fetch it automatically), analysis depth, and thread allocations.",
                        position="below",
                        page_index=4,
                    )
                )
            if app and app.isVisible():
                steps.append(
                    TourStep(
                        target=app,
                        title="Appearance & Themes",
                        text="Appearance: Switch between Dark & Light themes, choose custom board themes, import custom piece SVGs, pick live accent colors, and toggle sound effects.",
                        position="below",
                        page_index=4,
                    )
                )
            if api and api.isVisible():
                steps.append(
                    TourStep(
                        target=api,
                        title="AI Coach LLM Integration",
                        text="API Configuration: Manage LLM profiles (Groq, OpenAI, LM Studio, MiniMax) for AI Coach game reviews and configure Lichess personal access tokens.",
                        position="above",
                        page_index=4,
                    )
                )
            if ply and ply.isVisible():
                steps.append(
                    TourStep(
                        target=ply,
                        title="Player Accounts",
                        text="Player Accounts: Set your Chess.com and Lichess handles for automated performance stats and one-click game imports.",
                        position="above",
                        page_index=4,
                    )
                )
            if bok and bok.isVisible():
                steps.append(
                    TourStep(
                        target=bok,
                        title="Opening Book",
                        text="Opening Book: Configure an optional Polyglot (.bin) opening book for instant master-level opening repertoire moves.",
                        position="above",
                        page_index=4,
                    )
                )
            if dat and dat.isVisible():
                steps.append(
                    TourStep(
                        target=dat,
                        title="Data & Storage",
                        text="Data & Storage: View database file sizes, clear cached engine evaluations, or safely manage local application data.",
                        position="above",
                        page_index=4,
                    )
                )
            if lnk and lnk.isVisible():
                steps.append(
                    TourStep(
                        target=lnk,
                        title="Updates & Support",
                        text="Links & Feedback: Check for updates, rate the app, submit feature ideas, or report bugs with diagnostic logs.",
                        position="above",
                        page_index=4,
                    )
                )
            if save_btn and save_btn.isVisible():
                steps.append(
                    TourStep(
                        target=save_btn,
                        title="Save Settings",
                        text="Click 'Save Settings' to apply and persist all your configuration changes.",
                        position="left",
                        page_index=4,
                    )
                )
            if not steps:  # fallback
                steps.append(
                    TourStep(
                        target=sv,
                        title="Settings",
                        text="Configure Stockfish engine path, analysis depth, AI provider, board theme, and piece style here.",
                        position="below",
                        page_index=4,
                    )
                )

        return steps

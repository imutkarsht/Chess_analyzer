# Changelog

## v2.5.0 - AI Coach, Variations, Settings & Component Platform

### Features

- **AI Coach & Grounded Move Explanations**: Per-move explanations are built from a deterministic fact sheet (classification, evaluation swing, tactics, candidate lines), validated against those facts, and rendered in a dedicated Coach tab. The same pipeline powers persistent full-game summaries and falls back to offline deterministic text when no provider is configured or the network is unavailable. Explanation temperature, max tokens and reasoning effort are configurable, and explanations are cached with a configurable TTL.
- **Playable Variations & Branch Explorer**: Branch from the best move, a refutation, or any engine line without leaving the game. Variation trees are FEN-keyed and persistent for the session, rendered as a scrollable graph with lanes and nodes, with saved-tree badges in the move list and sibling cycling. The tree evicts branches at a configurable cap.
- **Settings Page Overhaul**: Schema-driven settings registry with a searchable category rail, Basic/Advanced split, single-source defaults and validation, and one card per settings area. Data Management now includes validated backup/restore, a local usage report, an open-data-folder action, cache retention policies, maintenance, and a separated danger zone.
- **History Page Optimisation**: Paged loading (10 detailed / 15 compact per page) with idle prefetch of the next page, debounced search/filters, shared pagination, and a persisted default layout. Game cards and compact rows render from one shared item widget.
- **Keyboard Shortcuts & Presets**: Central shortcut manager with Standard and Vim presets, move stepping, critical-move jumps, auto-replay, page switching, and a Settings cheat sheet/help dialog.
- **Board Display Toggles**: Coordinates and move-quality badges are real appearance settings, applied live to both Analysis and Explorer boards.
- **Configurable Cache Retention**: Explorer and explanation cache TTLs plus analysis-cache capacity are real settings, with amortised pruning applied as values are saved.
- **Integrations & Player Profiles**: Rebuilt Chess.com/Lichess/import cards with cached public profile previews, avatars, country normalisation, stale offline fallback, and token-aware import caps shared by the UI and fetch workers.
- **Lichess Explorer Authentication**: Explorer requests send the configured Lichess token, throttle to the account budget, gate live lookups on token presence, keep cached/book data available offline, reuse cached positions across app launches, and show pulsing skeleton rows while the first online lookup is in flight instead of briefly painting the local book.
- **LLM Profile Management**: Explicit Set Active action, per-field persistence, provider-default resets, and Custom base URLs kept visible in Basic mode.
- **Dashboard Layout**: Reorderable chart cards with pinned summary cards, stable-key persisted order, and a reusable drag/drop sortable list with auto-scroll and insertion guides.
- **Shared Date Picker**: Outlined editable field with a floating label, accent selection ring, painted border notch, month/year navigation, locale-aware weekdays, keyboard grid navigation, and scoped “no future dates” caps.
- **Central Toast System**: Five variants, per-window stacking, loading-to-result morphing, action buttons, progress, hover pause, dedupe, painted outline icons, and configurable placement.
- **Modernized Load Game**: Single dialog shell with a source toolbar, stacked field-style inputs, fetch action, query summary, skeleton loading, structured empty/error states with retry, and a PGN File/Text switch with a dropzone and paste action.

### Improvements

- **UI Refactor & Component Centralisation**: The GUI component library is grouped into `controls/`, `display/`, `feedback/`, `layout/`, and `lists/` behind one public facade. `MainWindow` is split into focused mixins, and every shared control now comes from one implementation: `Button`, `Input`/`TextArea`, `Select`, `Tabs`, `DatePicker`, `Toast`, `PaginationBar`, `EmptyState`, `StatusBadge`, `SegmentedControl`, `MiniBar`, and `SegmentedBar`. Styles are generated from the live palette in `styles.py` instead of per-widget QSS.
- **Landing Page UX**: Single-primary hierarchy (Load Game is the only filled action; GitHub is outlined, review is hollow, utilities are one row of text links), top-aligned CTA, neutral puzzle prompt with a turn badge, ghost Reveal, shortcut hints, and drag-over feedback.
- **Theme-Aware Controls & POV Results**: Theme switches re-render control icons, restyle the landing puzzle chrome (prompt, turn badge, revealed blurb), and keep result colours on the saved player's perspective.
- **Status Bar Idle State**: Idle shows a single `● Engine ready` pill; the separator and status label appear only for real messages such as progress, warnings, or errors.
- **Board & Pieces Overhaul**: Redesigned theme/piece settings with live previews; new installs default to the warmer Brown board theme.
- **Move List Polish**: Rounded card, side-dot headers, classification badges for all classified moves, widget-painted selection/hover, and responsive think-time labels.
- **Board Chrome**: Matchup header hugs the board width, captured-piece/clock rows stay attached to the board, and navigation uses a compact icon footer.
- **Engine Lines Redesign**: Pure `EngineLine` model, shared live session, dedicated widget, fixed-height rows, elided PVs, and throttled 10 Hz updates.
- **Board Stepping Performance**: Jump directly from cached `fen_before` instead of replaying from move 0.
- **Sidebar Start State**: Configurable Expanded/Collapsed default; collapsed mode no longer auto-expands on tab changes, icon-only buttons carry tooltips, and the active page gets a left accent bar.
- **Adaptive Workspace Layout**: First-launch size follows the available screen; workspace panes use actual width with 25/45/30 proportions.
- **Settings UX**: Logical category ordering, clearer Basic/Advanced split, capped control widths, tighter rows, structured Data Management actions, and a proper About page.
- **Secure Credentials**: LLM API keys and the Lichess token live in the OS credential store, with automatic migration from legacy `secrets.json`.
- **Settings Navigation**: Fixed category rail while only the options panel scrolls; search scrolls to the matching card.
- **Metric Dashboard Consistency**: Shared empty states, status badges, segmented controls, pagination, legends, and bars; one card lifecycle; lazily rendered Time Management subpages.
- **Toast-Driven Long-Running Work**: Backup/restore, cache maintenance, CSV import, online fetches, token checks, LLM tests, update checks, and full analysis now show a loading toast that resolves into success or error.
- **Load Game State & Recovery**: Inline skeletons, result summaries, change-filter/retry controls, and preserved PGN text/file state when switching tabs.
- **Update Dialog UX**: Rich Markdown release notes, clickable links, scrollable view, and streaming download progress.
- **Shared Loading Skeletons**: Coach and Metrics AI wait states use the same pulsing skeleton.
- **Shared Pagination Bar**: Page-size, index, and prev/next behaviour live in one component used by history, metrics cards, and drill-down.

### Bug Fixes

- **In-App Updater SSL Error**: Fixed `[SSL: CERTIFICATE_VERIFY_FAILED]` on macOS by switching the download worker to `requests` with bundled `certifi` CAs.
- **Accent Color Persistence**: Fixed custom accents reverting to the system default on restart.
- **Landing Tour Loop**: Fixed the empty landing tour repeating on every launch.
- **Evaluation Lines**: Continuations start from the selected position; checkmate shows only the mating line; live analysis is bounded by time/depth; Explorer search starts only when visible.
- **Engine Lines Lifecycle**: Fixed stale line resurrection, sequence/race mismatches, duplicate Stockfish spawns, and hang/timeout cases.
- **Board Stability**: Explorer no longer unflips on reload; captured pieces stay on their sides; orientation resets when loading a game.
- **Evaluation Graph Callback Leak**: Hover/click listeners attach once instead of on every render.
- **Lichess Result Mapping**: Resignation and timeout are preserved instead of becoming agreed draws.
- **PGN Think Time**: Time-control increments are included; zero-think moves are no longer discarded.
- **F Shortcut Guard**: `F` no longer flips the board while typing in a text field.
- **Missing Config Defaults**: Persisted defaults now cover theme mode, accent mode, shortcut preset, settings mode, tour state and update-check state.
- **Lichess Token Placement**: Moved Lichess credentials from AI Coach to Integrations.
- **Move List Crash After Data Restore**: Clearing a game now resets embedded cell widgets and prunes dead wrappers before variation badges refresh.
- **Lichess NDJSON Nulls**: Null opening objects and player entries no longer raise during import.
- **Clear Analysis Cache Scope**: Clearing the analysis cache no longer deletes AI Coach explanations.
- **Reset All Data Completeness**: Reset empties every cache table and raises on failure.
- **LLM Profile Persistence**: Profile edits save when a field is committed.
- **Tab Style Bleed**: Removed the global `QTabBar` QSS that leaked into unrelated tabs.
- **Toast Overlap and Dialog Clipping**: Toasts stack per window and stay anchored to the dialog that raised them.
- **Import Progress Expiry**: CSV import uses a persistent loading toast instead of a short info toast.
- **Update Check UI Freeze**: Manual update checks run in a background worker.
- **Toast Theme Refresh**: Toasts restyle on theme and accent changes.
- **Load Game Fetch Worker Lifetime**: Workers are parentless, cancel-aware, and deleted when their thread finishes.
- **Load Game Tab State**: Switching tabs no longer wipes pasted PGN text or the selected game.
- **Today's Game Cache**: Today's date results refresh after five minutes; historical dates stay cacheable.
- **Chess.com Date Boundaries**: Both platforms use the same local calendar day.
- **Unbounded API Requests**: All API calls now use a 30-second timeout.
- **Illegal-Move Error Style**: The Explorer SAN box uses a palette-driven invalid state instead of a hardcoded dark red.

### Chores

- Grouped `src/gui/components` into responsibility subpackages behind the existing public facade.
- Unified the Analysis and Explorer boards into one configurable `Board`.
- Removed the duplicate `ExplorerBoardWidget` and promotion dialog.
- Replaced deprecated `locale.getdefaultlocale()` with `locale.getlocale()`.
- Added `keyring` for OS credential storage, including the PyInstaller hidden import.
- Added a typed, validated settings schema with generated defaults and a persisted schema version.
- Cut the test suite to under 20 seconds by reusing a bare window, stubbing global QSS compilation, and removing timing-sensitive smoke tests; added an 85% branch-coverage floor with GUI modules excluded.
- Expanded backend coverage for caches, analyzer lifecycle/cancellation, engine start/stop and Chess960, updater dispatch, API handling, feedback failures, metrics filters, config migrations, and secret storage.
- Isolated tests from provider environment variables, the real config/history database, the OS keychain, and the network.
- Added a shared `BackgroundTaskCard`/`BackgroundTaskWorker` runner so storage, network, and update tasks cannot block the UI thread or overlap.
- Deleted legacy button/input/combobox style getters and factories; added test guards against raw widget styling and construction.
- Collapsed duplicated pagination logic into the shared `PaginationBar`.
- Removed duplicated metric chart helpers and rebuilt the metrics filter toolbar from a spec loop.
- Removed `Toast.show_message` and per-card toast helpers; all notifications go through one manager.
- Removed the unused `ChessComPanel`, `LichessPanel`, and `SourceBtn` along with their duplicate fetch paths.
- Added shared `FormField` and date/game-row formatting helpers.
- Replaced the old `ModernDatePicker` with the shared `DatePicker`.
- Removed the unused `config.example.json`.
- Rewrote `README.md` as a standard open-source landing page: install and quick start before the feature list, eight capability bullets instead of thirty feature entries, and links to `docs/`, `CHANGELOG.md`, and `CREDITS.md` instead of duplicating them.

---

## v2.4.0 - Performance Analytics, Interactive Landing Hub & Engine Polish

### Features

- **Performance Analytics Dashboard Overhaul**: Completely redesigned the Metrics dashboard to collect and present in-depth statistics including phase accuracies, advantage conversion, and tactical motifs.
- **Interactive Stats Drill-Down Explorer**: Users can click any metric category (Brilliancies, Blunders, Misses, Tactics, Phases, Openings) to open an interactive board modal jumping directly to the exact position.
- **Database Scalability for 1,000+ Games**: Enabled SQLite WAL mode, composite B-Tree indexes, automated compaction (`VACUUM`), and uncapped batch import/export supporting extensive game libraries.
- **Enhanced Brilliancy & Move Classification**: Improved algorithm accuracy with a piece sacrifice detection engine for genuine brilliancies and calibrated blunder/miss thresholds.
- **Pause & Resume Game Analysis**: Users can pause running analyses and resume seamlessly from the first unanalyzed move without losing progress.
- **Automatic In-Progress Game Staging**: Imported games are immediately staged in the database with status tracking (`completed`, `paused`, `not_started`) as soon as they are loaded.
- **Interactive 60-40 Landing Workspace**: On launch with no game loaded, displays an engaging 60-40 split hero hub with an interactive playable board on the left and a dedicated Welcome & Community Hub (`WelcomePanel`) on the right.
- **Famous Historic Games Discovery Engine**: Built-in curated collection of 25 iconic games from chess history, loading a random legendary position on launch with interactive move celebration and historical backstories.

### Improvements

- **Modernized Interactive Tour Overlay**: Restructured the guided tour overlay to dynamically highlight and navigate the new landing layout and sub-panel components.
- **MainWindow Modular Architecture**: Decomposed the monolithic 2,000-line `MainWindow` into focused mixins (`NavigationMixin`, `AnalysisMixin`, `GameLoadingMixin`, `StatusBarMixin`, `ThemeMixin`, `TourMixin`, `UpdateMixin`).
- **Storage Sub-Repositories Decomposition**: Split `GameHistoryManager` into focused single-responsibility repositories for games, API cache, explorer cache, and database connection.
- **Hardened Logging Pipeline**: Centralized logging system with debug and info log levels, rotating file handlers, and automatic redaction of sensitive API tokens.
- **Code Standards & Open Source Guidelines**: Added repository Code of Conduct, Security Policy, Ruff linter configuration with CI workflow, and standardized agent architecture guidelines.
- **Expanded Test Coverage**: Pruned redundant assertions, consolidated GUI fixtures, and expanded unit test coverage across backend and UI modules.

### Bug Fixes

- **Strict 10.0% Accuracy Floor**: Applied volatility-weighted harmonic accuracy scoring with a strict floor per move, preventing single blunders from collapsing overall game accuracy.

- **Progressive Analysis Clock Synchronization**: Fixed bug where dynamic clock times and captured pieces were not updated during live move-by-move streaming.
- **Board Theme Resolver Crash**: Resolved `KeyError: 'default'` by properly mapping configured board themes through `Styles.get_board_colors()`.
- **Database Resource Leaks**: Added explicit context management and teardown hooks to SQLite wrappers to prevent leaked connections on shutdown.
- **Tactical Detection False Positives**: Fixed inverted bitboard ray stepping and added Static Exchange Evaluation (SEE minimax) to eliminate false hanging piece alerts.
- **CSV Import Large Payload Crash**: Raised CSV field size limit to 2GB to prevent crashes when importing large analysis move payloads.


---

## v2.3.0 - Theme Engine, Progressive Analysis, Lichess Explorer & Feedback System

### Features

- **Complete Light Mode & Dynamic Theme System**: Full Light Mode support with tailored high-contrast boards and palettes, backed by a unified QSS template engine (`theme_template.qss`) and `ThemeManager`.
- **Live Move-by-Move Analysis**: Positions, evaluations, best moves, and classification badges now stream onto the board, move list, and eval bar in real time as each move is evaluated.
- **Lichess Opening Explorer Integration**: Real-time position lookups against Lichess Masters & public databases, featuring color-coded Win/Draw/Loss ratio bars (`RatioBar`) and local 2-day SQLite caching.
- **Enhanced Online Game Import (Chess.com & Lichess)**: Fetch game archives by specific dates, load matches directly via URL/Game ID, with automatic local SQLite caching for fast repeat loads.
- **History View Redesign**: Modern desktop game cards with time control badges (Bullet, Blitz, Rapid), view mode toggle (Detailed Cards vs. Compact Table), custom date range picker, and no-scroll pagination.
- **Automatic Game Termination Detector (`termination_detector.py`)**: Automatic detection and custom SVG badges for Checkmate, Resignation, Timeout, Stalemate, Abandonment, and Insufficient Material.
- **In-App Reviews & Feedback System**: Automatic review prompt after 3 analyzed games, paired with a unified 3-tab modal for Bug Reports (with diagnostic log attachments), Feature Suggestions, and Reviews.
- **Custom Toast & Dialog System**: Replaced native OS popups (`QMessageBox`) with smooth floating toast alerts and styled confirmation dialogs (`confirm_dialog`).

### Improvements

- **Analysis UI & Report Card Overhaul**: Redesigned hero header with POV-aware result banners, revamped report card layout, circular accuracy gauges, and high-contrast Electric Cyan evaluation graph cursor pin.
- **Live Accent Repainting**: Changing accent colors immediately updates sidebars, buttons, badges, and highlights in real time without requiring an app restart.
- **Card-Based Settings View**: Overhauled settings tabs with clean surface cards, segmented pill selectors, hash dropdowns (`ModernHashComboBox`), password toggles, and a 2x2 links grid.
- **Codebase & Styles Centralization**: Consolidated scattered inline stylesheets into `src/gui/styles.py` and modularized the explorer view into dedicated sub-modules.

### Bug Fixes

- **Stockfish Downloader Resilience**: Fixed engine download failures caused by upstream Stockfish GitHub release asset renames across Apple Silicon, Intel macOS, Windows, and Linux.
- **Theme Color Leaks**: Removed hardcoded background and border colors in Move Cells, Settings tabs, and Report Cards when toggling between themes.
- **POV Result Calculation**: Fixed result banner calculations to accurately display victory/defeat relative to the user's playing side.
- **Rendering & UI Artifacts**: Fixed legal move indicator dot alpha transparency (RGBA), removed nested dropdown borders, and prevented text clipping on pagination buttons.
- **Re-Analysis Cache Bypass**: Properly resets raw move history when re-analyzing games with cache disabled.

---

## v2.2.0 - Custom Themes, Setup Wizard & UX Polish

### New Features

- **Custom Piece Theme Import**: Import custom folders of 12 SVG piece images via Appearance Settings. SVG files are automatically scaled, normalized, and processed (handling complex gradients and grouping structures) to display beautifully across all views.
- **First-Run Setup Wizard**: A multi-page configuration guide on first startup to easily configure engine paths, LLM providers, online chess accounts, and interface appearance.
- **Auto-Engine Resolution & Downloader**: Automatically resolves Stockfish binary path across config, system PATH, common installation paths, and local downloads. Includes an integrated downloader to fetch the latest platform-appropriate Stockfish binary from GitHub.
- **Dynamic Chess Clocks**: Monospaced clocks next to captured pieces that update dynamically in real time based on PGN time data, with a visual red alert under 20 seconds.
- **Overhauled Interactive Tours**: Non-intrusive guided tours featuring target-pulsing accent glows and floating tooltips, keeping the app interactive during tours. Tours only trigger when page contents are actually loaded.

### Improvements

- **Basic/Advanced Settings Toggle**: Added a simplified settings view by default, with an advanced toggle option for fine-tuning engine parameters.
- **Context-Aware Error Dialogs**: Replaced generic message boxes with custom error dialogs (`EngineNotFoundDialog`, `LlmNotConfiguredDialog`) featuring direct action links to settings.
- **Performance & Disk Caching**: Added engine resolution disk caching to prevent CPU/disk overhead during startup and transitions.
- **UI & Font Polish**: Native styling improvements for macOS (e.g. SF Pro font stack integration, Gatekeeper self-fix for app bundles) and dark-themed dialog updates.
- **Config Legacy Cleanup**: Automated database/config cleanup of stale flat keys (`groq_api_key`, `groq_model`) on load.

### Bug Fixes

- **Checkmate Evaluation Reversal**: Fixed final position checkmate detection scoring `Mate(0)` instead of `Mate(-1)` to correctly identify the winning side.
- **Explorer Page Spacing**: Resolved a double-layout evaluation bar spacing bug on the Explorer page (fixing the 24px right-shift) and fixed coordinate grid overlays.
- **PGN Parsing Guards**: Rejects PGN files with no playable moves to filter out corrupt files and added "Try Again" buttons to parse failure dialogs.
- **Label Wrapping & Backgrounds**: Resolved label text clipping with word wrap on opening name panels, and fixed gray label background boxes in global styling.

---

## v2.1.0 - Analysis Explorer, Polyglot Books & Auto-Update

### New Features

- **Analysis Explorer**: Interactive explorer with independent board, move list, opening book integration, live engine analysis, and move classification.
- **Polyglot Opening Books**: Support for Polyglot binary opening books (`.bin`) configurable in Settings.
- **Auto-Update Framework**: Cross-platform update mechanism with native installers for Windows (Inno Setup), macOS (DMG), and Linux (AppImage).

### Improvements

- **Code Restructuring**: Backend split into `analysis/`, `api/`, `services/`, `storage/`, `updater/` directories. GUI split into `board/`, `analysis/`, `components/`, `dialogs/`, `views/`, `utils/`.
- **Settings Reorganization**: Settings split into dedicated views (API, Appearance, Engine, Player, Data, Book, Links).
- **Metrics Dashboard Refactored**: Modular card-based layout with separate components for accuracy, color performance, move quality, and opening stats.
- **Classification Algorithm Tuning**: Adjusted Blunder/Mistake/Inaccuracy thresholds for better Chess.com alignment.
- **Unified Load Dialog Refactored**: Load game dialog split into modular panel components (PGN file, PGN text, Chess.com, Lichess).
- **Local Opening Books**: Added local book moves as alternative to Lichess API dependency.

### Bug Fixes

- **Chess960 Persistence**: Fixed Chess960 flag not persisting across game save/load cycles.
- **AI Summary Export**: Fixed PGN export not setting starting FEN header.
- **PGN/History Transition Crashes**: Fixed crashes when switching between PGN loading and history views.
- **Live Lines Freeze**: Fixed engine analysis freeze when switching between Polyglot and internal books.
- **Live Engine Slowdown**: Fixed unbounded engine search depth — now uses configured time per move.
- **Analysis Worker Cleanup**: Live engine worker properly stopped on application exit.
- **Config Reloading**: Fixed configuration reloading and API profile validation.
- **Unified UI Styling**: Fixed header styling and accent color inconsistencies across pages.

---

## v2.0.1 - Unified Load Dialog & UI Polish

### New Features & UI Polish

- **Unified Load Game Dialog**: Consolidates all game loading sources (PGN file, PGN text, Chess.com, Lichess) into a single modal with async loading.
- **History Pagination & Per-Game Delete**: Game history loads page by page with individual game deletion.
- **Multi-LLM Profile Support**: Profile-based LLM configurations (Groq, LM Studio, MiniMax, Custom) with profile switching in Settings.
- **Stockfish Path Validator**: "Test Engine" button in Settings with immediate visual feedback.
- **Evaluation Graph Navigation**: Click any point on the graph to jump to that move.
- **Dynamic Accent Color**: UI updates in real time without restart.
- **Real-Time Engine Status**: Status bar with engine states (Ready, Calculating, Offline).
- **Sound Effects Toggle**: Switch sounds on/off in Settings.
- **Configurable Game Fetch Limit**: Control online fetch count (1-30).

### Improvements & Fixes

- **Local Data Paths**: Migrated config, database, and logs to OS-standard user data folders.
- **Live Engine CPU Optimization**: Conservative multi-PV defaults and configurable time budget prevent overheating.
- **Lichess Token Auth**: Fixed `401 Unauthorized` errors on Opening Explorer requests.
- **Worker Thread Leak**: Analysis worker properly closed on exit.
- **Keyboard Navigation**: Enhanced arrow key, Home/End, and graph navigation.
- **Move Count Display**: Fixed truncation past 9 in move list.

---

## v1.7 - Groq API Integration & Lichess Auth Fix

### New Features

- **Groq API Integration**: Switched from deprecated `google.generativeai` (Gemini) SDK to the official `groq` SDK.
- **Configurable AI Models**: Users can change the Groq model ID in Settings.

### Bug Fixes

- **Lichess Opening Explorer Auth**: Authenticated API requests using Lichess tokens to fix `401` errors.
- **Evaluation Graph Height**: Locked widget to intrinsic height, preventing jumping when paging games.
- **Per-Side Captured Pieces**: Split into two single-side rows with locked heights.
- **Square Board Enforcement**: Strictly square board during resize with aligned eval bar.

---

## v1.6 - UX Enhancements & Auto-Update

### New Features

- **Auto-Update Check**: Startup update check with one-click download.
- **Keyboard Shortcuts**: Comprehensive shortcuts (arrow keys, Home/End, F for flip, Ctrl+O, F1 for help).
- **Shortcuts Help Dialog**: Press F1 to see all shortcuts.
- **History Search & Filters**: Search by player, opening, event, date, ECO; filter by result and source.

### Improvements

- **Consistent Icon System**: QtAwesome (FontAwesome) icons throughout the app.
- **Configurable Engine Depth**: Choose analysis depth (10-25) from Settings.
- **UI Polish**: Consistent typography, muted color palette, clean card layout, button style variants.

---

## v1.5 - Themes, Stats Overhaul & Polish

### New Features

- **Splash Screen**: Beautiful startup screen for a polished launch experience.
- **Board & Piece Themes**: Customizable board colors and piece sets.
- **Live Settings Update**: All settings apply immediately without restart.
- **Stats by Piece Color**: Performance metrics broken down by White vs Black.

### Improvements

- **Stats Page Overhaul**: Completely redesigned Metrics dashboard.
- **Accuracy Algorithm Overhaul**: Lichess-style volatility-weighted harmonic mean, proper win probability conversion, tuned thresholds.
- **Move Classification**: Checkmate always classified as "Best"; tightened Inaccuracy/Mistake/Blunder thresholds; book moves get 100% accuracy.

### Bug Fixes

- **Final Position Score Bug**: Fixed `_analyze_final_position` not returning the score.
- **0% Accuracy Prevention**: Safeguards to prevent moves from getting 0% accuracy.

---

## v1.4 - Load Options, Data Backup & UI Overhaul

### New Features

- **Lichess URL Loading**: Direct support for loading games via Lichess links.
- **Paste PGN**: Quick option to load games by pasting PGN text.
- **CSV Export/Import**: Export/import game history for backup.
- **Settings Overhaul**: Completely redesigned Settings UI with centered layout.

### Improvements

- **Game History**: Visual source indicators (Lichess, Chess.com, PGN) in history list.
- **Code Quality**: Major refactoring with integrity tests.

### Bug Fixes

- **Settings Navigation**: Fixed unresponsive "Go to Settings" button.
- **Data Consistency**: Fixed missing ELO ratings on loaded games.
- **Game Duplication**: Resolved duplicate entries on import.

---

## v1.3 - Data, UI Polish & AI Coach

### New Features

- **Lichess Support**: Load games directly from Lichess usernames.
- **Ending Distribution Chart**: Visualizes game outcomes by type (Checkmate, Resignation, Time, Abandon).
- **Loading Overlay**: Non-blocking overlay while fetching games from online APIs.

### Improvements

- **AI Coach**: Refreshed UI with Refresh button, markdown/emoji stripping, and placeholder state.
- **Data Enrichment**: Database now stores opening, player ratings, termination, and FEN.
- **Game List**: Results clearly visible in game selection dialog.

### Bug Fixes

- **Checkmate Classification**: Fixed checkmates incorrectly classified as Blunders.
- **Book Move Count**: Fixed double-counting of book moves in summaries.

---

## v1.2 - UI Overhaul & Metrics Dashboard

### New Features

- **Metrics Dashboard**: Stats page with Overview, Move Quality, and Openings tabs.
- **Modern Sidebar UI**: Sleek integrated sidebar replacing the top menu bar.
- **Chess.com Game Selection**: Dialog with game details when loading from Chess.com.

### Improvements

- **Layout Optimization**: Better spacing and arrangement of analysis panel.
- **Visual Polish**: Fixed QFont warnings, added Exit button to sidebar.

---

## v1.1 - Analysis Refinements & UI Fixes

### New Features

- **Game History**: Auto-saves analyzed games with last-game restoration on startup.

### Improvements

- **"Miss" Classification**: Detects missed wins and missed checkmates.
- **Accuracy Formula**: Reverted to `100 * exp(-0.004 * acpl)` for consistent scoring.
- **Best Move Visibility**: Fixed missing icons in move list and on board.
- **Game Info Header**: Displays "White (Elo) vs Black (Elo) [Result]".

### Bug Fixes

- **Mate Score Accuracy**: Mate scores correctly converted to capped CP value for ACPL calculation.
- **Crashes**: Fixed `NameError` and `AttributeError` on startup.

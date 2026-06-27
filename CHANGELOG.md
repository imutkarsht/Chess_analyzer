# Changelog

## v2.1.0 - Analysis Explorer, Polyglot Books & Auto-Update (Latest)

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

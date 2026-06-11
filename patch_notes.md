# Patch Notes

## v2.0.1 - Unified Load Dialog & UI Polish

These changes are part of the latest stable v2.0.1 release.

### New Features & UI Polish
- **Unified Load Game Dialog**: Consolidates all game loading sources (PGN file, PGN text, Chess.com, Lichess) into a single modal. Game lists load asynchronously via a background worker, avoiding UI freezes. Each game shows full metadata (date, result, ELOs, time control, move count).
- **History Pagination & Per-Game Delete**: Game history now loads page by page. Individual games can be deleted from the database without purging the entire history.
- **Multi-LLM Profile Support**: Supports profile-based LLM configurations (Groq, LM Studio, MiniMax, Custom OpenAI-compatible endpoints) and allows switching the active profile directly in Settings.
- **Stockfish Path Validator**: A "Test Engine" button in Settings verifies the configured Stockfish binary inline and provides immediate visual feedback.
- **Evaluation Graph Navigation**: Click any point on the evaluation graph to jump directly to that move in the game.
- **Dynamic Accent Color**: Updating the accent color in Settings updates the entire UI in real time without requiring a restart.
- **Real-Time Engine Status**: Status bar indicates real-time engine states (Engine Ready - green, Calculating - orange spinner, Engine Offline - red).
- **Last-Move Square Highlighting**: Highlights the from and to squares of the last played move on the board with a subtle accent overlay.
- **Sound Effects Toggle**: Switch sound effects on or off under Settings -> Appearance.
- **Configurable Game Fetch Limit**: Control how many games are fetched from online APIs (1-30).
- **Lichess Clock Data**: Fetches clock times for each move and includes them in the AI summary prompt.
- **Chess960 Variant Icon**: Redesigned and renamed the freestyle variant icon to Chess960.
- **Custom Hexagonal Classification Icons**: Replaced default move classification and time control icons with high-quality custom hexagonal shapes.

### Improvements & Fixes
- **Local Application Data Paths**: Migrated `config.json`, SQLite database (`analysis_cache.db`), and `chess_analyzer.log` to OS-standard user data folders (e.g. `~/Library/Application Support/ChessAnalyzerPro` on macOS) instead of the app root.
- **Stats Dashboard Layout**: Donut charts grouped into a dedicated row, and Settings uses a custom MasonryLayout.
- **Live Engine CPU Optimization**: Conservative multi-PV defaults and a configurable per-position time budget prevent overheating on laptops.
- **Chess.com URL Fetch Speed**: Optimized Chess.com URL fetches.
- **Keyboard Navigation Fixes**: Enhanced arrow key, Home/End, and graph navigation.
- **Lichess Token Auth**: Solved `401 Unauthorized` errors when retrieving book moves from the Lichess Opening Explorer.
- **Worker Thread Leak**: Analysis worker thread is properly closed on application exit.
- **Move Count Display**: Fixed move count truncation past 9 in the move list.
- **Default Move Type**: Unanalyzed moves are classified as `book` by default rather than blank.

---

## v1.7 - Groq API Integration & Lichess Authentication Fix

### New Features
- **Groq API Integration**: Switched from the deprecated `google.generativeai` (Gemini) SDK to the official high-speed `groq` SDK for AI summaries and coach insights.
- **Configurable AI Models**: Users can now change and customize the Groq model ID (defaults to `llama-3.3-70b-versatile`) directly in the Settings tab.

### Bug Fixes & GUI Improvements
- **Lichess Opening Explorer Auth**: Authenticated Opening Explorer API requests using Lichess personal access tokens to fix the `401 Unauthorized` block on opening explorer book move lookups.
- **Evaluation Graph Height Pinning**: Locked the evaluation graph widget to its intrinsic height, preventing it from jumping in size when paging through games.
- **Per-Side Captured Pieces Layout**: Split captured pieces into two single-side rows (Black's captures above the board, White's below) with a locked 56px height, preventing the board from shifting on captures. Updated `flip_board()` to dynamically swap rows.
- **Captured Piece Chips & Advantage Pinning**: Inverted the backgrounds of captured piece chips for high contrast (dark on light and vice versa), enlarged piece symbols to 26px, and pinned the `+N` advantage counter chip to the left.
- **Square Board Enforcement & Eval Bar Alignment**: Enforced a strictly square aspect ratio for the board during resize events and aligned the evaluation bar to match the board's height and top edge.
- **Direct Geometry Control**: Replaced `QHBoxLayout` in `BoardWidget` with direct child geometry positioning to stop the layout manager from distorting square shapes during board updates.
- **Compact Pawn Count Chips**: Display captured pawns as a single chip with superscript counts (e.g., `♟³`) to keep the rows compact and prevent horizontal distortion.

---

## v1.6 - UX Enhancements & Auto-Update

### New Features
- **Auto-Update Check**: App now checks for updates on startup and notifies you when a new version is available with one-click download.
- **Keyboard Shortcuts**: Added comprehensive keyboard shortcuts (←/→ navigation, Home/End, F for flip, Ctrl+O to open, F1 for help).
- **Shortcuts Help Dialog**: Press F1 or click Help button to see all available keyboard shortcuts.
- **History Search**: Search games by player name, opening, event, date, or ECO code with real-time filtering.
- **History Filters & Sorting**: Filter games by result (Wins/Losses/Draws), source (Chess.com/Lichess/File), and sort by date or move count.
- **Enhanced Game Cards**: History list now shows opening name, time control, move count, termination type, and accuracy scores.

### Improvements
- **Consistent Icon System**: Migrated to QtAwesome (FontAwesome) icons throughout the app for a unified modern look.
- **Settings UI Polish**: All buttons now have appropriate icons (save, folder, key, palette, trash, globe, etc.).
- **Configurable Engine Depth**: Choose analysis depth (10-25) from Settings.
- **Dynamic Eval Graph**: Evaluation graph now adapts dynamically to game data.
- **Improved Loaders**: Better loading indicators and overlay improvements.

### UI Polish
- **Consistent Typography**: Unified font sizes and weights across all views.
- **Muted Color Palette**: Replaced bright emojis and colorful badges with professional muted tones.
- **Game List Redesign**: Clean card layout with icon-based metadata (date, time control, moves, termination).
- **Button Styling**: Consistent button styles - primary (accent), secondary (bordered), and danger (red) variants.
- **Sidebar Help Button**: Added Help (F1) button with FontAwesome icon for quick access to shortcuts.
- **Update Dialog**: Clean modal with version badges and formatted changelog.
- **History Controls**: Polished search bar, filter dropdowns, and action buttons with icons.

### Technical
- **Code Refactoring**: Consistent font usage and improved UI component structure.
- **Icon Assets**: Updated icon system with QtAwesome fallbacks.
- **Default Window Size**: Optimized default window dimensions.
- **Dependencies**: Added `qtawesome` and `packaging` libraries.

---

## v1.5 - Themes, Stats Overhaul & Polish

### New Features
- **Splash Screen**: Added a beautiful splash screen that displays during application startup for a more polished launch experience.
- **Board Themes**: Introduced multiple board color themes in the Settings, allowing users to customize the look of the chessboard.
- **Piece Themes**: Added support for different piece sets, letting users choose their preferred piece style.
- **Stats by Piece Color**: The Stats page now displays performance metrics broken down by piece color (White vs Black), giving deeper insight into your play.
- **Live Settings Update**: All settings now apply immediately without requiring app restart (Groq API Key, Lichess Token, Usernames).

### Improvements
- **Stats Page Overhaul**: Completely redesigned the Metrics/Stats dashboard for better visual presentation and more insightful data visualization.
- **Accuracy Algorithm Overhaul**: Complete rewrite of the accuracy calculation system:
    - Implemented Lichess-style **volatility-weighted harmonic mean** for game accuracy.
    - Added proper **Win Probability** conversion formula from centipawns.
    - Tuned decay constant and thresholds to better match Chess.com accuracy values.
- **Move Classification Improvements**:
    - **Checkmate Fix**: Moves delivering checkmate are now always classified as "Best" (was incorrectly showing as "Miss").
    - Tightened WPL thresholds for more accurate Inaccuracy/Mistake/Blunder detection.
    - Book moves now receive 100% accuracy (theoretical best play).
- **Classification Summary Logging**: Detailed breakdown of move classifications now logged after each analysis.
- **GUI Restructuring**: Major overhaul of the GUI code structure for better maintainability and performance.
- **Code Refactoring**: 
    - Created reusable utility functions to reduce code duplication.
    - Refactored the metric widget for cleaner architecture.
    - Removed redundant code across the codebase.
- **Backend Improvements**: Refactored backend code for better performance and cleaner architecture.

### Bug Fixes
- **Final Position Score Bug**: Fixed a critical bug where `_analyze_final_position` wasn't returning the score, causing the last move to always get incorrect accuracy.
- **0% Accuracy Moves**: Added safeguards to prevent moves from getting 0% accuracy (which destroyed harmonic mean calculations).
- **Metric Widget**: Fixed multiple bugs related to the metric widget display and statistics calculations.
- **Stats Display**: Resolved issues where stats were not updating correctly in certain scenarios.
- **UI Update Bug**: Fixed a bug where UI elements were not refreshing properly after certain actions.

---

## v1.4 - Load Options, Data Backup & UI Overhaul

### New Features
- **Enhanced Game Loading**:
    - **Load from Lichess URL**: Direct support for loading games via Lichess game links.
    - **Paste PGN**: Quick option to load games by pasting PGN text directly from the clipboard.
    - **Consolidated Menu**: Grouped all loading options (File, User, URL, Paste) into a cleaner menu structure.
- **Data Management**:
    - **CSV Export/Import**: Added functionality to export all your saved games to a CSV file for backup and import them back into your history.
- **Settings Overhaul**:
    - **Official Website Links**: Added direct links to the official website and feedback page in the Settings tab.
    - **UI Redesign**: Completely overhauled the Settings UI for better aesthetics, centered layout, and improved color blending.

### Improvements
- **Game History**:
    - Added visual indicators to show the source of the game (Lichess, Chess.com, PGN, etc.) in the history list.
- **Code Quality**:
    - Major refactoring to reduce redundancy and improve overall code quality.
    - Added integrity tests to ensure stability.

### Bug Fixes
- **Settings Navigation**: Fixed an issue where the "Go to Settings" button was unresponsive.
- **Engine Lines**: Resolved a graphical glitch where engine evaluation lines would display incorrectly.
- **Data Consistency**: Fixed a bug where loaded games were occasionally missing ELO ratings.
- **Game Duplication**: Resolved an issue where importing games could create duplicate entries in the database.

## v1.3 - Data, UI Polish & AI Coach

### New Features
- **Lichess Support**: 
    - Added ability to load games directly from **Lichess.org** usernames.
    - Application now remembers your last used Lichess username.
- **Loading Experience**:
    - Implemented a **Beautiful UI Loader** that displays a non-blocking overlay while fetching games from online APIs (Chess.com/Lichess).
- **Ending Distribution**:
    - Added a new **Ending Distribution** chart to the Metrics Dashboard, visualizing game outcomes by type (Checkmate, Resignation, Time, Abandon).

### Improvements
- **AI Coach Insights**:
    - Completely refreshed the **AI Coach** section with a cleaner UI.
    - Added a specific **Refresh Button** for generating insights.
    - Improved text processing to remove markdown/emojis for a professional look.
    - Added "Placeholder" state for better UX before analysis.
- **Metrics Dashboard**:
    - Enhanced visual styling of the Saved Games section.
- **Game List**:
    - Game results (1-0, 0-1, etc.) are now clearly visible in the "Select Game" dialog list.
- **Data Enrichment**:
    - Database now stores richer metadata including **Opening**, **Player Ratings**, **Termination**, and **FEN**.
    - Added support for saving usernames to `config.json` for convenience.

### Bug Fixes
- **Analysis Accuracy**:
    - Fixed a critical bug where **Checkmates** were sometimes incorrectly classified as **Blunders**.
    - Fixed a **Move Count Mismatch** where "Book" moves were being double-counted in summaries.

## v1.2 - UI Overhaul & Metrics Dashboard

### New Features
- **Metrics Dashboard**: 
    - Added a new **Stats** page providing comprehensive insights into your chess performance.
    - **Overview Tab**: View total games analyzed, win/loss/draw rates, and average accuracy across all games.
    - **Move Quality Tab**: Visual breakdown of move classifications (Brilliant, Great, Blunder, etc.) using interactive pie charts.
    - **Openings Tab**: Analyze your most frequent openings with a bar chart display.
- **Enhanced Navigation & Aesthetics**:
    - **Modern Sidebar UI**: Replaced the traditional top menu bar with a sleek, integrated sidebar for seamless navigation between Analyze, History, Stats, and Settings views.
    - **Visual Consistency**: Unified the application's look and feel with a consistent design language, improved icon set, and refined accent color usage across all panels.
    - **Consolidated Load Menu**: Unified game loading options into a single "Load Game" button with a dropdown menu for PGN, User, and Link imports.
- **Chess.com Integration**:
    - **Game Selection Dialog**: When loading from a Chess.com user, a new dialog now appears listing the last 5 games with details (Date, Opponent, Rating), allowing you to choose exactly which game to analyze.

### User Interface Refinements
- **Layout Optimization**: 
    - Improved the spacing and arrangement of the analysis panel to prevent UI squeezing.
    - Made the "Analyze Game" button more prominent for better accessibility.
- **Visual Polish**:
    - Fixed `QFont` warnings that were cluttering the logs, ensuring smoother font rendering in the Evaluation Bar.
    - Added a new "Exit" button to the sidebar for quick application closure.

## v1.1 - Analysis Refinements & UI Fixes

### New Features
- **Game History**:
    - Automatically saves analyzed games to a local history file.
    - Restores the last analyzed game on application startup.
    - Added "Clear History" option to the File menu.

### Analysis & Classification
- **New "Miss" Classification**: 
    - Implemented logic to identify "Missed Wins" (significant drop in win probability from a winning position).
    - Added detection for "Missed Mates" (failing to find a forced checkmate sequence).
- **Accuracy Fix**: 
    - Resolved a bug where games containing checkmates could result in 0.0% accuracy.
    - Mate scores are now correctly converted to a capped CP value (2000) for ACPL calculation.
- **"Great" Move Tuning**: 
    - Significantly increased the threshold for "Great" moves to a **15%** win probability difference. This makes "Great" moves much rarer and more meaningful, appearing only when a move is vastly superior to alternatives.
- **Accuracy Formula**: 
    - Reverted the accuracy formula to `100 * exp(-0.004 * acpl)` to ensure consistent and familiar scoring.

### User Interface
- **"Best" Move Visibility**: 
    - Fixed a persistent issue where "Best" move icons were not appearing in the move list or on the board.
    - Updated the `best.svg` icon structure and renamed it to `best_v2.svg` to bypass potential caching issues.
    - Explicitly enforced icon sizing in the Move List to ensure proper rendering.
- **Game Info Display**: 
    - Added a new header in the main window displaying "White (Elo) vs Black (Elo) [Result]" for the currently loaded game.

### Bug Fixes
- Fixed a `NameError` crash caused by a missing `QSize` import.
- Fixed an `AttributeError` related to the removal of the `game_list` component.

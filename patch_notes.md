# Patch Notes

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

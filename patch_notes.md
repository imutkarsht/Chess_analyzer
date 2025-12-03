# Patch Notes

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

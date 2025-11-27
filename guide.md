# Chess Analyzer - Developer Guide

Welcome to the Chess Analyzer codebase! This guide is designed to help you understand the project structure, key components, and how to extend the application.

## Project Structure

```
src/
├── backend/            # Core logic (Analysis, Engine, Parsing)
│   ├── analyzer.py     # Main analysis logic (Move classification, Accuracy)
│   ├── engine.py       # Wrapper for UCI engines (Stockfish)
│   ├── pgn_parser.py   # PGN parsing utilities
│   ├── models.py       # Data models (GameAnalysis, MoveAnalysis)
│   ├── cache.py        # Analysis caching mechanism
│   └── chess_com_api.py# Chess.com API integration
├── gui/                # User Interface (PyQt6)
│   ├── main_window.py  # Main application window
│   ├── board_widget.py # Chess board rendering (SVG)
│   ├── eval_bar.py     # Evaluation bar widget
│   ├── analysis_view.py# Move list and summary table
│   ├── game_list.py    # List of loaded games
│   ├── graph_widget.py # Evaluation graph
│   └── styles.py       # QSS Stylesheets (Dark Theme)
└── main.py             # Entry point
```

## Key Components

### Backend

#### `Analyzer` (`src/backend/analyzer.py`)
This is the heart of the application. It orchestrates the analysis process:
1.  **Engine Management**: Starts and stops the chess engine.
2.  **Move Loop**: Iterates through every move in the game.
3.  **Evaluation**: Uses `EngineManager` to get the evaluation (centipawns/mate) for each position.
4.  **Win Probability**: Converts centipawn evaluations into Win Probability (0.0 - 1.0) using a logistic curve.
5.  **Accuracy**: Calculates move accuracy based on the loss of Win Probability.
6.  **Classification**: Labels moves (Best, Mistake, Blunder, etc.) based on centipawn loss thresholds.

#### `EngineManager` (`src/backend/engine.py`)
Wraps the `python-chess` engine communication. It handles starting the UCI engine (e.g., Stockfish), configuring options (Threads, Hash), and sending analysis commands.

#### `PGNParser` (`src/backend/pgn_parser.py`)
Parses PGN files or text strings into `GameAnalysis` objects. It extracts metadata (players, result) and the move list.

### Frontend (GUI)

#### `MainWindow` (`src/gui/main_window.py`)
The main window that assembles all widgets. It handles:
-   Menu actions (Open PGN, Load from Chess.com).
-   Layout management (Splitter).
-   Theme application.

#### `BoardWidget` (`src/gui/board_widget.py`)
Renders the chess board using `chess.svg` and displays it in a `QSvgWidget`. It updates the board state based on the selected move.

#### `EvalBarWidget` (`src/gui/eval_bar.py`)
Visualizes the current evaluation. It uses a `QTimer` for smooth animations when the evaluation changes.

## How to Extend

### Adding a New Move Classification
1.  Open `src/backend/analyzer.py`.
2.  Update `self.thresholds` in `__init__`.
3.  Update `_classify_move` logic to use the new threshold.
4.  Open `src/gui/analysis_view.py`.
5.  Add the new type to `self.class_styles` with a color and symbol.
6.  Add the new type to the `types` list in `_update_summary`.

### Changing the Theme
1.  Open `src/gui/styles.py`.
2.  Modify the `DARK_THEME` string. You can change colors, fonts, and padding using standard CSS syntax supported by Qt (QSS).

### Adding a New API Integration
1.  Create a new file in `src/backend/` (e.g., `lichess_api.py`).
2.  Implement a class to fetch games (similar to `ChessComAPI`).
3.  Update `src/gui/main_window.py` to add a new menu action and dialog for the new service.

## Dependencies
-   `python-chess`: Core chess logic and PGN parsing.
-   `PyQt6`: GUI framework.
-   `requests`: HTTP requests for APIs.
-   `matplotlib`: (Optional) Used for graph widget (if enabled).

## Running Tests
Run `pytest` in the root directory to execute unit tests (if available).

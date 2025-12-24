# Chess Analyzer Pro - Onboarding Documentation

Welcome to the **Chess Analyzer Pro** codebase! This document is designed to guide you through the technical details of the project, explaining the structure, key components, and how to make common changes. Whether you are a beginner or an experienced developer, this guide will help you understand the "anatomy" of the application.

---

## 1. Project Overview

**Chess Analyzer Pro** is a desktop application built with **Python** and **PyQt6** that allows users to analyze chess games using the **Stockfish** engine. It provides detailed insights, including move classifications (Brilliant, Mistake, Blunder, etc.), win probability graphs, and AI-powered game summaries using Google Gemini.

### Key Technologies
*   **Language:** Python 3.10+
*   **GUI Framework:** PyQt6 (Qt for Python)
*   **Chess Logic:** `python-chess` library
*   **Engine:** Stockfish (via UCI protocol)
*   **AI:** Google Gemini API (for natural language summaries)
*   **Plotting:** Matplotlib (for evaluation graphs)

---

## 2. Directory Structure

Here is the high-level structure of the project:

```text
Chess_analyzer/
├── assets/                 # Static resources (images, icons, sounds)
├── src/                    # Source code
│   ├── backend/            # Core logic, analysis, and data handling
│   ├── gui/                # User Interface components (PyQt6)
│   └── utils/              # Helper functions (logging, config, paths)
├── tests/                  # Unit and integration tests
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── config.json             # User configuration (saved settings)
└── .env                    # Environment variables (API keys)
```

---

## 3. Architecture & Data Flow

The application follows a **Model-View-Controller (MVC)** inspired pattern:

1.  **Model (Backend):** Handles data logic.
    *   `GameAnalysis` object holds the game state, moves, and analysis results.
    *   `Analyzer` runs the heavy computation (Stockfish analysis).
2.  **View (GUI):** Displays the data.
    *   `MainWindow` is the main container.
    *   `BoardWidget` draws the chess board.
    *   `AnalysisPanel` shows stats and graphs.
3.  **Controller (Logic):**
    *   `main.py` initializes the app.
    *   Signals and Slots (PyQt6 mechanism) connect UI events (clicks) to backend functions.

### Data Flow Example: Analyzing a Game

| File | Purpose |
| :--- | :--- |
| **`analyzer.py`** | **Core Logic.** Contains the `Analyzer` class. It manages the analysis loop, calculates win probabilities, determines move accuracy (0-100%), and classifies moves (Best, Mistake, etc.). |
| **`engine.py`** | **Stockfish Wrapper.** Manages the Stockfish process. Handles starting/stopping the engine and sending UCI commands via `python-chess`. |
| **`models.py`** | **Data Structures.** Defines `GameAnalysis`, `MoveAnalysis`, and `GameMetadata` dataclasses. These objects are passed around the entire app. |
| **`pgn_parser.py`** | **PGN Handling.** Reads and parses `.pgn` files or text into `GameAnalysis` objects. |

| **`chess_com_api.py`** | **Chess.com Integration.** Fetches recent games or specific games from Chess.com using their public API. |
| **`lichess_api.py`** | **Lichess Integration.** Fetches recent games from Lichess.org users. |
| **`gemini_service.py`** | **AI Summaries.** Connects to Google's Gemini API to generate text summaries of the game based on the analysis data. |

| **`cache.py`** | **Performance.** Caches engine analysis results to avoid re-analyzing known positions. |

### `src/gui/` (The Face)

| File | Purpose |
| :--- | :--- |
| **`main_window.py`** | **Main Application.** Sets up the window, sidebar, and orchestrates the interaction between different views. It handles global events like key presses and menu actions. |
| **`analysis_view.py`** | **Analysis Dashboard.** Contains the `AnalysisPanel`, `MoveListPanel`, and `StatCard` widgets. This is where the user spends most of their time. |
| **`board_widget.py`** | **Chess Board.** Renders the board and pieces. Handles piece movement (if interactive) and board flipping. |
| **`graph_widget.py`** | **Evaluation Graph.** Draws the visual evaluation chart using Matplotlib. |
| **`metrics_widget.py`** | **Statistics.** Displays aggregate statistics across multiple games, including performance by piece color (White vs Black). |
| **`styles.py`** | **Theming.** Contains CSS-like stylesheets (QSS) for the application. Defines colors, fonts, and widget styles. |
| **`splash_screen.py`** | **Startup Screen.** Displays a branded splash screen during application initialization. |
| **`themes.py`** | **Board & Piece Themes.** Manages board color themes and piece set options for user customization. |

### `src/utils/` (The Helpers)

| File | Purpose |
| :--- | :--- |
| **`config.py`** | Manages `config.json` for saving user settings (theme, engine path, API keys, board/piece themes). |
| **`logger.py`** | Sets up the application logging (writes to `chess_analyzer.log`). |
| **`resources.py`** | Helper for loading images, icons, and sounds. |
| **`utils.py`** | Reusable utility functions shared across the codebase to reduce code duplication. |

---

## 5. How-To Guides (Making Changes)

### Scenario A: I want to change how "Blunders" are defined.
**File to modify:** `src/backend/analyzer.py`
1.  Open `analyzer.py`.
2.  Locate the `_classify_move` method (or the logic inside `analyze_game` loop).
3.  Look for the thresholds logic (e.g., `if wpl >= 0.20: move.classification = "Blunder"`).
4.  Adjust the `0.20` value. Lower means stricter (more blunders), higher means more lenient.

### Scenario B: I want to add a new column to the Move List.
**Files to modify:** `src/gui/analysis_view.py`
1.  Open `analysis_view.py`.
2.  Find the `MoveListPanel` class.
3.  In `__init__`, update `self.table.setColumnCount(3)` to `4` and add a header label.
4.  In `refresh` or `_set_move_item`, add logic to populate the new column (e.g., `self.table.setItem(row, 3, newItem)`).

### Scenario C: I want to change the app's color theme.
**File to modify:** `src/gui/styles.py`
1.  Open `styles.py`.
2.  Locate the `Styles` class.
3.  Update the color constants at the top (e.g., `COLOR_BACKGROUND`, `COLOR_ACCENT`).
4.  The app uses these constants to generate the QSS strings.

### Scenario D: I want to add a new API (e.g., Lichess).
> **Note:** Lichess support was added in v1.3! You can check `src/backend/lichess_api.py` for the implementation.
**Files to create/modify:**
1.  **Create** `src/backend/your_new_api.py` (copy structure from `chess_com_api.py`).
2.  **Modify** `src/gui/main_window.py`:
    *   Import your new API class.
    *   Add a new action to the "Load Game" menu.
    *   Connect the action to a new method.

---

## 6. Running the Application

### Prerequisites
1.  Install Python 3.10+.
2.  Download **Stockfish** and note its path.

### Setup
1.  Create a virtual environment:
    ```bash
    python -m venv venv
    .\venv\Scripts\activate  # Windows
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

### Running
```bash
python main.py
```
*Note: On first run, go to **Settings** and select your Stockfish executable path.*

---

## 7. Testing

We use **pytest** for unit and integration testing. It is crucial to run tests before pushing any changes to ensure stability.

### Running Tests
To run all tests, execute the following command in your terminal:
```bash
pytest
```

To run a specific test file:
```bash
pytest tests/test_game_load.py
```

> [!IMPORTANT]
> **Always run tests after adding a new feature!**
> Ensuring that new code doesn't break existing functionality is key to maintaining a healthy codebase.

---

## 8. Troubleshooting

*   **"Engine not found":** Ensure the path in Settings is correct and points to the Stockfish **executable** (not the folder).
*   **"API Key Error":** If using AI Summary, ensure your Gemini API key is valid and set in Settings.
*   **Logs:** Check `chess_analyzer.log` in the root directory for detailed error messages.

---

## 9. Building from Source

To create a standalone executable (`.exe`) for distribution, we use **PyInstaller**. The build configuration is defined in `build.spec`.

### Steps
1.  Ensure you have the development dependencies installed:
    ```bash
    pip install pyinstaller
    ```
2.  Run the build command:
    ```bash
    pyinstaller build.spec
    ```
3.  The output executable will be located in the `dist/` directory:
    ```text
    dist/ChessAnalyzerPro.exe
    ```

> [!NOTE]
> The `build.spec` file is configured to include necessary assets (images, icons) and handle hidden imports for libraries like `python-chess` and `PyQt6`.

# Chess Analyzer Pro - Onboarding Documentation

Welcome to the **Chess Analyzer Pro** codebase! This document is designed to guide you through the technical details of the project, explaining the structure, key components, and how to make common changes. Whether you are a beginner or an experienced developer, this guide will help you understand the "anatomy" of the application.

---

## 1. Project Overview

**Chess Analyzer Pro** is a desktop application built with **Python** and **PyQt6** that allows users to analyze chess games using the **Stockfish** engine. It provides detailed insights, including move classifications (Brilliant, Mistake, Blunder, etc.), win probability graphs, and AI-powered game summaries using Groq.

### Key Technologies
*   **Language:** Python 3.10+
*   **GUI Framework:** PyQt6 (Qt for Python)
*   **Chess Logic:** `python-chess` library
*   **Engine:** Stockfish (via UCI protocol)
*   **AI:** Groq API (for natural language summaries)
*   **Plotting:** Matplotlib (for evaluation graphs)

---

## 2. Directory Structure

Here is the high-level structure of the project:

```text
Chess_analyzer/
├── assets/                 # Static resources (images, icons, sounds)
├── src/                    # Source code
│   ├── backend/            # Core logic, analysis, and data handling
│   │   ├── analysis/       # Engine, move analysis, move classification, math helpers
│   │   ├── api/            # Chess.com & Lichess API integrations
│   │   ├── storage/        # Game history, caching, parsing, data models
│   │   ├── services/       # External services (Groq AI Coach)
│   │   └── updater/        # In-app desktop updater
│   ├── gui/                # User Interface components (PyQt6)
│   │   ├── views/          # Main page views (Analyze, History, Stats, Settings)
│   │   ├── components/     # Reusable layout and dashboard card widgets
│   │   ├── analysis/       # Background analysis threads and workers
│   │   └── utils/          # GUI-specific layout and widget factories
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
| **[`analyzer.py`](file:///Users/utkarsh/Developer/Projects/Chess_analyzer/src/backend/analysis/analyzer.py)** | **Core Logic.** Manages the analysis loop, calculates win probabilities, determines move accuracy (0-100%), and classifies moves. |
| **[`engine.py`](file:///Users/utkarsh/Developer/Projects/Chess_analyzer/src/backend/analysis/engine.py)** | **Stockfish Wrapper.** Manages the Stockfish process. Handles starting/stopping the engine and sending UCI commands. |
| **[`models.py`](file:///Users/utkarsh/Developer/Projects/Chess_analyzer/src/backend/storage/models.py)** | **Data Structures.** Defines `GameAnalysis`, `MoveAnalysis`, and `GameMetadata` dataclasses. |
| **[`pgn_parser.py`](file:///Users/utkarsh/Developer/Projects/Chess_analyzer/src/backend/storage/pgn_parser.py)** | **PGN Handling.** Reads and parses `.pgn` files or text into `GameAnalysis` objects. |
| **[`chess_com_api.py`](file:///Users/utkarsh/Developer/Projects/Chess_analyzer/src/backend/api/chess_com_api.py)** | **Chess.com Integration.** Fetches recent games or specific games from Chess.com. |
| **[`lichess_api.py`](file:///Users/utkarsh/Developer/Projects/Chess_analyzer/src/backend/api/lichess_api.py)** | **Lichess Integration.** Fetches recent games from Lichess.org users. |
| **[`groq_service.py`](file:///Users/utkarsh/Developer/Projects/Chess_analyzer/src/backend/services/groq_service.py)** | **AI Summaries.** Connects to Groq's API to generate text summaries of the game. |
| **[`cache.py`](file:///Users/utkarsh/Developer/Projects/Chess_analyzer/src/backend/storage/cache.py)** | **Performance.** Caches engine analysis results to avoid re-analyzing known positions. |

### `src/gui/` (The Face)

| File | Purpose |
| :--- | :--- |
| **[`main_window.py`](file:///Users/utkarsh/Developer/Projects/Chess_analyzer/src/gui/main_window.py)** | **Main Application.** Sets up the window, sidebar, and orchestrates the interaction between different views. |
| **[`analysis_view.py`](file:///Users/utkarsh/Developer/Projects/Chess_analyzer/src/gui/views/analysis_view.py)** | **Analysis Dashboard.** Re-exports the `AnalysisPanel` and `MoveListPanel` views. |
| **[`board_widget.py`](file:///Users/utkarsh/Developer/Projects/Chess_analyzer/src/gui/board/board_widget.py)** | **Chess Board.** Renders the board and pieces, and handles flipping. |
| **[`graph_widget.py`](file:///Users/utkarsh/Developer/Projects/Chess_analyzer/src/gui/components/graph_widget.py)** | **Evaluation Graph.** Draws the visual evaluation chart using Matplotlib. |
| **[`metrics_view.py`](file:///Users/utkarsh/Developer/Projects/Chess_analyzer/src/gui/views/metrics_view.py)** | **Statistics Dashboard.** Coordinates the decomposed metrics dashboard card widgets under `src/gui/views/metrics/`. |
| **[`styles.py`](file:///Users/utkarsh/Developer/Projects/Chess_analyzer/src/gui/styles.py)** | **Theming.** Contains CSS-like stylesheets (QSS) for the application. |
| **[`splash_screen.py`](file:///Users/utkarsh/Developer/Projects/Chess_analyzer/src/gui/dialogs/splash_screen.py)** | **Startup Screen.** Displays a branded splash screen. |
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
**File to modify:** `src/backend/analysis/move_classifier.py`
1.  Open `move_classifier.py`.
2.  Locate the classification logic and threshold constants.
3.  Adjust the thresholds to make them stricter or more lenient.

### Scenario B: I want to add a new column to the Move List.
**Files to modify:** `src/gui/analysis/move_list_panel.py`
1.  Open `move_list_panel.py`.
2.  In `__init__`, update the table columns configuration and headers.
3.  Update the populate logic to draw the new column item.

### Scenario C: I want to change the app's color theme.
**File to modify:** `src/gui/styles.py`
1.  Open `styles.py`.
2.  Locate the `Styles` class.
3.  Update the color constants at the top (e.g., `COLOR_BACKGROUND`, `COLOR_ACCENT`).
4.  The app uses these constants to generate the QSS strings.

### Scenario D: I want to add a new game loading source.
**Files to create/modify:**
1.  **Create** your API class in `src/backend/` if it requires fetching online games (e.g., see `src/backend/lichess_api.py`).
2.  **Modify** `src/gui/dialogs/load_game_dialog.py`:
    *   Create a new right-panel tab class representing the UI layout for your source (e.g., see `_ChessComPanel` or `_PgnTextPanel`).
    *   Add your new source ID and details to the `_SOURCES` tuple.
    *   Instantiate the panel inside `LoadGameDialog._build_panels()` and add it to `self.stack`.
    *   Wire the panel's signals (`pgn_ready`, `pending_cleared`) to trigger `self._set_pending` in the parent dialog.
    *   Update `LoadGameDialog._switch_source` to handle resetting your new panel.

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
*   **"API Key Error":** If using AI Summary, ensure your LLM configuration profile is active and the API key is valid.
*   **Logs:** Check `chess_analyzer.log` in the platform-specific user data directory (e.g., `~/Library/Application Support/ChessAnalyzerPro` on macOS) for detailed error messages.

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

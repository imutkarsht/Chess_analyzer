# How to Use Chess Analyzer Pro

This comprehensive guide takes you from installation to mastering the advanced features of Chess Analyzer Pro.

## 1. Getting the Latest Build

To get the latest version of the application:
1.  **Clone/Pull the Repository**: Ensure you have the latest code from GitHub.
    ```bash
    git pull origin main
    ```
**Build the Executable**: We use PyInstaller to create a standalone `.exe`.
    ```bash
    pyinstaller build.spec
    ```
    *This will create a `dist` folder containing the `ChessAnalyzerPro.exe` file.*

2. **Download latest build**
    * Download the latest build from the [releases page](https://github.com/imutkarsht/Chess_analyzer/releases).
---

## 2. Running the Application

1.  Navigate to the `dist` folder created in the previous step.
2.  Double-click **`ChessAnalyzerPro.exe`** to launch the application.

> **Note**: On the very first run, you may be prompted to configure the Stockfish engine path.

---

## 3. Configuration

All configurations are managed locally in the **Settings** tab. Click on the "Settings" icon (gear) in the sidebar to access them.

### A. Stockfish Engine (Crucial)
You **must** download and link the Stockfish engine for analysis to work.
1.  Download Stockfish from [stockfishchess.org](https://stockfishchess.org/download/).
2.  Extract the `.exe` file to a known location (e.g., a `stockfish` folder inside the app directory).
3.  In the app, go to **Settings > Chess Engine**.
4.  Click **Browse**, select the `stockfish.exe` file, and click **Save Engine Path**.

### B. API Configuration
To unlock advanced features like AI Summaries and Lichess imports:

*   **Gemini API Key**:
    *   Required for: **AI Game Summaries** and **Coach Insights**.
    *   Get a key from [Google AI Studio](https://aistudio.google.com/).
    *   Enter it in **Settings > API Configuration > Gemini API Key** and click **Save**.

*   **Lichess API Token**:
    *   Required for: Importing user games from Lichess.
    *   Generate a personal access token from your Lichess account (Preferences > API Access tokens).
    *   Enter it in **Settings > API Configuration > Lichess API Token** and click **Save**.

### C. Player Usernames
Pre-configure your usernames to make loading games faster.
*   Enter your **Chess.com** and **Lichess.org** usernames in the **Settings > Player Usernames** section.
*   Once saved, the "Load from User" dialogs will auto-fill with these names.

### D. Appearance
*   **Accent Color**: Customize the application's look by changing the accent color in **Settings > Appearance**.

---

## 4. Dependencies for Local Execution

The generated `.exe` is mostly standalone, but it requires the following external components:

1.  **Stockfish Engine**: As mentioned above, this is **not bundled** and must be downloaded separately.
2.  **VS C++ Redistributable**: On some fresh Windows installations, you might need the Visual C++ Redistributable packages (typically already installed on most systems).
3.  **Internet Connection**: Required for:
    *   Importing games from Chess.com/Lichess.
    *   Fetching Opening names (if using online book).
    *   Generating AI Summaries (Gemini).

---

## 5. Auto-Generated Files

The application automatically creates and manages the following files in its root directory (where the `.exe` is located):

| File | Purpose |
| :--- | :--- |
| **`config.json`** | Stores your saved settings (engine path, usernames, theme preferences). |
| **`analysis_cache.db`** | A SQLite database that stores analysis results. This prevents re-analyzing the same moves, making future reviews instant. |
| **`chess_analyzer.log`** | A text file containing application logs. useful for debugging errors or crashes. |

---

## 6. Data Privacy & Local Storage

Your privacy is paramount. **We do not collect any personal data.**

*   **Local Storage**: All your data, including game history, analysis results (`analysis_cache.db`), and configurations (`config.json`), remains strictly on your local machine.
*   **No Cloud Sync**: We do not send your games or analysis to any remote server (except to Google/Lichess APIs when you explicitly trigger those features).
*   **API Keys**: Your Gemini and Lichess keys are stored locally in `config.json` and are **never** shared with us.

---

## 7. How to Use: A to Z

### Loading Games
There are multiple ways to load a game into the analyzer:
1.  **Open PGN File**: `File > Open PGN...` - Load a game from a local `.pgn` file.
2.  **Load from Chess.com User**: `File > Load from Chess.com User...` - Fetches the most recent games for the configured username.
3.  **Load from Lichess User**: `File > Load from Lichess User...` - Fetches recent games from Lichess.

### Analysis & Features
Once a game is loaded:

*   **Start Analysis**: Click the **Analyze Game** button in the sidebar. The engine will evaluate every move.
*   **Navigation**:
    *   Use the **Arrow Keys** (Left/Right) to move through the game.
    *   Click on any move in the **Move List** to jump to that position.
    *   Drag the scrollbar or click on the **Evaluation Graph** to jump to key moments.
*   **Move Classification**:
    *   Moves are color-coded:
        *   🔵 **Brilliant/Great**: Exceptional play.
        *   🟢 **Best/Excellent**: Optimal moves.
        *   🟡 **Inaccuracy**: Slight loss of advantage.
        *   🔴 **Mistake/Blunder**: Significant errors.
*   **AI Summary**: After analysis is complete, click the "AI Summary" tab (robot icon) to get a natural language explanation of the game's story.

### Detailed Stats
*   **Game Stats**: View accuracy per player, opening name, and blunder counts in the **Analysis Panel**.
*   **Global Stats (Metrics)**: Click the **Stats** icon in the sidebar to see your performance over time (Win/Loss rates, accuracy trends) across all analyzed games.

### History & Caching
*   **History Tab**: Keeps a record of all games you've analyzed. Double-click any entry to reload that game.
*   **Analysis Cache**: The app remembers every position it has analyzed. If you reload an old game, the analysis will appear *instantly* without running the engine again.
    *   *Tip: You can clear this cache in Settings if it gets too large.*

---

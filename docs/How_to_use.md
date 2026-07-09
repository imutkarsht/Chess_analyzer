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

> **Note**: On the very first launch, or if no chess engine is configured, the **Setup Wizard** will automatically launch to guide you through the initial configuration.

---

## 3. Configuration & Data Files

All configuration, logs, and database files are now automatically managed inside OS-standard user directories rather than the application root:
- **macOS**: `~/Library/Application Support/ChessAnalyzerPro`
- **Windows**: `%APPDATA%/ChessAnalyzerPro`
- **Linux**: `~/.local/share/chessanalyzerpro`

Configurations are managed in the **Settings** tab (gear icon in the sidebar) or through the first-run Setup Wizard.

### A. Stockfish Engine (Crucial)
You must configure the Stockfish engine for analysis. The application makes this extremely simple:
1. **Auto-Detection**: On startup, the application automatically attempts to resolve the Stockfish path by checking your config, system `PATH`, common installation paths, and any previously downloaded engines.
2. **One-Click Downloader**: If no engine is found, you can download a platform-matched Stockfish binary automatically from within the Setup Wizard or Settings view.
3. **Manual Selection**: If you prefer, go to **Settings > Chess Engine**, click **Browse**, and select your custom Stockfish executable.
4. Click **Test Engine** to verify the path is valid and functional.

### B. LLM & API Configuration
To unlock advanced features like AI Summaries and Lichess imports, configure the following APIs:

*   **LLM Profiles (AI summaries & coaching)**:
    - The application supports multiple **LLM Profiles** with different providers.
    - Select from **Groq** (Cloud), **LM Studio** (Local), **MiniMax** (Cloud), or **Custom** (any OpenAI-compatible endpoint).
    - Provide the **API Key**, **Model ID**, and **Base URL** (if using LM Studio or a Custom endpoint).
    - Select your active profile. All API insights will use the active profile.
*   **Lichess API Token**:
    - Required to fetch Opening/Book move names from Lichess without rate-limit issues, and to fetch private games.
    - Generate a token at [lichess.org/account/oauth/token](https://lichess.org/account/oauth/token) with the `Read games` scope.
    - Paste it into the **Lichess API Token** field in Settings and click **Save**.

### C. Player Usernames
Pre-configure your usernames to make loading games faster:
*   Enter your **Chess.com** and **Lichess.org** usernames in **Settings > Player Usernames** and click **Save**.
*   Once saved, the Load Game dialog will auto-fill with these names and personal stats calculations will automatically filter to show your games.

### D. Appearance & Audio
*   **Accent Color**: Select an accent color in **Settings > Appearance**. Changing the color updates the entire UI in real time.
*   **Board & Piece Themes**: Select a board theme (Default, Brown, Blue, Purple, Grey) and piece set (cburnett, merida, alpha, cardinal, chess7) to update the visual board immediately.
*   **Custom SVG Theme Import**: You can import any folder of 12 SVG piece images (`wk.svg`, `bp.svg`, etc.) in Appearance Settings. The app will automatically scale and normalize them to fit the board properly.
*   **Sound Effects**: Check or uncheck **Enable Sound Effects** in **Settings > Appearance** to toggle audio feedback on moves, captures, checks, and castles.

---

## 4. Dependencies for Local Execution

The generated `.exe` is mostly standalone, but it requires the following external components:

1.  **Stockfish Engine**: As mentioned above, this is **not bundled** and must be downloaded separately.
2.  **VS C++ Redistributable**: On some fresh Windows installations, you might need the Visual C++ Redistributable packages (typically already installed on most systems).
3.  **Internet Connection**: Required for:
    *   Importing games from Chess.com/Lichess.
    *   Fetching Opening names (if using online book).
    *   Generating AI Summaries (Groq).

---

## 5. Auto-Generated Files

The application automatically creates and manages the following files inside OS-specific user data directories:

| File | Purpose |
| :--- | :--- |
| **`config.json`** | Stores your saved settings (engine path, usernames, theme preferences, LLM profiles). |
| **`analysis_cache.db`** | A SQLite database that stores your game history and position analysis cache, making future reviews instant. |
| **`chess_analyzer.log`** | A text file containing application logs, useful for debugging errors or crashes. |

---

## 6. Data Privacy & Local Storage

Your privacy is paramount. **We do not collect any personal data.**

*   **Local Storage**: All your data, including game history, analysis results (`analysis_cache.db`), and configurations (`config.json`), remains strictly on your local machine in the system user data folder.
*   **No Cloud Sync**: We do not send your games or analysis to any remote server (except to LLM/Lichess/Chess.com APIs when you explicitly trigger those features).
*   **API Keys**: Your LLM keys and Lichess tokens are stored locally in `config.json` and are **never** shared with us.

---

## 7. How to Use: A to Z

### Loading Games
Click **Load Game** (or press `Ctrl+O`) to open the unified game loader:
1.  **PGN File**: Drag and drop or browse for local `.pgn` files.
2.  **Paste PGN**: Paste raw PGN text directly from your clipboard.
3.  **Chess.com**: Enter a Chess.com username to fetch recent games, or paste a game URL directly.
4.  **Lichess**: Enter a Lichess username to fetch recent games, or paste a game URL directly.

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

### Analysis Explorer
The Analysis Explorer is a dedicated interactive view for analyzing positions outside the main game flow. Access it by clicking "Explore from here" in the analysis panel.

*   **Independent Board**: The explorer has its own chessboard with click-to-move and drag-and-drop support. Legal-move dots and selection highlights make move entry easy.
*   **Move List**: A move list tracks all moves played within the explorer session. Click any move to navigate back; use the navigation buttons (first, prev, next, last) for quick movement.
*   **Inline Move Input**: Type moves in standard algebraic notation (e.g. "e4", "Nf3", "O-O") directly into the "type SAN move..." field in the Moves header. Press Enter to play the move. Case-insensitive: "bxf2" works the same as "Bxf2".
*   **Opening Book**: The explorer has a built-in Lichess ECO opening database. As you navigate, the "Book Moves" panel shows known opening moves from the database with statistics. Click a book move to navigate to it.
*   **Engine Analysis**: Enable "Engine Lines" to see live Stockfish evaluation in the current position. Each line shows the eval score, depth, and principal variation. Click any engine line to play its first move on the board.
*   **Move Classification**: Toggle "Classify Moves" to automatically classify moves as Brilliant, Great, Best, Excellent, Good, Inaccuracy, Mistake, Blunder, Miss, or Book. When enabled, all unclassified moves are processed sequentially (backlog classification).
*   **Board Actions**: Use the toolbar to Flip Board, Copy FEN (current position as FEN string), or Copy PGN (all moves as PGN text).
*   **Captured Pieces**: Captured pieces for each side are shown above and below the board with a material advantage indicator. The border hides when no pieces are captured.
*   **Toggles**:
    - **Classify Moves**: Auto-classify moves during exploration.
    - **Legal Moves**: Show/hide legal move dots on the board.
    - **Engine Lines**: Enable/disable live Stockfish analysis.
    - **Use Cache**: Cache engine analysis results for faster revisit.

### Detailed Stats
*   **Game Stats**: View accuracy per player, opening name, and blunder counts in the **Analysis Panel**.
*   **Global Stats (Metrics)**: Click the **Stats** icon in the sidebar to see your performance over time (Win/Loss rates, accuracy trends) across all analyzed games.
*   **Stats by Piece Color**: View your performance breakdown by piece color (White vs Black) to understand how you play from each side.

### History & Caching
*   **History Tab**: Keeps a record of all games you've analyzed. Double-click any entry to reload that game.
*   **Analysis Cache**: The app remembers every position it has analyzed.

### Data Management
*   **Export History**: Go to **Settings > Data Management > Export Games to CSV** to backup your game history.
*   **Import History**: Use **Import Games from CSV** to restore your history (e.g., on a new computer).
*   **Clear Data**: You can clear the cache or entire history from the Settings tab if needed.

---

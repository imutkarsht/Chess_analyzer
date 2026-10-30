# How to Use Chess Analyzer Pro

This comprehensive guide takes you from installation to mastering the advanced features of Chess Analyzer Pro.

## 1. Getting the Latest Build

To get the latest version of the application:

1.  **Clone/Pull the Repository**: Ensure you have the latest code from GitHub.
    ```bash
    git pull origin master
    ```
2.  **Build the Executable**: We use PyInstaller and platform installer scripts to create standalone packages (`.dmg` for macOS, `.exe` for Windows, `.AppImage` for Linux).

    ```bash
    pyinstaller build.spec
    ```

    _This will create a `dist` folder containing the executable bundle._

3.  **Or Download Pre-built Releases**:
    - Download the latest release installer for your platform from the [GitHub Releases page](https://github.com/imutkarsht/Chess_analyzer/releases).

---

## 2. Running the Application

1.  Navigate to the `dist` folder created in the previous step (or install from the downloaded release).
2.  Launch **`ChessAnalyzerPro`** (or `ChessAnalyzerPro.exe` on Windows).

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

- **LLM Profiles (AI summaries & coaching)**:
  - The application supports multiple **LLM Profiles** with different providers.
  - Select from **Groq** (Cloud), **LM Studio** (Local), **MiniMax** (Cloud), or **Custom** (any OpenAI-compatible endpoint).
  - Provide the **API Key**, **Model ID**, and **Base URL** (if using LM Studio or a Custom endpoint).
  - Select your active profile. All API insights will use the active profile.
- **Lichess API Token**:
  - Required for live Opening Explorer lookups and for importing private games; public imports work without it but are rate-limited.
  - Generate a token at [lichess.org/account/oauth/token](https://lichess.org/account/oauth/token) with the `Read games` scope.
  - Paste it into the **Lichess API Token** field in Settings → Integrations and click **Save**. Explorer requests are throttled to your account budget, and cached/book data stays available offline.

### C. Player Usernames

Pre-configure your usernames to make loading games faster:

- Enter your **Chess.com** and **Lichess.org** usernames in **Settings > Player Usernames** and click **Save**.
- Once saved, the Load Game dialog will auto-fill with these names and personal stats calculations will automatically filter to show your games.

### D. Appearance & Audio

- **Accent Color**: Select an accent color in **Settings > Appearance**. Changing the color updates the entire UI in real time.
- **Board & Piece Themes**: Select a board theme (Green, Blue, Brown, Gray, Purple, Teal, Cherry, Neon) and piece set (cburnett, merida, alpha, cardinal, chess7) to update the visual board immediately. New installs start on the warm **Brown** theme.
- **Board Display**: Toggle coordinates and move-quality badges independently; both apply live to the Analysis and Explorer boards.
- **Custom SVG Theme Import**: You can import any folder of 12 SVG piece images (`wk.svg`, `bp.svg`, etc.) in Appearance Settings. The app will automatically scale and normalize them to fit the board properly.
- **Sound Effects**: Check or uncheck **Enable Sound Effects** in **Settings > Appearance** to toggle audio feedback on moves, captures, checks, and castles.

---

## 4. Dependencies for Local Execution

The generated `.exe` is mostly standalone, but it requires the following external components:

1.  **Stockfish Engine**: As mentioned above, this is **not bundled** and must be downloaded separately.
2.  **VS C++ Redistributable**: On some fresh Windows installations, you might need the Visual C++ Redistributable packages (typically already installed on most systems).
3.  **Internet Connection**: Required only for optional features:
    - Importing games from Chess.com/Lichess.
    - Live Opening Explorer lookups (with a Lichess token).
    - Generating AI explanations and summaries.
    - Checking for and downloading updates.

---

## 5. Auto-Generated Files

The application automatically creates and manages the following files inside OS-specific user data directories:

| File | Purpose |
| :-- | :-- |
| **`config.json`** | Stores your saved settings (engine path, usernames, theme preferences, LLM profiles). |
| **`analysis_cache.db`** | A SQLite database that stores your game history and position analysis cache, making future reviews instant. |
| **`chess_analyzer.log`** | A text file containing application logs, useful for debugging errors or crashes. |
| **`analysis_cache.db.pre-restore.db`** | Automatic safety copy written next to the database before a restore. |
| **Backup files** | `chess-analyzer-backup-<timestamp>.db`, saved wherever you choose (defaults to Documents). |

Credentials (LLM keys and the Lichess token) are **not** written to these files;
they live in the OS credential store through `keyring`.

---

## 6. Data Privacy & Local Storage

Your privacy is paramount. **We do not collect any personal data.**

- **Local Storage**: All your data, including game history, analysis results (`analysis_cache.db`), and configurations (`config.json`), remains strictly on your local machine in the system user data folder.
- **No Cloud Sync**: We do not send your games or analysis to any remote server (except to LLM/Lichess/Chess.com APIs when you explicitly trigger those features).
- **API Keys**: Your LLM keys and Lichess tokens are stored in your operating system's credential store (macOS Keychain, Windows Credential Locker, or Linux Secret Service) and are **never** shared with us or written to plaintext `config.json`.

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

- **Start Analysis**: Click the **Analyze Game** button in the analysis header. The engine will evaluate every move.
- **Navigation**:
  - Use the **Arrow Keys** (Left/Right) to move through the game.
  - Use the shortcut preset (Standard or Vim) to jump to the next/previous critical move, start auto-replay, or switch pages. Press `F1` for the full cheat sheet.
  - Click on any move in the **Move List** to jump to that position.
  - Drag the scrollbar or click on the **Evaluation Graph** to jump to key moments.
- **Move Classification**:
  - Moves are color-coded:
    - 🔵 **Brilliant/Great**: Exceptional play.
    - 🟢 **Best/Excellent**: Optimal moves.
    - 🟡 **Inaccuracy**: Slight loss of advantage.
    - 🔴 **Mistake/Blunder**: Significant errors.
- **Status bar**: When idle it shows only `● Engine ready`; progress, warnings, and errors appear next to it only while they are relevant.

### AI Coach

The Coach tab turns engine facts into readable explanations:

- **Per-move explanation**: Select a move and open the Coach tab. The explanation is built from a deterministic fact sheet (classification, evaluation swing, tactical motifs, candidate lines), validated before display, and cached with a configurable TTL.
- **Full-game summary**: After analysis completes, generate a persistent game report; it is stored with the game and shown again on later visits.
- **Offline behaviour**: With no active LLM profile or no network, the app shows a deterministic offline explanation instead of failing.
- **Tuning**: Settings → AI Coach exposes temperature, max tokens, and reasoning effort. “Test Connection” exercises the same parameters as a real explanation.
- **Privacy**: Only the grounded fact sheet and prompt are sent to the configured endpoint — never your database or full game archive.

### Variations & Branch Explorer

- **Start a branch**: Use “Show best move”, “Show refutation”, or click any engine line to branch from the current position.
- **Persistent tree**: Variations are keyed by FEN and survive leaving/re-entering variation mode for the session.
- **Branch graph**: The strip under the board shows lanes and nodes; click a node to jump, rename or delete branches.
- **Move list badges**: Positions that already have saved analysis show a badge; cycle sibling branches from the move list.
- **Limits**: Branches are evicted at a configurable cap to keep the session responsive.

### Analysis Explorer

The Analysis Explorer is a dedicated interactive view for analyzing positions outside the main game flow. Access it by clicking "Explore from here" in the analysis panel.

- **Independent Board**: The explorer has its own chessboard with click-to-move and drag-and-drop support. Legal-move dots and selection highlights make move entry easy.
- **Move List**: A move list tracks all moves played within the explorer session. Click any move to navigate back; use the navigation buttons (first, prev, next, last) for quick movement.
- **Inline Move Input**: Type moves in standard algebraic notation (e.g. "e4", "Nf3", "O-O") directly into the "type SAN move..." field in the Moves header. Press Enter to play the move. Case-insensitive: "bxf2" works the same as "Bxf2".
- **Opening Book**: The explorer has a built-in Lichess ECO opening database. As you navigate, the "Book Moves" panel shows known opening moves from the database with statistics. Click a book move to navigate to it.
- **Engine Analysis**: Enable "Engine Lines" to see live Stockfish evaluation in the current position. Each line shows the eval score, depth, and principal variation. Click any engine line to play its first move on the board.
- **Move Classification**: Toggle "Classify Moves" to automatically classify moves as Brilliant, Great, Best, Excellent, Good, Inaccuracy, Mistake, Blunder, Miss, or Book. When enabled, all unclassified moves are processed sequentially (backlog classification).
- **Board Actions**: Use the toolbar to Flip Board, Copy FEN (current position as FEN string), or Copy PGN (all moves as PGN text).
- **Captured Pieces**: Captured pieces for each side are shown above and below the board with a material advantage indicator. The border hides when no pieces are captured.
- **Toggles**:
  - **Classify Moves**: Auto-classify moves during exploration.
  - **Legal Moves**: Show/hide legal move dots on the board.
  - **Engine Lines**: Enable/disable live Stockfish analysis.
  - **Use Cache**: Cache engine analysis results for faster revisit.

### Detailed Stats

- **Game Stats**: View accuracy per player, opening name, and blunder counts in the **Analysis Panel**.
- **Global Stats (Metrics)**: Click the **Stats** icon in the sidebar to see your performance over time (Win/Loss rates, accuracy trends) across all analyzed games.
- **Stats by Piece Color**: View your performance breakdown by piece color (White vs Black) to understand how you play from each side.

### History & Caching

- **History Tab**: Keeps a record of every game you've analyzed. Double-click any entry to reload it.
- **Layouts**: Switch between detailed cards and compact rows; the default layout is an Appearance setting and the header toggle overrides it for the session.
- **Paging**: Games load one page at a time (10 detailed / 15 compact) and the next page is prefetched while you read, so scrolling stays smooth even with large libraries.
- **Filters**: Search by player, opening, or date; filter by result, type, and source. Input is debounced so typing stays responsive.
- **Analysis Cache**: The app remembers every position it has analyzed, so repeat reviews are instant.

### Data Management

- **Export History**: **Settings > Data Management > Export Games to CSV**.
- **Import History**: **Import Games from CSV** to restore a library on another machine.
- **Backup & Restore**: Create and validate a full database backup, with an automatic safety copy before a restore.
- **Storage Report**: See what the local database actually holds and open the data folder directly.
- **Retention**: Set explorer/explanation cache TTLs and the analysis-cache capacity; pruning runs as values are saved.
- **Maintenance**: Compact the database (`VACUUM`) and clear individual caches.
- **Danger Zone**: Reset local data only after an explicit confirmation.

---

# Chess Analyzer Pro

![License](https://img.shields.io/badge/license-MIT-blue.svg) ![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg) [![Test Suite](https://github.com/imutkarsht/Chess_analyzer/actions/workflows/test.yml/badge.svg)](https://github.com/imutkarsht/Chess_analyzer/actions/workflows/test.yml) ![Version](https://img.shields.io/badge/version-2.5.0-green.svg)

![Chess Analyzer Pro Logo](assets/images/logo.png)

> 🌐 **Official Website:** [chessanalyzer.xyz](https://chessanalyzer.xyz/)  
> Visit the official site for detailed documentation, latest updates, and to report bugs or request features.

## 🎥 Showcase

<p align="center">
  <a href="https://ik.imagekit.io/hghxc7q4v/Chess%20Analyzer/v2.1/showcasevideo.mp4" target="_blank">
    <img src="https://ik.imagekit.io/hghxc7q4v/Chess%20Analyzer/app/dark/native/analysis_loaded.png" alt="Chess Analyzer Pro showcase" width="90%">
    <br>
    <sub>▶ Click to watch the showcase video</sub>
  </a>
</p>

**Chess Analyzer Pro** is a powerful, full-stack Python desktop application designed to bring professional-grade chess analysis to your local machine. Inspired by platforms like Chess.com, it combines the robust analysis capabilities of Stockfish with a sleek, responsive PyQt6 interface.

## ✨ What's New in 2.5.0

- **AI Coach with grounded move explanations** — every explanation is built from deterministic engine facts, validated before display, and falls back to an offline explanation when no provider is available.
- **Playable variations and a branch explorer** — branch from the best move, a refutation, or any engine line, with persistent trees, a branch graph, and saved-tree badges in the move list.
- **Settings page overhaul** — a schema-driven registry, searchable category rail, Basic/Advanced split, and a complete Data & Storage suite with backup, restore, retention, and maintenance.
- **History page optimisation** — paged loading, idle prefetch of the next page, debounced filters, and a persisted default card/compact layout.
- **UI refactor and component platform** — one shared component library (`Button`, `Input`, `Select`, `Tabs`, `Toast`, `DatePicker`, `PaginationBar`, and more) behind a single facade, `MainWindow` split into focused mixins, and one style generator per control.

See the [CHANGELOG](CHANGELOG.md) for the full release and [docs/architecture.md](docs/architecture.md) for how the codebase is organised.

## 📸 Screenshots

| Deep Analysis & Live Lines | Opening Explorer |
| :-: | :-: |
| ![Analysis View](https://ik.imagekit.io/hghxc7q4v/Chess%20Analyzer/app/dark/native/analysis_loaded.png) | ![Opening Explorer](https://ik.imagekit.io/hghxc7q4v/Chess%20Analyzer/app/dark/native/explorer_engine.png) |

| Performance Dashboard | AI Coach Summary |
| :-: | :-: |
| ![Performance Metrics](https://ik.imagekit.io/hghxc7q4v/Chess%20Analyzer/app/dark/native/metrics_dashboard.png) | ![AI Coach Summary](https://ik.imagekit.io/hghxc7q4v/Chess%20Analyzer/app/dark/native/analysis_coach_summary.png) |

| Playable Variations | Game History |
| :-: | :-: |
| ![Variations](https://ik.imagekit.io/hghxc7q4v/Chess%20Analyzer/app/dark/native/variation_tree.png) | ![Game History](https://ik.imagekit.io/hghxc7q4v/Chess%20Analyzer/app/dark/native/history_detailed.png) |

| Interactive Landing Hub | Load Game |
| :-: | :-: |
| ![Landing](https://ik.imagekit.io/hghxc7q4v/Chess%20Analyzer/app/dark/native/landing.png) | ![Load Game](https://ik.imagekit.io/hghxc7q4v/Chess%20Analyzer/app/dark/native/load_game_initial.png) |

## 🚀 Features

### Core Analysis

- **Stockfish Integration**: Leverages the world's strongest chess engine for deep analysis with **live move-by-move progressive updates** and pause/resume support.
- **Move Classification**: Automatically classifies every move (Brilliant, Great, Best, Excellent, Good, Inaccuracy, Mistake, Blunder, Miss) with sacrifice detection for brilliancies.
- **AI Coach & Move Explanations**: Grounded, per-move explanations built from deterministic engine facts, plus persistent full-game summaries. Uses any OpenAI-compatible endpoint — **Groq** (Cloud), **LM Studio** (Local), **MiniMax** (Cloud), or a Custom server — with an offline deterministic fallback.
- **Playable Variations & Branch Explorer**: Branch from the best move, a refutation, or any engine line. Variation trees are persistent for the session, shown as a branch graph with saved-tree badges and sibling cycling.
- **Win Probability**: Calculates and displays win probability swings for every move.
- **Opening Explorer**: Deep opening analysis using a built-in local SQLite openings database, custom Polyglot opening books (`*.bin` files), and live **Lichess game database integration** (a Lichess token is required for live data) with Win/Draw/Loss ratio bars.
- **Ending & Termination Analysis**: Detects and charts game outcomes by exact termination reason (Checkmate, Time, Resignation, Stalemate, Abandonment, Insufficient Material).

### Performance Analytics

- **Comprehensive Metrics Dashboard**: In-depth analytics tracking tactical motifs (forks, pins, skewers, hanging pieces), game phase accuracies (Opening, Middlegame, Endgame), and advantage conversion rates.
- **Interactive Stats Drill-Down**: Click on any metric card across your game library to launch an interactive position explorer with engine evaluations and candidate lines.
- **Player Rating Tracking**: Fetches and charts official player ratings across Bullet, Blitz, Rapid, Classical, and Puzzles from Chess.com and Lichess.

### User Interface

- **Interactive Landing & Historic Games Hub**: Launches into an engaging 60-40 split hero hub featuring 25 curated legendary games from history to explore on an interactive board, paired with a project welcome center.
- **Interactive Board**: Fully functional chessboard with drag-and-drop support, visual move indicators, legal move dots, and a warm Brown default theme.
- **Evaluation Graph**: Dynamic graph visualizing the game's evaluation flow with an interactive active move cursor pin.
- **Game List & History**: Modern desktop game cards or compact rows, time control badges, rating tags, paged loading with idle prefetch, and a persisted default layout.
- **Move List**: Detailed move history with classification icons, evaluation scores, live engine lines, and saved variation badges.
- **Keyboard Shortcuts**: Standard and Vim presets, move stepping, critical-move jumps, auto-replay, page switching, and an in-app cheat sheet.
- **Highly Configurable Settings**: Schema-driven settings with a searchable category rail, Basic/Advanced split, theme and board customization, AI Coach tuning, cache retention, backup/restore, and maintenance tools.
- **Customizable Dashboard**: Reorder chart cards while pinned summary cards stay fixed; the order persists across sessions.

### Import & Export

- **PGN Support**: Robust parsing for single and multi-game PGN files with drag-and-drop loading.
- **Direct Text Input**: Paste PGN text directly from your clipboard for quick analysis.
- **Web Imports**:
  - **Chess.com**: Import recent matches, filter archives by date, or load specific game URLs.
  - **Lichess**: Import recent matches, filter archives by date, or load specific game URLs.
- **Data Backup & Scalability**: Local SQLite storage supporting 1,000+ game archives, instant repeat loads, and full CSV export for external analysis.

### Audio & Visuals

- **Dual-Theme Support**: Full **Dark Mode** and **Light Mode** support with dynamic theme switching.
- **Live Accent Colors**: Change accent colors with instant live repainting without requiring an app restart.
- **Toast Notifications**: Clean floating toast alerts and styled confirmation dialogs.
- **Sound Effects**: Immersive audio feedback for moves, captures, checks, castles, and game completion.
- **Board Themes & Custom Pieces**: Multiple board colorways and custom piece SVG import support.

## 💻 Tech Stack

- **Core**: Python 3.10+
- **GUI**: PyQt6 (Modern, responsive desktop interface)
- **Engine**: Stockfish (Via UCI protocol for world-class analysis)
- **Database**: **SQLite** references locally (`analysis_cache.db`) to cache analysis results, ensuring instant loading for previously analyzed games.
- **Config**: Local `config.json` for persistent user settings, with `src/config/settings_schema.py` as the single source of defaults and validation. Credentials are stored through `keyring` in the OS credential store.
- **Networking**: `requests` with bundled `certifi` CAs for imports, updates, and LLM calls.
- **Integrations**:
  - **LLM Providers**: Grounded AI Coach explanations and game summaries. Natively supports **Groq**, **LM Studio**, **MiniMax**, and **Custom OpenAI-compatible** servers.
  - **Lichess & Chess.com**: Direct game import APIs and Lichess Opening Explorer.

## 🏗️ Architecture

The codebase is split into a Qt-free backend (`src/backend/`) and a PyQt6 presentation layer (`src/gui/`). GUI code imports shared widgets only from the `src.gui.components` facade, and `MainWindow` is composed from focused mixins. Full file-by-file reference, runtime flows, patterns, and extension recipes live in **[docs/architecture.md](docs/architecture.md)**.

```text
main.py → src/gui (views, components, dialogs) → src/backend (analysis, storage, APIs) → SQLite / Stockfish
```

## 🔒 Data Privacy & Local Storage

We prioritize your privacy. **Chess Analyzer Pro** is a "Local-First" application.

- **Local Database**: All analysis data and game history are stored in a local SQLite database (`analysis_cache.db`).
- **No Cloud Uploads**: Your games and moves are **never** uploaded to our servers. Analysis happens entirely on your machine using the bundled Stockfish engine.
- **Secure Credentials**: API keys and Lichess tokens are stored in your operating system’s credential store (macOS Keychain, Windows Credential Locker, or Linux Secret Service), never in the plaintext `config.json`.

## 🛠️ Installation

### Prerequisites

- Python 3.10 or higher
- [Stockfish Engine](https://stockfishchess.org/download/)

### Steps

1.  **Clone the Repository**

    ```bash
    git clone https://github.com/imutkarsht/Chess_analyzer.git
    cd Chess_analyzer
    ```

2.  **Create a Virtual Environment (Recommended)** Using [uv](https://github.com/astral-sh/uv) (faster and more reliable):

    ```bash
    # Install uv if you haven't already
    pip install uv

    # Create virtual environment
    uv venv .venv

    # Activate
    # Windows
    .venv\Scripts\activate
    # macOS/Linux
    source .venv/bin/activate
    ```

3.  **Install Dependencies**

    ```bash
    uv pip install -r requirements.txt
    ```

4.  **Setup Stockfish**
    - Download the Stockfish engine for your OS (or use the in-app downloader).
    - Extract the executable to a known location (e.g., inside a `stockfish/` folder in the project root).

## 🎮 Usage

1.  **Run the Application**

    ```bash
    python main.py
    ```

2.  **Configure Engine & Appearance**
    - Go to the **Settings** tab in the sidebar.
    - Under **Chess Engine**, enter or browse to your Stockfish executable path (or click Download Stockfish).
    - Under **Opening Book**, you can optionally specify a Polyglot opening book (`*.bin` file) to supplement opening line evaluations.
    - Under **Board & Pieces**, pick a board theme and piece set; new installs start on the warm Brown theme.

3.  **Load a Game**
    - Click **Load Game** at the top of the Analyze tab (or press `Ctrl+O`).
    - Choose your preferred loading method:
      - **Online Fetch**: Fetch from Chess.com or Lichess by recent games, date range, or game URL.
      - **PGN File**: Drag and drop or browse for `.pgn` files.
      - **PGN Text**: Paste raw PGN text directly.
    - Double-click or select a game and click **Load Game**.

4.  **Analyze**
    - Click **Analyze Game** in the analysis header.
    - Watch real-time evaluations and move classifications stream live onto the board and move list.
    - Once complete, explore the evaluation graph, accuracy summary, variations, and the AI Coach tab.

## 🧪 Testing

Run the test suite to ensure everything is working correctly:

```bash
# Install dev dependencies first
pip install -r requirements-dev.txt

# Run all tests (1,100+ tests; the suite should finish in under 20 seconds)
pytest tests/

# Check backend/utility branch coverage (85% floor; GUI modules excluded)
pytest tests/ --cov=src --cov-branch --cov-report=term-missing
```

> On Linux servers or CI without a display, set `QT_QPA_PLATFORM=offscreen` before running pytest.

Tests run against temporary data and must stay offline, fast, deterministic, and cross-platform. See [CONTRIBUTING.md](CONTRIBUTING.md#8-test-quality-expectations) for the full test-quality guidelines.

## 🤝 Contributing

Contributions are welcome, but they are **issue-first**: every pull request must close or reference an existing issue. If you want to add a feature or fix something that has no issue yet, open one and let a maintainer verify it before you start coding. PRs without a linked issue will not be approved.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow, development setup, test requirements, and branch conventions.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

> **Note:** The chess piece graphics in `assets/pieces/` are a separate third-party work dual-licensed upstream under GPLv2+ and CC BY-SA 3.0, used and distributed in this project under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) (see [Third-Party Assets](#third-party-assets) below).

## Third-Party Assets

The chess piece graphics shipped in [`assets/pieces/`](assets/pieces/) come from the **Cburnett** SVG chess set by **Colin M.L. Burnett**.

- Source: [Wikimedia Commons — SVG chess pieces](https://commons.wikimedia.org/wiki/Category:SVG_chess_pieces)
- Upstream License: Dual-licensed under **GPLv2+** and **CC BY-SA 3.0** (used here under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/))
- Per-file notice: see [`assets/pieces/THIRD-PARTY-README.md`](assets/pieces/THIRD-PARTY-README.md) and [`LICENSE`](LICENSE)

The SVGs are kept in a separate directory so they can be replaced or removed without touching the MIT-licensed source code.

## Acknowledgements

- [Stockfish](https://stockfishchess.org/) for the powerful chess engine.
- [Python-Chess](https://python-chess.readthedocs.io/) for the chess library.
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) for the GUI framework.
- [Lichess openings database](https://github.com/lichess-org/chess-openings) for providing the compiled opening datasets.
- Chess piece graphics by **Colin M.L. Burnett (Cburnett)**, distributed via [Wikimedia Commons](https://commons.wikimedia.org/wiki/Category:SVG_chess_pieces) and used in the [Lichess](https://lichess.org) project (CC BY-SA 3.0).

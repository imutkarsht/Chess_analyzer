# Chess Analyzer Pro

![Chess Analyzer Pro Logo](assets/images/logo.png)

**Chess Analyzer Pro** is a powerful, full-stack Python desktop application designed to bring professional-grade chess analysis to your local machine. Inspired by platforms like Chess.com, it combines the robust analysis capabilities of Stockfish with a sleek, responsive PyQt6 interface.

## 🚀 Features

### Core Analysis
- **Stockfish Integration**: Leverages the world's strongest chess engine for deep, move-by-move analysis.
- **Move Classification**: automatically classifies every move (Brilliant, Great, Best, Excellent, Good, Inaccuracy, Mistake, Blunder, Miss).
- **Win Probability**: Calculates and displays win probability swings for every move.
- **Opening Explorer**: Identifies openings and variations using a built-in book and online APIs.

### User Interface
- **Interactive Board**: Fully functional chessboard with drag-and-drop support and visual move indicators.
- **Evaluation Graph**: Dynamic graph visualizing the game's evaluation flow.
- **Game List**: Easy navigation between multiple games in a PGN.
- **Move List**: Detailed move history with classification icons and evaluation scores.

### Import & Export
- **PGN Support**: robust parsing for single and multi-game PGN files.
- **Chess.com Import**: Directly import games from Chess.com users or specific game URLs.

### Audio & Visuals
- **Sound Effects**: Immersive audio feedback for moves, captures, checks, castles, and game completion.
- **Themes**: Modern dark theme for reduced eye strain during long analysis sessions.

## 🛠️ Installation

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/yourusername/chess-analyzer-pro.git
    cd chess-analyzer-pro
    ```

2.  **Install Dependencies**
    Ensure you have Python 3.8+ installed.
    ```bash
    pip install -r requirements.txt
    ```

3.  **Setup Stockfish**
    - Download the Stockfish engine for your OS from [stockfishchess.org](https://stockfishchess.org/download/).
    - Extract the executable to a known location (e.g., inside a `stockfish/` folder in the project root).

## 🎮 Usage

1.  **Run the Application**
    ```bash
    python main.py
    ```

2.  **Configure Engine**
    - Upon first launch, or via `Settings > Configure Engine...`, select your Stockfish executable.

3.  **Load a Game**
    - **File > Open PGN...**: Load a local `.pgn` file.
    - **File > Load from Chess.com User...**: Fetch recent games for a specific user.
    - **File > Load from Chess.com URL...**: Analyze a specific game URL.

4.  **Analyze**
    - Click `Analysis > Analyze Game` to start the engine.
    - Watch the progress bar as the engine evaluates each move.
    - Once complete, explore the move list and graph!

## 🧪 Testing

Run the test suite to ensure everything is working correctly:

```bash
python -m pytest tests/
```

## 🔮 Roadmap (Version 2.0)

We are constantly improving Chess Analyzer Pro. Here is what's coming in the next major release:

- [ ] **Cloud Analysis**: Offload heavy analysis to cloud servers for faster results on lower-end hardware.
- [ ] **PDF Export**: Generate professional PDF reports of your games with diagrams and annotations.
- [ ] **Coach Mode**: AI-powered natural language explanations for *why* a move was good or bad.
- [ ] **Opening Repertoire Builder**: Tools to build and practice your opening repertoire.
- [ ] **Endgame Tablebases**: Integration with Syzygy tablebases for perfect endgame play.
- [ ] **Multi-Engine Support**: Compare analysis from different engines (e.g., Leela Chess Zero).

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

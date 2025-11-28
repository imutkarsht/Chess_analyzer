# Chess Analyzer Pro

A full-stack Python desktop application that accepts chess games as PGN, analyzes them with Stockfish, and presents a Chess.com-style game analysis.

## Features
- **PGN Support**: Load single or multiple games from PGN files.
- **Chess.com Integration**: Import games directly from Chess.com users or URLs.
- **Stockfish Analysis**: Integrates with Stockfish engine for deep analysis.
- **Opening Explorer**: Identifies openings using Lichess API and local cache.
- **Move Classification**: Automatically classifies moves (Best, Brilliant, Blunder, Mistake, etc.).
- **Evaluation Graph**: Visualizes the game's evaluation swing.
- **Sound Effects**: Immersive audio feedback for moves, captures, checks, and game end.
- **Caching**: Caches analysis results to avoid re-computation.
- **Responsive UI**: Built with PyQt6, ensuring a smooth experience.

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Stockfish Engine**:
   - Download Stockfish from [stockfishchess.org](https://stockfishchess.org/download/).
   - Place the executable in a known location.

3. **Run the Application**:
   ```bash
   python main.py
   ```

4. **Configure Engine**:
   - In the app, go to `Settings` -> `Configure Engine...`
   - Select your Stockfish executable.

## Development
- Run tests: `python tests/verify_backend.py`

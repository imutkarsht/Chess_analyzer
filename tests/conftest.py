"""
Shared pytest fixtures for Chess Analyzer tests.
"""
import pytest
import sys
import os
from PyQt6.QtWidgets import QApplication

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# ============ QT Application Fixture ============
@pytest.fixture(scope="session")
def qapp():
    """Provides a QApplication instance for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app

# ============ Mock Fixtures ============
@pytest.fixture
def mock_engine(mocker):
    """Mocks the chess engine."""
    mock = mocker.Mock()
    mock.analyse.return_value = {"score": mocker.Mock(white=lambda: mocker.Mock(score=lambda: 100))}
    return mock

@pytest.fixture
def mock_requests(mocker):
    """Mocks requests library for API tests."""
    return mocker.patch("requests.get")

# ============ Sample Data Fixtures ============
SAMPLE_PGN_CHESSCOM = """[Event "Live Chess"]
[Site "Chess.com"]
[Date "2023.10.01"]
[Round "-"]
[White "Player1"]
[Black "Player2"]
[Result "1-0"]
[WhiteElo "1500"]
[BlackElo "1400"]
[TimeControl "600"]
[ECO "C65"]
[Termination "Normal"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 Nf6 4. O-O Be7 5. Re1 b5 6. Bb3 d6 7. c3 O-O 1-0"""

SAMPLE_PGN_LICHESS = """[Event "Rated Blitz game"]
[Site "https://lichess.org/abcd1234"]
[Date "2023.10.01"]
[White "LichessPlayer1"]
[Black "LichessPlayer2"]
[Result "0-1"]

1. d4 d5 2. c4 e6 3. Nc3 Nf6 0-1"""

SAMPLE_PGN_FILE = """[Event "Local Game"]
[Site "?"]
[Date "2023.10.01"]
[White "LocalPlayer1"]
[Black "LocalPlayer2"]
[Result "1/2-1/2"]

1. e4 e5 2. Nf3 Nf6 1/2-1/2"""

@pytest.fixture
def sample_pgn_chesscom():
    """Sample Chess.com PGN."""
    return SAMPLE_PGN_CHESSCOM

@pytest.fixture
def sample_pgn_lichess():
    """Sample Lichess PGN."""
    return SAMPLE_PGN_LICHESS

@pytest.fixture
def sample_pgn_file():
    """Sample file-based PGN (no recognizable site)."""
    return SAMPLE_PGN_FILE

@pytest.fixture
def sample_game():
    """Creates a sample GameAnalysis object."""
    from src.backend.models import GameAnalysis, GameMetadata, MoveAnalysis
    import chess
    
    metadata = GameMetadata(
        white="TestWhite",
        black="TestBlack",
        result="1-0",
        date="2023.10.01",
        event="Test Event",
        headers={},
        white_elo="1500",
        black_elo="1400",
        source="chesscom"
    )
    
    moves = [
        MoveAnalysis(1, 1, "e4", "e2e4", chess.STARTING_FEN),
        MoveAnalysis(1, 2, "e5", "e7e5", "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"),
    ]
    
    return GameAnalysis(
        game_id="test_game_id",
        metadata=metadata,
        moves=moves,
        pgn_content=SAMPLE_PGN_CHESSCOM
    )

@pytest.fixture
def temp_db(tmp_path):
    """Creates a temporary database path."""
    db_path = tmp_path / "test_history.db"
    return str(db_path)

@pytest.fixture
def temp_config(tmp_path):
    """Creates a temporary config file path."""
    config_path = tmp_path / "config.json"
    return str(config_path)

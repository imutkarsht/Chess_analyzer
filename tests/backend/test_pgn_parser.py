"""
Tests for PGN Parser - parsing, source detection, edge cases.
"""
import pytest
from src.backend.pgn_parser import PGNParser
from src.backend.models import GameAnalysis


class TestPGNParsing:
    """Tests for basic PGN parsing functionality."""
    
    def test_parse_pgn_text_basic(self, sample_pgn_chesscom):
        """Test parsing a simple PGN string."""
        games = PGNParser.parse_pgn_text(sample_pgn_chesscom)
        
        assert len(games) == 1
        game = games[0]
        assert isinstance(game, GameAnalysis)
        assert game.metadata.white == "Player1"
        assert game.metadata.black == "Player2"
        assert game.metadata.result == "1-0"
        assert len(game.moves) > 0

    def test_parse_pgn_file(self, tmp_path, sample_pgn_chesscom):
        """Test parsing PGN from file."""
        pgn_file = tmp_path / "test.pgn"
        pgn_file.write_text(sample_pgn_chesscom, encoding="utf-8")
        
        games = PGNParser.parse_pgn_file(str(pgn_file))
        
        assert len(games) == 1
        assert games[0].metadata.white == "Player1"

    def test_parse_multiple_games(self, sample_pgn_chesscom, sample_pgn_lichess):
        """Test parsing multiple games in one PGN string."""
        combined_pgn = sample_pgn_chesscom + "\n\n" + sample_pgn_lichess
        games = PGNParser.parse_pgn_text(combined_pgn)
        
        assert len(games) == 2
        assert games[0].metadata.white == "Player1"
        assert games[1].metadata.white == "LichessPlayer1"

    def test_parse_empty_pgn(self):
        """Test parsing empty PGN returns empty list."""
        games = PGNParser.parse_pgn_text("")
        assert games == []

    def test_parse_invalid_pgn(self):
        """Test parsing invalid PGN is handled gracefully (returns game with no moves)."""
        games = PGNParser.parse_pgn_text("This is not a PGN")
        # Parser may return empty or a placeholder - either is acceptable
        assert games == [] or (len(games) == 1 and len(games[0].moves) == 0)


class TestSourceDetection:
    """Tests for source detection from Site header."""
    
    def test_detect_chesscom_source(self, sample_pgn_chesscom):
        """Test Chess.com source is detected correctly."""
        games = PGNParser.parse_pgn_text(sample_pgn_chesscom)
        assert games[0].metadata.source == "chesscom"

    def test_detect_lichess_source(self, sample_pgn_lichess):
        """Test Lichess source is detected correctly."""
        games = PGNParser.parse_pgn_text(sample_pgn_lichess)
        assert games[0].metadata.source == "lichess"

    def test_detect_file_source(self, sample_pgn_file):
        """Test unknown site defaults to 'file' source."""
        games = PGNParser.parse_pgn_text(sample_pgn_file)
        assert games[0].metadata.source == "file"


class TestMetadataExtraction:
    """Tests for metadata extraction from PGN headers."""
    
    def test_extract_elo_ratings(self, sample_pgn_chesscom):
        """Test ELO ratings are extracted."""
        games = PGNParser.parse_pgn_text(sample_pgn_chesscom)
        game = games[0]
        
        assert game.metadata.white_elo == "1500"
        assert game.metadata.black_elo == "1400"

    def test_extract_time_control(self, sample_pgn_chesscom):
        """Test time control is extracted."""
        games = PGNParser.parse_pgn_text(sample_pgn_chesscom)
        assert games[0].metadata.time_control == "600"

    def test_extract_eco(self, sample_pgn_chesscom):
        """Test ECO code is extracted."""
        games = PGNParser.parse_pgn_text(sample_pgn_chesscom)
        assert games[0].metadata.eco == "C65"

    def test_extract_termination(self, sample_pgn_chesscom):
        """Test termination is extracted."""
        games = PGNParser.parse_pgn_text(sample_pgn_chesscom)
        assert games[0].metadata.termination == "Normal"

"""
Tests for data models - GameMetadata, GameAnalysis, MoveAnalysis.
"""
import pytest
from src.backend.models import GameMetadata, GameAnalysis, MoveAnalysis


class TestGameMetadata:
    """Tests for GameMetadata dataclass."""
    
    def test_default_values(self):
        """Test default values are set correctly."""
        meta = GameMetadata(
            white="W", 
            black="B", 
            result="1-0", 
            date="2023.01.01", 
            event="Test", 
            headers={}
        )
        
        assert meta.source == "file"  # Default source
        assert meta.white_elo is None
        assert meta.black_elo is None
        assert meta.time_control is None
        assert meta.eco is None
        assert meta.termination is None
        assert meta.opening is None
        assert meta.starting_fen is None

    def test_all_fields(self):
        """Test all fields can be set."""
        meta = GameMetadata(
            white="Magnus",
            black="Hikaru",
            result="1/2-1/2",
            date="2023.12.01",
            event="World Championship",
            headers={"Site": "lichess.org"},
            white_elo="2800",
            black_elo="2750",
            time_control="180+2",
            eco="C65",
            termination="Normal",
            opening="Ruy Lopez",
            starting_fen=None,
            source="lichess"
        )
        
        assert meta.white == "Magnus"
        assert meta.source == "lichess"
        assert meta.white_elo == "2800"


class TestMoveAnalysis:
    """Tests for MoveAnalysis dataclass."""
    
    def test_basic_move(self):
        """Test creating a basic move."""
        move = MoveAnalysis(
            move_number=1,
            ply=1,
            san="e4",
            uci="e2e4",
            fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        )
        
        assert move.san == "e4"
        assert move.uci == "e2e4"
        assert move.classification == "Book"  # Default classification
        assert move.eval_before_cp is None

    def test_analyzed_move(self):
        """Test move with analysis data."""
        move = MoveAnalysis(
            move_number=1,
            ply=1,
            san="e4",
            uci="e2e4",
            fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            classification="Best",
            eval_before_cp=30,
            eval_after_cp=25
        )
        
        assert move.classification == "Best"
        assert move.eval_before_cp == 30


class TestGameAnalysis:
    """Tests for GameAnalysis dataclass."""
    
    def test_game_with_moves(self):
        """Test creating a game with moves."""
        meta = GameMetadata(
            white="W", black="B", result="1-0", 
            date="2023.01.01", event="Test", headers={}
        )
        moves = [
            MoveAnalysis(1, 1, "e4", "e2e4", "startfen"),
        ]
        
        game = GameAnalysis(
            game_id="test123",
            metadata=meta,
            moves=moves,
            pgn_content="1. e4 1-0"
        )
        
        assert game.game_id == "test123"
        assert len(game.moves) == 1
        assert game.summary == {}  # Empty dict, not analyzed yet

    def test_game_with_summary(self):
        """Test game with analysis summary."""
        meta = GameMetadata(
            white="W", black="B", result="1-0",
            date="2023.01.01", event="Test", headers={}
        )
        
        game = GameAnalysis(
            game_id="test123",
            metadata=meta,
            moves=[],
            pgn_content="1-0",
            summary={
                "white": {"accuracy": 85.5, "Best": 10, "Blunder": 1},
                "black": {"accuracy": 78.2, "Best": 8, "Blunder": 3}
            }
        )
        
        assert game.summary["white"]["accuracy"] == 85.5

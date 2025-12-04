import pytest
from src.gui.board_widget import BoardWidget
from src.backend.models import GameAnalysis, GameMetadata, MoveAnalysis
import chess

def test_board_widget_init(qapp):
    """Test BoardWidget initialization."""
    widget = BoardWidget()
    assert widget is not None
    assert widget.board.fen() == chess.STARTING_FEN

def test_set_position(qapp):
    """Test setting board position."""
    widget = BoardWidget()
    
    # Create a dummy game
    move = MoveAnalysis(1, 1, "e4", "e2e4", chess.STARTING_FEN)
    game = GameAnalysis("id", GameMetadata(), [move], "pgn")
    
    widget.load_game(game)
    widget.set_position(0)
    
    assert widget.board.move_stack[0].uci() == "e2e4"

def test_flip_board(qapp):
    """Test flipping the board."""
    widget = BoardWidget()
    assert widget.is_flipped == False
    widget.flip_board()
    assert widget.is_flipped == True

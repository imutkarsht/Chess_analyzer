import unittest
from unittest.mock import MagicMock
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from backend.analyzer import Analyzer
from backend.models import GameAnalysis, MoveAnalysis

class TestAnalyzerIndexError(unittest.TestCase):
    def test_analyze_game_with_empty_list_return(self):
        # Mock EngineManager
        mock_engine = MagicMock()
        
        # Mock analyze_position to return an EMPTY list
        mock_engine.analyze_position.return_value = []
        
        analyzer = Analyzer(mock_engine)
        
        # Create a dummy game
        game = GameAnalysis(game_id="test", metadata=MagicMock())
        move = MoveAnalysis(
            move_number=1, ply=1, san="e4", uci="e2e4", fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        )
        game.moves = [move]
        
        # Run analysis
        try:
            analyzer.analyze_game(game)
        except IndexError as e:
            self.fail(f"Analyzer crashed with IndexError: {e}")
        except Exception as e:
            # We expect it might crash with something else if we don't handle it, 
            # but we specifically want to avoid IndexError
            print(f"Caught expected other error or new error: {e}")

if __name__ == '__main__':
    unittest.main()

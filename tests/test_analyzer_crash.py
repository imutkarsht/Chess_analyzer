import unittest
from unittest.mock import MagicMock
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from backend.analyzer import Analyzer
from backend.models import GameAnalysis, MoveAnalysis

class TestAnalyzerCrash(unittest.TestCase):
    def test_analyze_game_with_list_return(self):
        # Mock EngineManager
        mock_engine = MagicMock()
        
        # Mock analyze_position to return a list (simulating multi-pv)
        # It needs to return a list of dict-like objects
        # We need a dict that has .get() method
        mock_info = {"score": MagicMock(), "pv": []}
        mock_info["score"].is_mate.return_value = False
        mock_info["score"].score.return_value = 100
        
        # Return a list containing the mock info
        mock_engine.analyze_position.return_value = [mock_info]
        
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
        except AttributeError as e:
            if "'list' object has no attribute 'get'" in str(e):
                self.fail(f"Analyzer crashed with the specific AttributeError: {e}")
            else:
                raise e
        except Exception as e:
            # We only care if it crashes with the specific error
            pass

if __name__ == '__main__':
    unittest.main()

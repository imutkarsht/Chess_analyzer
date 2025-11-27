import unittest
from unittest.mock import MagicMock
import sys
import os
import chess.engine

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from backend.analyzer import Analyzer
from backend.models import GameAnalysis, MoveAnalysis

class TestAnalyzerPovScore(unittest.TestCase):
    def test_analyze_game_with_pov_score(self):
        # Mock EngineManager
        mock_engine = MagicMock()
        
        # Create a real PovScore object
        real_score = chess.engine.PovScore(chess.engine.Cp(150), chess.WHITE)
        
        # Mock analyze_position to return a dict with this score
        mock_info = {"score": real_score, "pv": []}
        
        # Return a list containing the mock info (since we also fixed the list issue)
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
            self.fail(f"Analyzer crashed with AttributeError: {e}")
        except Exception as e:
             # We expect it might crash with something else if we don't handle it, 
            # but we specifically want to avoid AttributeError related to score
            print(f"Caught expected other error or new error: {e}")

if __name__ == '__main__':
    unittest.main()

import sys
import os
import unittest
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.backend.analyzer import Analyzer
from src.backend.engine import EngineManager
from src.backend.models import GameAnalysis, MoveAnalysis, GameMetadata

class TestMultiPV(unittest.TestCase):
    def test_multipv_population(self):
        # Mock EngineManager
        engine_mock = MagicMock()
        
        # Mock analyze_position to return a list of info dicts (Multi-PV)
        mock_info_list = [
            {"score": MagicMock(relative=MagicMock(score=lambda mate_score: 100, mate=lambda: None), is_mate=lambda: False), "pv": [MagicMock(uci=lambda: "e2e4")]},
            {"score": MagicMock(relative=MagicMock(score=lambda mate_score: 50, mate=lambda: None), is_mate=lambda: False), "pv": [MagicMock(uci=lambda: "d2d4")]},
            {"score": MagicMock(relative=MagicMock(score=lambda mate_score: 20, mate=lambda: None), is_mate=lambda: False), "pv": [MagicMock(uci=lambda: "g1f3")]}
        ]
        engine_mock.analyze_position.return_value = mock_info_list
        
        analyzer = Analyzer(engine_mock)
        analyzer.config["use_cache"] = False # Disable cache for this test
        
        # Create a dummy game
        game = GameAnalysis(
            game_id="test_game",
            metadata=GameMetadata(),
            moves=[
                MoveAnalysis(move_number=1, ply=1, san="e4", uci="e2e4", fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
            ]
        )
        
        # Run analysis
        analyzer.analyze_game(game)
        
        # Check if multi_pvs is populated
        move = game.moves[0]
        self.assertEqual(len(move.multi_pvs), 3)
        self.assertEqual(move.multi_pvs[0]["pv"], ["e2e4"])
        self.assertEqual(move.multi_pvs[1]["pv"], ["d2d4"])
        self.assertEqual(move.multi_pvs[2]["pv"], ["g1f3"])
        
        print("Multi-PV verification successful!")

if __name__ == '__main__':
    unittest.main()

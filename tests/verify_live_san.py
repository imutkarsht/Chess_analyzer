import sys
import os
import unittest
from unittest.mock import MagicMock
import chess

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.backend.analyzer import Analyzer
from src.backend.models import GameAnalysis, MoveAnalysis, GameMetadata
from src.gui.live_analysis import LiveAnalysisWorker

class TestLiveAnalysisSAN(unittest.TestCase):
    def test_san_conversion(self):
        # Mock EngineManager
        engine_mock = MagicMock()
        
        # Mock analyze_position to return UCI PVs
        mock_info_list = [
            {"score": MagicMock(relative=MagicMock(score=lambda mate_score: 100, mate=lambda: None), is_mate=lambda: False), "pv": [chess.Move.from_uci("e2e4")]},
        ]
        engine_mock.analyze_position.return_value = mock_info_list
        
        analyzer = Analyzer(engine_mock)
        analyzer.config["use_cache"] = False
        
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
        
        # Check SAN
        move = game.moves[0]
        self.assertEqual(move.multi_pvs[0]["pv_san"], "1. e4")
        print("SAN verification successful!")

    def test_live_worker_process_info(self):
        worker = LiveAnalysisWorker("dummy_path")
        board = chess.Board()
        
        # Mock info from engine
        info = {
            "depth": 10,
            "score": MagicMock(relative=MagicMock(score=lambda mate_score: 50, mate=lambda: None), is_mate=lambda: False),
            "pv": [chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")],
            "multipv": 1
        }
        
        result = worker._process_info(info, board)
        
        self.assertEqual(result["depth"], 10)
        self.assertEqual(result["score_value"], "0.50")
        self.assertEqual(result["pv_san"], "1. e4 e5")
        print("Live Worker info processing verification successful!")

if __name__ == '__main__':
    unittest.main()

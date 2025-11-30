import sys
import os
import unittest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock QApplication
app = QApplication(sys.argv)

from src.gui.graph_widget import GraphWidget

class TestGraphScaling(unittest.TestCase):
    def setUp(self):
        self.widget = GraphWidget()
        self.widget.ax = MagicMock()
        self.game_analysis = MagicMock()
        
    def test_scaling_drawish_game(self):
        """Test scaling for a game with small evals (< 100). Should floor at 100."""
        # Max eval 50
        move1 = MagicMock()
        move1.eval_after_cp = 50
        move1.eval_after_mate = None
        move1.classification = None
        
        self.game_analysis.moves = [move1]
        
        self.widget.plot_game(self.game_analysis)
        
        self.widget.ax.set_ylim.assert_called_with(-100, 100)
        
    def test_scaling_moderate_game(self):
        """Test scaling for a game with moderate evals (100-200). Should fit exactly."""
        # Max eval 150
        move1 = MagicMock()
        move1.eval_after_cp = 150
        move1.eval_after_mate = None
        move1.classification = None
        
        self.game_analysis.moves = [move1]
        
        self.widget.plot_game(self.game_analysis)
        
        self.widget.ax.set_ylim.assert_called_with(-150, 150)
        
    def test_scaling_extreme_game(self):
        """Test scaling for a game with extreme evals (> 200). Should cap at 200."""
        # Max eval 500 (should be clamped to 200 in data, and limit capped at 200)
        move1 = MagicMock()
        move1.eval_after_cp = 500
        move1.eval_after_mate = None
        move1.classification = None
        
        self.game_analysis.moves = [move1]
        
        self.widget.plot_game(self.game_analysis)
        
        # Data clamping check? Not easy to check internal list without mocking plot.
        # But we can check set_ylim.
        self.widget.ax.set_ylim.assert_called_with(-200, 200)

if __name__ == '__main__':
    unittest.main()

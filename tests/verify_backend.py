import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backend.pgn_parser import PGNParser
from src.backend.models import GameAnalysis

def test_backend():
    print("Testing PGN Parser...")
    pgn_path = os.path.join(os.path.dirname(__file__), '..', 'test.pgn')
    games = PGNParser.parse_pgn_file(pgn_path)
    
    if not games:
        print("FAIL: No games parsed.")
        return
    
    game = games[0]
    print(f"Parsed Game: {game.metadata.white} vs {game.metadata.black}")
    print(f"Moves: {len(game.moves)}")
    
    if len(game.moves) > 0:
        print(f"First move: {game.moves[0].san}")
        print("PASS: PGN Parsing")
    else:
        print("FAIL: No moves found")

if __name__ == "__main__":
    test_backend()

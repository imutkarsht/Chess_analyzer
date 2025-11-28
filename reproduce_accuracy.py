import sys
import os
import json

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from backend.pgn_parser import PGNParser
from backend.analyzer import Analyzer
from backend.engine import EngineManager

def main():
    pgn_file = "test.pgn"
    if not os.path.exists(pgn_file):
        print(f"Error: {pgn_file} not found.")
        return

    print(f"Parsing {pgn_file}...")
    games = PGNParser.parse_pgn_file(pgn_file)
    if not games:
        print("No games found.")
        return

    game = games[0]
    print(f"Game: {game.metadata.white} vs {game.metadata.black} ({game.metadata.result})")

    # Initialize Analyzer
    # Assuming stockfish is in PATH. If not, we might need to find it.
    # On Windows, it might be stockfish.exe
    engine_path = "stockfish"
    
    # Check if stockfish is in path or local folder
    engine_path = os.path.join(os.getcwd(), "stockfish", "stockfish-windows-x86-64-avx2.exe") # Assuming standard name, will check dir
    if not os.path.exists(engine_path):
        # Fallback to searching in stockfish dir
        stockfish_dir = os.path.join(os.getcwd(), "stockfish")
        if os.path.exists(stockfish_dir):
            for f in os.listdir(stockfish_dir):
                if f.endswith(".exe"):
                    engine_path = os.path.join(stockfish_dir, f)
                    break

    print(f"Using engine: {engine_path}")
    
    try:
        analyzer = Analyzer(EngineManager(engine_path))
        # Reduce time per move for faster repro
        analyzer.config["time_per_move"] = 0.01 
        
        print("Starting analysis...")
        analyzer.analyze_game(game, callback=lambda i, n: print(f"Analyzing move {i+1}/{n}", end='\r'))
        print("\nAnalysis complete.")
        
        summary = game.summary
        print("\nSummary:")
        print(json.dumps(summary, indent=2))
        
        white_accs = summary['white'].get('accuracies', [])
        black_accs = summary['black'].get('accuracies', [])
        
        print(f"\nWhite Accuracies ({len(white_accs)}): {white_accs}")
        print(f"Black Accuracies ({len(black_accs)}): {black_accs}")
        
        white_acc = summary['white'].get('accuracy', 0)
        black_acc = summary['black'].get('accuracy', 0)
        
        print(f"\nWhite Accuracy: {white_acc:.2f}%")
        print(f"Black Accuracy: {black_acc:.2f}%")
        
        if white_acc > black_acc and game.metadata.result == "0-1":
            print("\nISSUE REPRODUCED: White lost but has higher accuracy.")
        elif black_acc > white_acc and game.metadata.result == "1-0":
             print("\nISSUE REPRODUCED: Black lost but has higher accuracy.")
        else:
            print("\nResult seems consistent with accuracy (Winner has higher accuracy).")

    except Exception as e:
        print(f"\nError during analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

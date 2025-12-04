import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from backend.lichess_api import LichessAPI
import json

def test_normalization():
    print("Fetching games for 'monsieur_VK'...")
    games = LichessAPI.get_user_games("monsieur_VK", max_games=1)
    
    if not games:
        print("No games found or error fetching games.")
        return

    game = games[0]
    print("\nNormalized Game Data:")
    print(json.dumps(game, indent=2))

    # Verification checks
    required_fields = ["white", "black", "time_class", "end_time", "pgn", "url"]
    missing_fields = [field for field in required_fields if field not in game]
    
    if missing_fields:
        print(f"\nFAILED: Missing fields: {missing_fields}")
    else:
        print("\nSUCCESS: All required fields present.")
        
    if "username" not in game["white"] or "rating" not in game["white"]:
        print("FAILED: Missing white player details")
    else:
        print("SUCCESS: White player details present")

    if "username" not in game["black"] or "rating" not in game["black"]:
        print("FAILED: Missing black player details")
    else:
        print("SUCCESS: Black player details present")

if __name__ == "__main__":
    test_normalization()

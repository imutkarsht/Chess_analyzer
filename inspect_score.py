import chess.engine
import chess

def inspect_pov_score():
    # Create a dummy score
    # PovScore(Cp(100), chess.WHITE)
    score = chess.engine.PovScore(chess.engine.Cp(100), chess.WHITE)
    
    print(f"Type: {type(score)}")
    print(f"Relative: {score.relative}")
    print(f"Relative Type: {type(score.relative)}")
    print(f"Relative Dir: {dir(score.relative)}")
    
    try:
        print(f"Relative Score method: {score.relative.score(mate_score=10000)}")
    except AttributeError as e:
        print(f"Error calling relative.score(): {e}")

if __name__ == "__main__":
    inspect_pov_score()

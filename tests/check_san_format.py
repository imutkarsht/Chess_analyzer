import chess

def test_san_format():
    # Case 1: White to move, Move 1
    board = chess.Board()
    moves = [chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5"), chess.Move.from_uci("g1f3")]
    san = board.variation_san(moves)
    print(f"Start Pos (White): {san}")
    
    # Case 2: Black to move, Move 1
    board = chess.Board()
    board.push_uci("e2e4")
    moves = [chess.Move.from_uci("e7e5"), chess.Move.from_uci("g1f3"), chess.Move.from_uci("b8c6")]
    san = board.variation_san(moves)
    print(f"Move 1 (Black): {san}")
    
    # Case 3: Mid-game, White to move, Move 10
    fen = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQ1RK1 w kq - 4 5" # Move 5
    board = chess.Board(fen)
    moves = [chess.Move.from_uci("d2d3"), chess.Move.from_uci("d7d6")]
    san = board.variation_san(moves)
    print(f"Move 5 (White): {san}")

    # Case 4: Mid-game, Black to move, Move 5
    fen = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQ1RK1 b kq - 4 5" # Move 5, Black to move? 
    # FEN "w" means White to move. Let's make it "b".
    fen_b = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQ1RK1 b kq - 4 5"
    board = chess.Board(fen_b)
    moves = [chess.Move.from_uci("d7d6"), chess.Move.from_uci("d2d3")]
    san = board.variation_san(moves)
    print(f"Move 5 (Black): {san}")

if __name__ == "__main__":
    test_san_format()
